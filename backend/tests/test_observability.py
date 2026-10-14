import json
import tempfile
import unittest
import uuid
from pathlib import Path
from fastapi.testclient import TestClient
from api.main import create_app
from core.config import Settings
from utils.observability import failure


class LoggingTests(unittest.TestCase):
    def test_correlation_classification_and_secret_exclusion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = create_app(Settings(f'sqlite:///{root / "db.sqlite"}', root / 'uploads', '', None, ''))

            @app.get('/test-failure')
            def broken():
                try:
                    raise TimeoutError('private-token-and-document-text')
                except Exception as exc:
                    raise failure('generation', exc) from exc

            @app.get('/test-unexpected')
            def unexpected():
                raise RuntimeError('private-token-and-document-text')

            reference = str(uuid.uuid4())
            with TestClient(app) as client:
                response = client.get('/test-failure', headers={'X-Request-ID': reference})
                self.assertEqual(response.status_code, 504)
                self.assertEqual(response.json()['detail'], 'This is taking longer than expected. Please try again.')
                self.assertNotIn('stage', response.json()['error'])
                self.assertEqual(response.headers['X-Request-ID'], reference)
                self.assertEqual(response.json()['error']['request_id'], reference)
                self.assertEqual(response.json()['error']['code'], 'PROVIDER_TIMEOUT')
                self.assertEqual(client.get('/test-unexpected').status_code, 500)
                invalid = client.post('/auth/register', headers={'X-Stride-Request': '1'}, json={'password': 'private-token-and-document-text'})
                self.assertEqual(invalid.status_code, 422)
                self.assertEqual(invalid.json()['error']['code'], 'VALIDATION_FAILED')
                csrf = client.post('/auth/logout')
                self.assertEqual(csrf.json()['error']['code'], 'CSRF_HEADER_MISSING')
                self.assertIn('X-Request-ID', csrf.headers)
            content = (root / 'logs' / 'backend.jsonl').read_text()
            self.assertNotIn('private-token-and-document-text', content)
            records = [json.loads(line) for line in content.splitlines()]
            error = next(r for r in records if r.get('request_id') == reference and r['event'] == 'operation_failed')
            self.assertEqual(error['exception_chain'][0]['type'], 'TimeoutError')
            self.assertIn('model endpoint', error['diagnostic'])
            self.assertTrue(error['exception_chain'][0]['frames'])
            self.assertTrue(any(r['event'] == 'request_completed' and r.get('duration_ms') is not None for r in records))
