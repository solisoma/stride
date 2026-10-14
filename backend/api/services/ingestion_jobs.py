"""Persistent ingestion jobs: uploading never runs the processing pipeline."""
import hashlib
import json
import time
import uuid
from pathlib import Path, PureWindowsPath
from db.models import Document, DocumentIngestion, Journey, Base
from db.session import create_database
from pipeline.ingestor import Ingestor, consume, flatten_tree
from pipeline.utils.storage.storage_manager import StorageManager
from pipeline.utils.storage.checkpoint_cache import CheckpointCache
from pipeline.utils.core.helper_fns import serialize_branch
from providers.pipeline_client import create_pipeline_client
from providers.compatible import CompatibleProvider
from providers.transcription import create_transcriber
from api.services.loop_service import state_for, rebuild_plan
from utils.observability import request_id, failure, get_logger
from utils.shutdown import shutdown_event, check_shutdown


LABELS = {'pdf_page': 'Reading document pages', 'document_extract': 'Extracting document content',
          'extract_image_content': 'Reading embedded images', '_ask_llm_to_split': 'Organizing sections',
          '_summarize': 'Preparing summaries', '_summarize_cluster': 'Preparing group summaries',
          'transcribe': 'Transcribing media', 'docx_paragraph': 'Reading document content', 'cluster_batch': 'Grouping related sections'}


def recover_jobs(sessions):
    with sessions() as db:
        db.query(DocumentIngestion).filter_by(status='processing').update(
            {'status': 'queued', 'progress': 'Waiting to resume', 'error': ''}, synchronize_session=False)
        db.query(DocumentIngestion).filter_by(status='ready', plan_pending=True).update(
            {'plan_pending': False, 'progress': 'Ready', 'plan_error': 'Material is ready. Please rebuild your learning plan.'}, synchronize_session=False)
        db.commit()


