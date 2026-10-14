from sqlalchemy import or_
from db.models import Document, DocumentIngestion


def ready_documents(db, journey_id):
    return db.query(Document).outerjoin(DocumentIngestion, Document.id == DocumentIngestion.document_id).filter(
        Document.journey_id == journey_id,
        or_(DocumentIngestion.document_id.is_(None), DocumentIngestion.status == 'ready'),
    ).order_by(Document.id).all()


def material_payload(db, document):
    job = db.get(DocumentIngestion, document.id)
    return {'id': document.id, 'name': document.name, 'passages': len(document.passages),
            'status': job.status if job else 'ready', 'progress': job.progress if job else 'Ready',
            'error': job.error if job else '', 'reference': job.request_reference if job else '',
            'plan_error': job.plan_error if job else '', 'plan_pending': job.plan_pending if job else False}
