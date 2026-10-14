"""RabbitMQ delivery with a transactional SQL outbox and confirmed publishing."""
import json
import time
import uuid
from db.models import IngestionMessage, DocumentIngestion
from utils.observability import get_logger

QUEUE = 'learnforward.ingestion.v1'
RETRY_QUEUE = QUEUE + '.retry'


def enqueue(db, document_id, delayed=False):
    db.add(IngestionMessage(id=str(uuid.uuid4()), document_id=document_id,
                            delayed=delayed, created_at=time.time()))


def connect(settings):
    import pika
    parameters = pika.URLParameters(settings.rabbitmq_url)
    parameters.heartbeat = 60
    parameters.socket_timeout = 5
    parameters.blocked_connection_timeout = 10
    return pika.BlockingConnection(parameters)


def declare(channel):
    channel.queue_declare(queue=QUEUE, durable=True)
    channel.queue_declare(queue=RETRY_QUEUE, durable=True, arguments={
        'x-message-ttl': 30000, 'x-dead-letter-exchange': '',
        'x-dead-letter-routing-key': QUEUE,
    })


def publish_pending(settings, sessions, connection_factory=connect):
    """Delete an outbox row only after RabbitMQ confirms its persistent message."""
    import pika
    with sessions() as db:
        rows = db.query(IngestionMessage).order_by(IngestionMessage.created_at).limit(100).all()
        if not rows:
            return 0
        connection = connection_factory(settings)
        try:
            channel = connection.channel()
            declare(channel)
            channel.confirm_delivery()
            for row in rows:
                channel.basic_publish(exchange='', routing_key=RETRY_QUEUE if row.delayed else QUEUE,
                    body=json.dumps({'version': 1, 'document_id': row.document_id}), mandatory=True,
                    properties=pika.BasicProperties(delivery_mode=2, content_type='application/json', message_id=row.id))
                db.delete(row)
                db.commit()
            return len(rows)
        finally:
            connection.close()


def after_processing(settings, sessions, document_id):
    """Failure is persisted first; bounded retries are published through the outbox."""
    with sessions() as db:
        job = db.get(DocumentIngestion, document_id)
        if job is None or job.status == 'ready':
            return True
        if job.status == 'failed' and job.attempts < settings.ingestion_max_attempts:
            job.status, job.progress, job.error = 'queued', 'Waiting to retry processing', ''
            enqueue(db, document_id, delayed=True)
            db.commit()
            get_logger('ingestion').info('ingestion_retry_scheduled', extra={'fields': {
                'document_id': document_id, 'attempt': job.attempts}})
        # Failed jobs have reached the limit. Queued jobs already have a retry message.
        return job.status in {'failed', 'queued'}


def parse_message(body):
    data = json.loads(body)
    if not isinstance(data, dict) or data.get('version') != 1:
        raise ValueError('Unsupported ingestion message')
    document_id = data.get('document_id')
    if type(document_id) is not int or document_id < 1:
        raise ValueError('Invalid document identifier')
    return document_id
