from api.services.focused_learning import guide_instruction, topic_context
from utils.shutdown import shutdown_event, shutdown_signals, check_shutdown
import uuid
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from utils.observability import configure_logging, close_logging, get_logger, request_id, failure
import secrets
import time
import hashlib
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, Request
from core.config import Settings
from db.session import create_database
from db.models import Base, Journey, Document, Activity, Ownership
from api.services.loop_service import state_for, generate as provider_generate, source_context
from api.services.auth_service import COOKIE, session_user
from api.services.learning_service import authorize
from api.routes.accounts import account_router
from api.routes.journey_extras import extras_router
from providers.compatible import CompatibleProvider
from providers.transcription import create_transcriber
from pipeline.utils.parsers.media_parser import MEDIA_EXTENSIONS


from api.schemas.learning import JourneyInput, PracticeInput


def create_app(settings=None, provider=None, transcriber=None, pipeline_client=None):
    settings = settings or Settings.load()
    engine, sessions = create_database(settings.database_url)
    provider = provider or CompatibleProvider(settings)
    transcriber = transcriber or create_transcriber(settings)

    @asynccontextmanager
    async def lifespan(app):
        shutdown_event.clear()
        configure_logging(settings.log_dir or settings.storage.parent / 'logs', settings.log_level)
        try:
            Base.metadata.create_all(engine)
            settings.storage.mkdir(parents=True, exist_ok=True)
            with shutdown_signals():
                get_logger('app').info('application_started')
                yield
        finally:
            engine.dispose()
            close_logging()

    app = FastAPI(title='Stride', lifespan=lifespan)

    def db_session():
        with sessions() as db:
            db.info['settings'] = settings
            db.info['pipeline_client'] = pipeline_client
            yield db

    def current_user(request: Request, db=Depends(db_session)):
        return session_user(db, request.cookies.get(COOKIE))

    app.include_router(account_router(db_session, current_user, settings))
    app.include_router(extras_router(db_session, current_user, authorize, provider))

    def error_response(status, detail, code, stage=None, headers=None):
        error = {'code': code, 'request_id': request_id.get()}
        return JSONResponse({'detail': detail, 'error': error}, status_code=status, headers=headers)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        code = getattr(exc, 'code', f'HTTP_{exc.status_code}')
        get_logger('http').warning('request_rejected', extra={'fields': {'status': exc.status_code, 'error_code': code, 'stage': getattr(exc, 'stage', None)}})
        detail = exc.detail if exc.status_code < 500 or hasattr(exc, 'code') else 'We could not complete this request right now. Please try again later.'
        return error_response(exc.status_code, detail, code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        fields = sorted({str(e['loc'][-1]) for e in exc.errors()})
        get_logger('http').warning('validation_failed', extra={'fields': {'error_code': 'VALIDATION_FAILED'}})
        return error_response(422, 'Check these fields: ' + ', '.join(fields), 'VALIDATION_FAILED')

    @app.middleware('http')
    async def observe_request(request, call_next):
        try:
            correlation = str(uuid.UUID(request.headers.get('X-Request-ID', '')))
        except ValueError:
            correlation = str(uuid.uuid4())
        token = request_id.set(correlation)
        started = time.perf_counter()
        try:
            if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'} and request.headers.get('X-Stride-Request') != '1' and request.headers.get('X-LearnForward-Request') != '1':
                response = error_response(403, 'Missing X-Stride-Request header', 'CSRF_HEADER_MISSING')
            else:
                try:
                    check_shutdown()
                    response = await call_next(request)
                except Exception as exc:
                    error = failure('request', exc)
                    response = error_response(error.status_code, error.detail, error.code, error.stage)
            response.headers['Cache-Control'] = 'no-store'
            response.headers['X-Request-ID'] = correlation
            level = 'error' if response.status_code >= 500 else 'warning' if response.status_code >= 400 else 'info'
            route = request.scope.get('route')
            getattr(get_logger('http'), level)('request_completed', extra={'fields': {'method': request.method, 'route': getattr(route, 'path', 'unmatched'), 'status': response.status_code, 'duration_ms': round((time.perf_counter() - started) * 1000, 2)}})
            return response
        finally:
            request_id.reset(token)

    def generate(task, passages):
        return provider_generate(provider, task, passages)

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    @app.post('/journeys', status_code=201)
    def create_journey(body: JourneyInput, user=Depends(current_user), db=Depends(db_session)):
        if not body.subject.strip():
            raise HTTPException(422, 'Subject is required')
        journey = Journey(goal=body.goal, subject=body.subject.strip(), access_token=secrets.token_urlsafe(32))
        db.add(journey)
        db.flush()
        db.add(Ownership(journey_id=journey.id, user_id=user.id))
        state_for(db, journey.id)
        db.commit()
        return {'id': journey.id, 'goal': journey.goal, 'subject': journey.subject}

    @app.post('/journeys/{journey_id}/documents', status_code=202)
    def upload(journey_id: int, file: UploadFile = File(...), user=Depends(current_user), db=Depends(db_session)):
        authorize(journey_id, db, user)
        from pathlib import Path
        from db.models import DocumentIngestion
        from api.services.material_service import material_payload
        suffix = Path(file.filename or '').suffix.lower()
        if suffix not in {'.pdf', '.docx', '.txt', '.md'} | MEDIA_EXTENSIONS:
            raise HTTPException(415, 'Unsupported document or media format')
        content = file.file.read(settings.max_upload_bytes + 1)
        if len(content) > settings.max_upload_bytes:
            raise HTTPException(413, 'Upload exceeds size limit')
        if not content:
            raise HTTPException(422, 'Choose a file with readable content')
        path = settings.storage / (secrets.token_hex(16) + suffix)
        try:
            path.write_bytes(content)
            document = Document(journey_id=journey_id, name=Path(file.filename or f'material{suffix}').name, passages=[])
            db.add(document)
            db.flush()
            db.add(DocumentIngestion(document_id=document.id, file_path=str(path.resolve()),
                                     source_hash=hashlib.sha256(content).hexdigest(), status='queued',
                                     created_at=time.time(), updated_at=time.time()))
            from api.services.ingestion_queue import enqueue
            enqueue(db, document.id)
            db.commit()
        except Exception:
            db.rollback()
            path.unlink(missing_ok=True)
            raise
        get_logger('ingestion').info('upload_queued', extra={'fields': {'journey_id': journey_id, 'document_id': document.id, 'bytes': len(content), 'format': suffix}})
        return material_payload(db, document)

    @app.post('/journeys/{journey_id}/guides')
    def guide(journey_id: int, body: PracticeInput, user=Depends(current_user), db=Depends(db_session)):
        journey = authorize(journey_id, db, user)
        state = state_for(db, journey_id)
        revision = state.revision
        topic = topic_context(db, journey_id, body.topic)
        passages = source_context(db, journey_id, body.topic, limit=24, preferred_citations=topic.get('citations', []))
        result = generate(guide_instruction(journey, body.topic, topic), passages)
        if not isinstance(result.get('content'), str):
            raise HTTPException(502, 'Invalid guide response')
        db.refresh(state)
        if state.revision != revision:
            raise HTTPException(409, 'Materials changed during generation. Please retry.')
        activity = Activity(journey_id=journey_id, topic=body.topic, kind='guide', data={'result': result, 'evidence': passages, 'revision': revision, 'created_at': time.time()})
        db.add(activity)
        db.commit()
        return {**result, 'id': activity.id, 'sources': passages, 'revision': revision}

    return app


app = create_app()
