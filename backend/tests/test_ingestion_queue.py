import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from api.services.ingestion_queue import enqueue, publish_pending, parse_message, after_processing, QUEUE, RETRY_QUEUE
from db.models import Base, IngestionMessage, DocumentIngestion, Document, Journey
from db.session import create_database


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine, self.sessions = create_database(f'sqlite:///{Path(self.tmp.name) / "queue.db"}')
        Base.metadata.create_all(self.engine)
        self.settings = SimpleNamespace(ingestion_max_attempts=3)
        self.broker = Mock()
        self.channel = self.broker.channel.return_value
        with self.sessions() as db:
            journey = Journey(access_token='test-token', goal='exam', subject='Queues')
            db.add(journey); db.flush()
            document = Document(journey_id=journey.id, name='notes', passages=[])
            db.add(document); db.flush()
            self.document_id = document.id
            db.add(DocumentIngestion(document_id=document.id, file_path='notes.txt', source_hash='hash',
                                     status='failed', attempts=1, created_at=time.time(), updated_at=time.time()))
            db.commit()

    def tearDown(self):
        self.engine.dispose()
        self.tmp.cleanup()

    def test_outbox_is_transactional(self):
        with self.sessions() as db:
            enqueue(db, self.document_id)
            db.rollback()
            self.assertEqual(db.query(IngestionMessage).count(), 0)

    def test_confirmed_publish_removes_message_and_sends_only_identifier(self):
        with self.sessions() as db:
            enqueue(db, self.document_id); db.commit()
        self.assertEqual(publish_pending(self.settings, self.sessions, lambda _: self.broker), 1)
        self.channel.confirm_delivery.assert_called_once()
        sent = self.channel.basic_publish.call_args.kwargs
        self.assertEqual(sent['routing_key'], QUEUE)
        self.assertEqual(parse_message(sent['body']), self.document_id)
        self.assertEqual(sent['properties'].delivery_mode, 2)
        with self.sessions() as db:
            self.assertEqual(db.query(IngestionMessage).count(), 0)

    def test_publish_failure_retains_outbox(self):
        with self.sessions() as db:
            enqueue(db, self.document_id); db.commit()
        self.channel.basic_publish.side_effect = RuntimeError('broker unavailable')
        with self.assertRaises(RuntimeError):
            publish_pending(self.settings, self.sessions, lambda _: self.broker)
        with self.sessions() as db:
            self.assertEqual(db.query(IngestionMessage).count(), 1)

    def test_delayed_retry_is_durable_and_bounded(self):
        self.assertTrue(after_processing(self.settings, self.sessions, self.document_id))
        with self.sessions() as db:
            self.assertEqual(db.get(DocumentIngestion, self.document_id).status, 'queued')
            self.assertTrue(db.query(IngestionMessage).one().delayed)
        publish_pending(self.settings, self.sessions, lambda _: self.broker)
        self.assertEqual(self.channel.basic_publish.call_args.kwargs['routing_key'], RETRY_QUEUE)
        with self.sessions() as db:
            job = db.get(DocumentIngestion, self.document_id)
            job.status, job.attempts = 'failed', 3
            db.commit()
        after_processing(self.settings, self.sessions, self.document_id)
        with self.sessions() as db:
            self.assertEqual(db.query(IngestionMessage).count(), 0)
            self.assertEqual(db.get(DocumentIngestion, self.document_id).status, 'failed')

    def test_malformed_messages_are_rejected(self):
        for body in ('[]', '{}', '{"version":1,"document_id":true}', '{"version":1,"document_id":-1}'):
            with self.assertRaises(ValueError):
                parse_message(body)
