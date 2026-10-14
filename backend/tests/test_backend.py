from api.services.ingestion_jobs import process_next
from tests.pipeline_fake import PipelineClient
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from core.config import Settings
from api.main import create_app


class FakeProvider:
    def generate(self, instruction, evidence):
        citations = [evidence[0]['id']]
        if 'Build a learning plan' in instruction:
            return {'topics': [{'title': 'binary search', 'prerequisites': [], 'citations': citations}], 'concerns': [], 'citations': citations}
        if 'learner follow-up' in instruction:
            return {'content': 'Use sorted inputs.', 'citations': citations}
        if 'focused guide' in instruction:
            return {'title': 'Guide', 'content': 'A focused explanation.', 'citations': citations}
        if 'Evaluate understanding' in instruction:
            return {'verdict': 'needs_revision', 'explanation': 'Check the prerequisite.', 'next_step': 'Revisit the guide.', 'citations': citations}
        return {'prompt': 'Explain the scenario.', 'options': [], 'criteria': 'Private expected reasoning.', 'citations': citations}


class BackendTests(unittest.TestCase):
    def test_journey_flow_and_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(f'sqlite:///{root / "test.db"}', root / 'uploads', '', None, '')
            with TestClient(create_app(settings, FakeProvider(), pipeline_client=PipelineClient())) as client:
                client.headers['X-Stride-Request'] = '1'
                client.post('/auth/register', json={'name': 'Learner', 'email': 'learner@example.com', 'password': 'long secure test password'})
                journey = client.post('/journeys', json={'goal': 'exam', 'subject': 'Algorithms'}).json()
                prefix = f'/journeys/{journey["id"]}'
                headers = {}
                self.assertEqual(client.get('/auth/me').status_code, 200)
                self.assertEqual(client.post(prefix + '/documents', headers=headers, files={'file': ('notes.txt', b'Binary search halves a sorted search space.')} ).status_code, 202)
                self.assertTrue(process_next(settings, FakeProvider(), pipeline_client=PipelineClient()))
                self.assertEqual(client.post(prefix + '/guides', headers=headers, json={'topic': 'binary search'}).status_code, 200)
                question = client.post(prefix + '/questions', headers=headers, json={'topic': 'binary search'}).json()
                self.assertNotIn('criteria', question)
                response = client.post(prefix + f'/questions/{question["id"]}/answers', headers=headers, json={'answer': 'Search every element.'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(client.get(prefix + '/progress', headers=headers).json()['attempts']), 1)
                other = client.post('/journeys', json={'goal': 'new_field', 'subject': 'Math'}).json()
                other_prefix = f'/journeys/{other["id"]}'
                other_headers = {}
                self.assertEqual(client.post(other_prefix + f'/questions/{question["id"]}/answers', headers=other_headers, json={'answer': 'Test'}).status_code, 404)
                self.assertEqual(client.post(other_prefix + '/questions', headers=other_headers, json={'topic': 'math'}).status_code, 400)

    def test_upload_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(f'sqlite:///{root / "test.db"}', root / 'uploads', '', None, '', max_upload_bytes=4)
            with TestClient(create_app(settings, FakeProvider(), pipeline_client=PipelineClient())) as client:
                client.headers['X-Stride-Request'] = '1'
                client.post('/auth/register', json={'name': 'Learner', 'email': 'learner@example.com', 'password': 'long secure test password'})
                journey = client.post('/journeys', json={'goal': 'exam', 'subject': 'Math'}).json()
                response = client.post(f'/journeys/{journey["id"]}/documents', headers={}, files={'file': ('notes.txt', b'12345')})
                self.assertEqual(response.status_code, 413)


if __name__ == '__main__':
    unittest.main()
