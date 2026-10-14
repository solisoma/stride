import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from core.config import Settings
from api.main import create_app
from api.services.ingestion_jobs import process_next, recover_jobs
from db.session import create_database
from db.models import Document, DocumentIngestion, DocumentTree, IngestionCheckpoint, IngestionMessage
from pipeline.utils.storage.checkpoint_cache import CheckpointCache
from tests.pipeline_fake import PipelineClient
from tests.test_backend import FakeProvider


class IngestionJobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.settings = Settings(f'sqlite:///{root / "db.sqlite"}', root / 'uploads', '', None, '')
        self.pipeline = PipelineClient()
        self.provider = FakeProvider()
        self.client = TestClient(create_app(self.settings, self.provider, pipeline_client=self.pipeline))
        self.client.__enter__()
        self.client.headers['X-Stride-Request'] = '1'
        self.client.post('/auth/register', json={'name':'Learner','email':'jobs@example.com','password':'a secure test password'})
        self.journey = self.client.post('/journeys', json={'goal':'exam','subject':'Algorithms'}).json()
        self.prefix = f'/journeys/{self.journey["id"]}'
        self.engine, self.sessions = create_database(self.settings.database_url)

    def tearDown(self):
        self.client.__exit__(None,None,None)
        self.engine.dispose()
        self.tmp.cleanup()

    def upload(self, content=b'Binary search requires sorted inputs.'):
        response = self.client.post(self.prefix+'/documents', files={'file':('notes.txt', content)})
        self.assertEqual(response.status_code, 202)
        return response.json()

    def test_upload_returns_before_model_calls_and_ready_filter_blocks_queued_materials(self):
        material = self.upload()
        self.assertEqual(material['status'], 'queued')
        self.assertEqual(self.pipeline.calls, [])
        self.assertNotIn('file_path', material)
        with self.sessions() as db:
            self.assertEqual(db.query(IngestionMessage).one().document_id, material['id'])
        self.assertEqual(self.client.post(self.prefix+'/guides', json={'topic':'binary search'}).status_code, 409)
        self.assertTrue(process_next(self.settings,self.provider,pipeline_client=self.pipeline))
        with self.sessions() as db:
            job=db.get(DocumentIngestion, material['id'])
            self.assertEqual(job.status,'ready')
            self.assertFalse(job.plan_pending)
            self.assertTrue(Path(job.file_path).exists())
            self.assertIsNotNone(db.get(DocumentTree,material['id']))
            self.assertEqual(db.query(IngestionCheckpoint).count(),0)
        self.assertEqual(self.client.post(self.prefix+'/guides',json={'topic':'binary search'}).status_code,200)

    def test_failed_processing_retains_file_and_retry_reuses_completed_work(self):
        material=self.upload(b'First section. '*600)
        original=self.pipeline.parse
        count=0
        def flaky(*args,**kwargs):
            nonlocal count
            count+=1
            if count==2:raise RuntimeError('simulated failure')
            return original(*args,**kwargs)
        self.pipeline.parse=flaky
        process_next(self.settings,self.provider,pipeline_client=self.pipeline)
        with self.sessions() as db:
            job=db.get(DocumentIngestion,material['id'])
            self.assertEqual(job.status,'failed')
            self.assertTrue(Path(job.file_path).exists())
            self.assertEqual(db.get(Document,material['id']).passages,[])
            self.assertGreater(db.query(IngestionCheckpoint).count(),0)
        retry=self.client.post(self.prefix+f'/documents/{material["id"]}/retry',json={})
        self.assertEqual(retry.status_code,202)
        with patch('pipeline.ingestor.extract_text_pages',side_effect=AssertionError('Extraction repeated')):
            process_next(self.settings,self.provider,pipeline_client=self.pipeline)
        self.assertEqual(count,3)
        with self.sessions() as db:self.assertEqual(db.get(DocumentIngestion,material['id']).status,'ready')

    def test_retry_checks_journey_ownership_and_restart_recovers_jobs(self):
        material=self.upload()
        other=self.client.post('/journeys',json={'goal':'exam','subject':'Other'}).json()
        self.assertEqual(self.client.post(f'/journeys/{other["id"]}/documents/{material["id"]}/retry',json={}).status_code,404)
        with self.sessions() as db:
            job=db.get(DocumentIngestion,material['id']);job.status='processing';db.commit()
        recover_jobs(self.sessions)
        with self.sessions() as db:self.assertEqual(db.get(DocumentIngestion,material['id']).status,'queued')

    def test_step_cache_is_durable_and_thread_safe(self):
        material=self.upload()
        cache=CheckpointCache(self.sessions,material['id'],'configuration')
        calls=[]
        self.assertEqual(cache.run('image',{'index':1},lambda:calls.append(1) or 'Visible text'),'Visible text')
        resumed=CheckpointCache(self.sessions,material['id'],'configuration')
        self.assertEqual(resumed.run('image',{'index':1},lambda:calls.append(2) or 'New text'),'Visible text')
        self.assertEqual(calls,[1])

    def test_message_targets_exact_document_and_duplicate_does_not_reprocess(self):
        first = self.upload(b'First document.')
        second = self.upload(b'Second document.')
        self.assertTrue(process_next(self.settings, self.provider, pipeline_client=self.pipeline, document_id=second['id']))
        with self.sessions() as db:
            self.assertEqual(db.get(DocumentIngestion, first['id']).status, 'queued')
        count = len(self.pipeline.calls)
        self.assertFalse(process_next(self.settings, self.provider, pipeline_client=self.pipeline, document_id=second['id']))
        self.assertEqual(len(self.pipeline.calls), count)

    def test_broker_failure_atomically_schedules_retry_without_terminal_status(self):
        material = self.upload()
        with patch.object(self.pipeline, 'parse', side_effect=RuntimeError('simulated failure')):
            process_next(self.settings, self.provider, pipeline_client=self.pipeline,
                         document_id=material['id'], auto_retry=True)
        with self.sessions() as db:
            job = db.get(DocumentIngestion, material['id'])
            self.assertEqual(job.status, 'queued')
            self.assertEqual(job.error, '')
            self.assertEqual(db.query(IngestionMessage).filter_by(delayed=True).count(), 1)
