from api.services.ingestion_jobs import process_next
from tests.pipeline_fake import PipelineClient
import json
import tempfile
import time
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from api.main import create_app
from core.config import Settings
from db.session import create_database
from db.models import AttemptMeta, User, LoginSession, Journey, Document


PASSWORD = 'a long test password for learning'


class Coach:
    def __init__(self):
        self.counter = 0
        self.fail = False
        self.concern = False
        self.evidence = []
        self.instruction = ''

    def generate(self, instruction, evidence):
        if self.fail:
            raise ValueError('simulated outage')
        self.evidence = evidence
        self.instruction = instruction
        citations = [evidence[0]['id']]
        if 'Build a learning plan' in instruction:
            return {'topics': [{'title': 'Binary search', 'prerequisites': [], 'citations': citations}], 'concerns': [{'source_claim': evidence[0]['text'], 'alternative': 'Sorted inputs are required (unverified model interpretation)', 'reason': 'The source may omit this prerequisite', 'citations': citations}] if self.concern else [], 'citations': citations}
        if 'Evaluate understanding' in instruction:
            task = json.loads(instruction)
            return {'verdict': 'correct' if 'sorted' in task['learner_answer'] else 'needs_revision', 'explanation': 'Binary search requires sorted input; an unsorted array does not preserve the elimination rule.', 'next_step': 'Try a fresh scenario.', 'citations': citations}
        if 'learner follow-up' in instruction:
            return {'content': 'Check whether inputs are sorted.', 'citations': citations}
        if 'focused guide' in instruction:
            return {'title': 'Binary search', 'content': 'Check sorted inputs.', 'citations': citations}
        self.counter += 1
        return {'prompt': f'Scenario {self.counter}: which input supports binary search?', 'options': [], 'criteria': 'Requires sorted input.', 'citations': citations}


class LearningLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.settings = Settings(f'sqlite:///{root / "db.sqlite"}', root / 'uploads', '', None, '')
        self.coach = Coach()
        self.pipeline = PipelineClient()
        self.app = create_app(self.settings, self.coach, pipeline_client=self.pipeline)
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.client.headers['X-Stride-Request'] = '1'
        self.assertEqual(self.client.post('/auth/register', json={'name': 'Ada', 'email': 'ada@example.com', 'password': PASSWORD}).status_code, 201)
        self.journey = self.client.post('/journeys', json={'goal': 'technical_interview', 'subject': 'Algorithms'}).json()
        self.prefix = f'/journeys/{self.journey["id"]}'

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()

    def upload(self, text=b'Binary search needs sorted inputs.'):
        result = self.client.post(self.prefix + '/documents', files={'file': ('notes.txt', text)})
        self.assertEqual(result.status_code, 202)
        self.assertTrue(process_next(self.settings, self.coach, pipeline_client=self.pipeline))
        return next(m for m in self.client.get(self.prefix + '/documents').json() if m['id'] == result.json()['id'])

    def question(self):
        result = self.client.post(self.prefix + '/questions', json={'topic': 'Binary search'})
        self.assertEqual(result.status_code, 200)
        self.assertNotIn('criteria', result.json())
        return result.json()

    def answer(self, question, text, submission='submission-1'):
        return self.client.post(self.prefix + f'/questions/{question["id"]}/answers', json={'answer': text, 'submission_id': submission})

    def test_accounts_isolation_csrf_and_password_storage(self):
        with TestClient(self.app) as other:
            self.assertEqual(other.get(self.prefix + '/progress').status_code, 401)
            self.assertEqual(other.post('/auth/login', json={'email': 'ada@example.com', 'password': PASSWORD}).status_code, 403)
            other.headers['X-Stride-Request'] = '1'
            other.post('/auth/register', json={'name': 'Other', 'email': 'other@example.com', 'password': PASSWORD})
            for route in ['/documents', '/plan', '/progress', '/chat', '/reviews', '/activities']:
                self.assertEqual(other.get(self.prefix + route).status_code, 404)
            self.assertEqual(other.get('/journeys').json(), [])
        engine, sessions = create_database(self.settings.database_url)
        with sessions() as db:
            self.assertNotEqual(db.query(User).filter_by(email='ada@example.com').one().password_hash, PASSWORD)
            self.assertEqual(len(db.query(LoginSession).first().token_hash), 64)
        engine.dispose()
        cookie = self.client.cookies.get('learnforward_session')
        self.client.post('/auth/logout')
        self.assertEqual(self.client.get('/auth/me').status_code, 401)
        self.client.cookies.set('learnforward_session', cookie)
        self.assertEqual(self.client.get('/auth/me').status_code, 401)
        self.assertEqual(self.client.post('/auth/login', json={'email': 'ada@example.com', 'password': 'incorrect'}).status_code, 401)

    def test_upload_refresh_keeps_progress_and_invalidates_questions(self):
        self.upload()
        q = self.question()
        self.assertEqual(self.answer(q, 'not sure').status_code, 200)
        old = self.question()
        self.upload(b'A second document on sorted arrays.')
        self.assertEqual(len(self.client.get(self.prefix + '/documents').json()), 2)
        progress = self.client.get(self.prefix + '/progress').json()
        self.assertEqual(len(progress['attempts']), 1)
        self.assertEqual(progress['topics'][0]['status'], 'recheck_after_update')
        self.assertEqual(self.answer(old, 'sorted', 'new-submission').status_code, 409)
        self.assertEqual(self.client.get(self.prefix + '/plan').json()['revision'], 2)

    def test_feedback_loop_idempotency_and_retention(self):
        self.upload()
        q = self.question()
        first = self.answer(q, 'not sure')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self.answer(q, 'not sure').json()['id'], first.json()['id'])
        self.assertEqual(self.answer(q, 'sorted inputs', 'repeat-the-same-question').status_code, 409)
        self.assertEqual(self.client.get(self.prefix + '/plan').json()['next']['action'], 'revise_then_practise')
        q2 = self.question()
        self.assertNotEqual(q['prompt'], q2['prompt'])
        self.assertTrue(q2['supported'])
        self.answer(q2, 'sorted inputs', 'submission-2')
        self.assertEqual(self.client.get(self.prefix + '/progress').json()['topics'][0]['status'], 'needs_independent_check')
        engine, sessions = create_database(self.settings.database_url)
        with sessions() as db:
            for meta in db.query(AttemptMeta).all():
                meta.created_at = time.time() - 90000
            db.commit()
        q3 = self.question()
        self.assertFalse(q3['supported'])
        self.answer(q3, 'sorted inputs', 'submission-3')
        self.assertEqual(self.client.get(self.prefix + '/progress').json()['topics'][0]['status'], 'revisit_later')
        with sessions() as db:
            db.query(AttemptMeta).filter_by(submission_id='submission-3').one().created_at -= 90000
            db.commit()
        self.answer(self.question(), 'sorted inputs', 'submission-4')
        self.assertEqual(self.client.get(self.prefix + '/progress').json()['topics'][0]['status'], 'retained_in_practice')
        engine.dispose()

    def test_saved_chat_guides_and_login_resume(self):
        self.upload()
        self.client.post(self.prefix + '/guides', json={'topic': 'Binary search'})
        self.client.post(self.prefix + '/chat', json={'message': 'Explain the sorted prerequisite'})
        self.answer(self.question(), 'sorted inputs')
        self.client.post('/auth/logout')
        self.client.post('/auth/login', json={'email': 'ada@example.com', 'password': PASSWORD})
        self.assertEqual(self.client.get('/journeys').json()[0]['id'], self.journey['id'])
        self.assertEqual(len(self.client.get(self.prefix + '/chat').json()), 1)
        self.assertEqual(len(self.client.get(self.prefix + '/progress').json()['attempts']), 1)
        self.assertEqual(self.client.get(self.prefix + '/activities').json()[-1]['kind'], 'guide')

    def test_source_disagreement_and_choice(self):
        self.coach.concern = True
        self.upload()
        review = self.client.get(self.prefix + '/reviews').json()[0]
        self.assertEqual(review['verification'], 'unverified comparison')
        self.assertEqual(self.client.post(self.prefix + f'/reviews/{review["id"]}', json={'decision': 'use_alternative', 'note': 'Use sorted inputs.'}).status_code, 200)
        self.question()
        self.assertEqual(self.coach.evidence[0]['source_review']['decision'], 'use_alternative')
        self.client.post(self.prefix + f'/reviews/{review["id"]}', json={'decision': 'exclude'})
        self.assertEqual(self.client.post(self.prefix + '/questions', json={'topic': 'Binary search'}).status_code, 400)

    def test_failed_plan_does_not_lose_upload(self):
        self.coach.fail = True
        result = self.upload()
        self.assertTrue(result['plan_error'])
        self.assertEqual(len(self.client.get(self.prefix + '/documents').json()), 1)
        self.coach.fail = False
        self.assertEqual(self.client.post(self.prefix + '/plan').status_code, 200)

    def test_study_chat_context_and_stale_guides(self):
        self.upload()
        guide = self.client.post(self.prefix + '/guides', json={'topic': 'Binary search'}).json()
        reply = self.client.post(self.prefix + '/chat', json={'message': 'Explain this section', 'activity_id': guide['id']})
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json()['context']['kind'], 'guide')
        context = json.loads(self.coach.instruction)['learning_context']
        self.assertEqual(context['content'], guide['content'])
        self.upload(b'More current material about sorted inputs.')
        reply = self.client.post(self.prefix + '/chat', json={'message': 'Explain this section again', 'activity_id': guide['id']})
        self.assertTrue(reply.json()['context']['stale'])
        self.assertEqual(reply.json()['revision'], 2)
        self.assertEqual(len(self.client.get(self.prefix + '/chat').json()), 2)

    def test_chat_context_isolation_and_no_hidden_rubric(self):
        self.upload()
        question = self.question()
        self.client.post(self.prefix + '/chat', json={'message': 'Help me understand this scenario', 'activity_id': question['id']})
        context = json.loads(self.coach.instruction)['learning_context']
        self.assertNotIn('criteria', context)
        self.assertNotIn('Requires sorted input.', context['content'])
        other = self.client.post('/journeys', json={'goal': 'exam', 'subject': 'Another journey'}).json()
        result = self.client.post(f'/journeys/{other["id"]}/chat', json={'message': 'Read this scenario', 'activity_id': question['id']})
        self.assertEqual(result.status_code, 404)

    def test_expired_session_and_forged_source_quote(self):
        engine, sessions = create_database(self.settings.database_url)
        with sessions() as db:
            db.query(LoginSession).update({LoginSession.expires_at: time.time() - 1})
            db.commit()
        self.assertEqual(self.client.get('/auth/me').status_code, 401)
        self.client.post('/auth/login', json={'email': 'ada@example.com', 'password': PASSWORD})
        self.upload()
        original = self.coach.generate
        def forged(instruction, evidence):
            result = original(instruction, evidence)
            if 'Build a learning plan' in instruction:
                result['concerns'] = [{'source_claim': 'A quote absent from the material', 'alternative': 'Something else', 'reason': 'A concern', 'citations': result['citations']}]
            return result
        self.coach.generate = forged
        self.assertEqual(self.client.post(self.prefix + '/plan').status_code, 200)
        self.assertEqual(self.client.get(self.prefix + '/reviews').json(), [])
        engine.dispose()

    def test_legacy_import_keeps_existing_records(self):
        engine, sessions = create_database(self.settings.database_url)
        with sessions() as db:
            legacy = Journey(goal='exam', subject='Legacy learning', access_token='legacy-private-token')
            db.add(legacy)
            db.flush()
            old_id = legacy.id
            db.add(Document(journey_id=old_id, name='old notes', passages=[{'page': 1, 'text': 'Existing notes.'}]))
            db.commit()
        self.assertEqual(self.client.get(f'/journeys/{old_id}/documents').status_code, 404)
        self.assertEqual(self.client.post('/journeys/claim', json={'journey_id': old_id, 'access_token': 'wrong'}).status_code, 404)
        result = self.client.post('/journeys/claim', json={'journey_id': old_id, 'access_token': 'legacy-private-token'})
        self.assertEqual(result.status_code, 200)
        self.assertNotIn('access_token', result.json())
        self.assertEqual(self.client.get(f'/journeys/{old_id}/documents').json()[0]['name'], 'old notes')
        self.assertEqual(self.client.post('/journeys/claim', json={'journey_id': old_id, 'access_token': 'legacy-private-token'}).status_code, 404)
        engine.dispose()