def process_next(settings, provider=None, transcriber=None, pipeline_client=None, document_id=None, auto_retry=False):
    check_shutdown()
    engine, sessions = create_database(settings.database_url)
    reference = str(uuid.uuid4())
    token = request_id.set(reference)
    try:
        with sessions() as db:
            query = db.query(DocumentIngestion).filter_by(status='queued')
            if document_id is not None:
                query = query.filter_by(document_id=document_id)
            job = query.order_by(DocumentIngestion.created_at, DocumentIngestion.document_id).first()
            if job is None:
                return False
            document_id = job.document_id
            claimed = db.query(DocumentIngestion).filter_by(document_id=document_id, status='queued').update(
                {'status': 'processing', 'error': '', 'request_reference': reference,
                 'progress': 'Starting processing', 'attempts': DocumentIngestion.attempts + 1,
                 'updated_at': time.time()}, synchronize_session=False)
            db.commit()
            if not claimed:
                return False
            db.refresh(job)
            document = db.get(Document, document_id)
            if document is None:
                raise RuntimeError('Queued document is missing')
            source_key = f'{document.journey_id}:{job.source_hash}'
            provider = provider or CompatibleProvider(settings)
            transcriber = transcriber or create_transcriber(settings)
            storage = StorageManager(db, defer_cleanup=True)
            configuration = hashlib.sha256(json.dumps({
                'pipeline': 'persistent-ingestion-v2', 'hash': job.source_hash,
                'model': settings.model, 'tree': settings.tree_builder_model,
                'vision': settings.vision_model, 'transcription': settings.transcription_model,
                'summary': settings.summary_backend, 'fanout': settings.tree_fanout,
                'endpoint': settings.base_url, 'transcription_endpoint': settings.transcription_base_url,
                'transcription_provider': settings.transcription_provider, 'whisper_model': settings.whisper_model,
                'whisper_device': settings.whisper_device, 'whisper_language': settings.whisper_language,
            }, sort_keys=True).encode()).hexdigest()
            def progress(message):
                if shutdown_event.is_set():
                    return
                with sessions() as status_db:
                    status_db.query(DocumentIngestion).filter_by(document_id=document_id, status='processing').update(
                        {'progress': LABELS.get(message, 'Organizing learning material'), 'updated_at': time.time()}, synchronize_session=False)
                    status_db.commit()
            cache = CheckpointCache(sessions, document_id, configuration, progress)
            try:
                path = Path(job.file_path)
                if PureWindowsPath(job.file_path).is_absolute() and not path.is_absolute():
                    path = settings.storage / PureWindowsPath(job.file_path).name
                if not path.is_absolute():
                    path = settings.storage / path
                path = path.resolve()
                if not path.is_relative_to(settings.storage.resolve()) or not path.is_file():
                    raise ValueError('Uploaded file is unavailable')
                if hashlib.sha256(path.read_bytes()).hexdigest() != job.source_hash:
                    raise ValueError('Uploaded file has changed')
                if job.configuration and job.configuration != configuration:
                    cache.clear()
                    for suffix in ('', '_media', '_transcript'):
                        storage.delete_checkpoint(source_key, suffix)
                job.configuration = configuration
                db.commit()
                client = pipeline_client or create_pipeline_client(settings)
                db.info.update(settings=settings, pipeline_client=client)
                root = consume(Ingestor.process_file(source_key, path, storage, client, settings,
                              transcriber, cancel_event=shutdown_event, cache=cache), progress=progress)
                check_shutdown()
                document.passages = flatten_tree(root, document_id)
                root.header = document.name
                storage.save_document_tree(document_id, serialize_branch(root), settings.tree_fanout)
                state = state_for(db, document.journey_id)
                state.revision += 1
                state.plan_status = 'needs_rebuild'
                job.status, job.progress, job.error = 'ready', 'Updating your learning plan', ''
                job.plan_pending = True
                job.updated_at = time.time()
                db.commit()
            except BaseException as exc:
                db.rollback()
                job = db.get(DocumentIngestion, document_id)
                if job is not None:
                    if shutdown_event.is_set() or not isinstance(exc, Exception):
                        job.status, job.progress = 'queued', 'Waiting to resume'
                        job.error = ''
                    else:
                        error = failure('ingestion', exc, document_id=document_id)
                        job.status, job.progress, job.error = 'failed', 'Processing stopped', error.detail
                        if auto_retry and job.attempts < settings.ingestion_max_attempts:
                            from api.services.ingestion_queue import enqueue
                            enqueue(db, document_id, delayed=True)
                            job.status, job.progress, job.error = 'queued', 'Waiting to retry processing', ''
                    job.updated_at = time.time()
                    db.commit()
                if not isinstance(exc, Exception):
                    raise
                return True
            # Material readiness and its tree were committed before plan generation.
            try:
                rebuild_plan(db, db.get(Journey, document.journey_id), provider)
                job.plan_error = ''
            except BaseException as exc:
                db.rollback()
                job = db.get(DocumentIngestion, document_id)
                if job is None:
                    raise RuntimeError('Ingestion record disappeared during plan refresh') from exc
                if isinstance(exc, Exception) and not shutdown_event.is_set():
                    failure('plan_refresh', exc, document_id=document_id)
                job.plan_error = 'Material is ready, but we could not update your learning plan. Please try Rebuild plan.'
                if not isinstance(exc, Exception):
                    job.plan_pending = False
                    job.progress = 'Ready'
                    db.commit()
                    raise
            job.plan_pending, job.progress = False, 'Ready'
            db.commit()
            # Only discard processing checkpoints after the ready tree is committed.
            try:
                cache.clear()
                for suffix in ('', '_media', '_transcript'):
                    storage.delete_checkpoint(source_key, suffix)
            except Exception as exc:
                db.rollback()
                failure('checkpoint_cleanup', exc, document_id=document_id)
            get_logger('ingestion').info('ingestion_ready', extra={'fields': {'document_id': document_id, 'passages': len(document.passages)}})
            return True
    finally:
        request_id.reset(token)
        engine.dispose()


def initialize_worker(settings):
    engine, sessions = create_database(settings.database_url)
    Base.metadata.create_all(engine)
    recover_jobs(sessions)
    from api.services.ingestion_queue import enqueue
    from db.models import IngestionMessage
    with sessions() as db:
        existing = {row.document_id for row in db.query(IngestionMessage).all()}
        for job in db.query(DocumentIngestion).filter_by(status='queued').all():
            if job.document_id not in existing:
                enqueue(db, job.document_id)
        db.commit()
    engine.dispose()
