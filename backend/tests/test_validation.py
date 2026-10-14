from api.services.ingestion_jobs import process_next
from tests.pipeline_fake import PipelineClient
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from fastapi.testclient import TestClient
from api.main import create_app
from core.config import Settings
from utils.citations import validate_citations


class ValidationTests(unittest.TestCase):
    def test_citation_validation(self):
        evidence = [{'id': '1:0'}]
        validate_citations({'citations': ['1:0']}, evidence)
        for citations in ([], ['unknown'], [{}], None):
            with self.assertRaises(ValueError):
                validate_citations({'citations': citations}, evidence)

    def test_limits_must_be_positive(self):
        with self.assertRaises(ValueError):
            Settings('sqlite://', Path('.'), '', None, '', max_media_seconds=0)

    def test_injected_provider_cannot_bypass_source_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(f'sqlite:///{root / "test.db"}', root / 'uploads', '', None, '')
            provider = SimpleNamespace(generate=lambda task, evidence: {'content': 'Unsupported claim', 'citations': ['invented']})
            with TestClient(create_app(settings, provider, pipeline_client=PipelineClient())) as client:
                client.headers['X-Stride-Request'] = '1'
                client.post('/auth/register', json={'name': 'Learner', 'email': 'learner@example.com', 'password': 'long secure test password'})
                journey = client.post('/journeys', json={'goal': 'exam', 'subject': 'Math'}).json()
                prefix = f'/journeys/{journey["id"]}'
                headers = {}
                client.post(prefix + '/documents', headers=headers, files={'file': ('notes.txt', b'Addition combines numbers.')})
                process_next(settings, provider, pipeline_client=PipelineClient())
                self.assertEqual(client.post(prefix + '/guides', headers=headers, json={'topic': 'addition'}).status_code, 502)
