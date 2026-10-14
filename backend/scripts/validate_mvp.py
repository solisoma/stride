"""Real-PDF MVP verification using the actual backend and a separate validation DB."""
import argparse
import hashlib
import json
import time
import threading
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from core.config import Settings
from api.main import create_app
from api.services.ingestion_jobs import process_next
from db.session import create_database
from db.models import Document, DocumentTree, DocumentIngestion
from pipeline.utils.parsers.extractors import extract_pdf_pages
from providers.pipeline_client import create_pipeline_client


def verify_tree(tree, extracted, fanout):
    nodes, leaves = [], []
    def visit(node, depth=0):
        nodes.append((node, depth))
        assert node['header'].strip(), 'Empty heading'
        assert node['summary'].strip(), 'Empty summary'
        assert len(node['children']) <= fanout, 'Fanout violation'
        if node['children']:
            assert node['content'] is None, 'Parent also holds source content'
            for child in node['children']:
                visit(child, depth + 1)
        else:
            assert isinstance(node['content'], str) and node['content'].strip(), 'Empty source leaf'
            leaves.append(node)
    visit(tree)
    coverage = []
    for page in extracted:
        text = page['text']
        used = set()
        for leaf in [n for n in leaves if n['metadata'].get('page', n['page_number']) == page['page']]:
            position = text.find(leaf['content'])
            while position >= 0 and used.intersection(range(position, position + len(leaf['content']))):
                position = text.find(leaf['content'], position + 1)
            assert position >= 0, f'Changed or duplicated source content on page {page["page"]}'
            used.update(range(position, position + len(leaf['content'])))
        missing = [i for i, char in enumerate(text) if not char.isspace() and i not in used]
        assert not missing, f'Missing source text on page {page["page"]}'
        coverage.append({'page': page['page'], 'characters': len(text), 'complete': True})
    assert {n['metadata'].get('page', n['page_number']) for n in leaves} == {p['page'] for p in extracted}
    return {'nodes': len(nodes), 'leaves': len(leaves), 'depth': max(d for _, d in nodes),
            'coverage': coverage, 'root_children': [n['header'] for n in tree['children']]}


def run(source, ingestion_only=False, reprocess=False, subject='Erran business model and operations', goal='new_field', document_name=None):
    source = Path(source).resolve()
    assert source.is_file() and source.suffix.lower() == '.pdf'
    settings = Settings.load()
    key = hashlib.sha256(source.read_bytes()).hexdigest()
    output = Path(__file__).resolve().parents[1] / '.mvp-validation' / key
    output.mkdir(parents=True, exist_ok=True)
    settings.database_url = f'sqlite:///{output / "validation.db"}'
    settings.storage = output / 'uploads'
    settings.log_dir = output / 'logs'
    settings.session_secure = False
    metrics = {'requests': 0, 'tokens': 0}
    lock = threading.Lock()
    pipeline = create_pipeline_client(settings)
    for name in ('parse', 'create'):
        original = getattr(pipeline.chat.completions, name)
        def measured(*args, _original=original, **kwargs):
            response = _original(*args, **kwargs)
            with lock:
                metrics['requests'] += 1
                if response.usage:
                    metrics['tokens'] += response.usage.total_tokens
            return response
        setattr(pipeline.chat.completions, name, measured)
    report = {'pdf': source.name, 'model': settings.model, 'checks': {}, 'pipeline_usage': metrics}
    engine, sessions = create_database(settings.database_url)
    def save():
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    try:
        with TestClient(create_app(settings, pipeline_client=pipeline)) as client:
            client.headers['X-Stride-Request'] = '1'
            def request(method, path, **kwargs):
                response = getattr(client, method)(path, **kwargs)
                if not 200 <= response.status_code < 300:
                    report['failure'] = {'endpoint': path, 'status': response.status_code, 'response': response.json()}
                    save()
                    raise AssertionError(f'{path}: HTTP {response.status_code}; inspect validation report')
                return response.json()
            credentials = {'email': 'validation@stride.invalid', 'password': f'validation-only-{key}'}
            login = client.post('/auth/login', json=credentials)
            if login.status_code != 200:
                request('post', '/auth/register', json={'name': 'MVP Validation', **credentials})
            journeys = request('get', '/journeys')
            journey = journeys[0] if journeys else request('post', '/journeys', json={'goal': goal, 'subject': subject})
            prefix = f'/journeys/{journey["id"]}'
            documents = request('get', prefix + '/documents')
            if not documents:
                document = request('post', prefix + '/documents', files={'file': (document_name or source.name, source.read_bytes(), 'application/pdf')})
                assert document['status'] == 'queued'
            else:
                document = documents[0]
                if document['status'] == 'failed':
                    request('post', prefix + f'/documents/{document["id"]}/retry', json={})
            if reprocess:
                with sessions() as db:
                    job = db.get(DocumentIngestion, document['id'])
                    assert job is not None
                    job.status = 'queued'
                    db.commit()
                document['status'] = 'queued'
            # Keep verification metadata aligned with the chosen PDF on resumed runs.
            from db.models import Journey
            with sessions() as db:
                saved_journey = db.get(Journey, journey['id'])
                saved_document = db.get(Document, document['id'])
                assert saved_journey is not None and saved_document is not None
                saved_journey.subject, saved_journey.goal = subject, goal
                saved_document.name = document_name or source.name
                saved_tree = db.get(DocumentTree, document['id'])
                if saved_tree is not None:
                    saved_tree.tree_data = {**saved_tree.tree_data, 'header': saved_document.name}
                db.commit()
            def captured(*args, **kwargs):
                pages = extract_pdf_pages(*args, **kwargs)
                (output / 'extraction.json').write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding='utf-8')
                return pages
            started = time.perf_counter()
            if document['status'] != 'ready':
                with patch('pipeline.ingestor.extract_pdf_pages', side_effect=captured):
                    process_next(settings, pipeline_client=pipeline, document_id=document['id'])
            with sessions() as db:
                job = db.get(DocumentIngestion, document['id'])
                assert job and job.status == 'ready', f'Ingestion failed: {job.error if job else "missing job"}'
                stored = db.get(DocumentTree, document['id'])
                assert stored is not None
                tree = stored.tree_data
                stored_document = db.get(Document, document['id'])
                assert stored_document is not None
                passages = stored_document.passages
            extracted = json.loads((output / 'extraction.json').read_text(encoding='utf-8'))
            report['tree'] = verify_tree(tree, extracted, settings.tree_fanout)
            report['ingestion_seconds'] = round(time.perf_counter() - started, 2)
            report['checks']['source_coverage_and_tree'] = True
            (output / 'tree.json').write_text(json.dumps(tree, ensure_ascii=False, indent=2), encoding='utf-8')
            (output / 'passages.json').write_text(json.dumps(passages, ensure_ascii=False, indent=2), encoding='utf-8')
            save()
            print('INGESTION VERIFIED', json.dumps(report['tree']), flush=True)
            if ingestion_only:
                return output
            plan = request('post', prefix + '/plan', json={})
            assert plan['topics'], 'No plan topics'
            report['checks']['plan'] = True
            topic = plan['topics'][0]['title']
            guide = request('post', prefix + '/guides', json={'topic': topic})
            assert guide['content'].strip() and guide['citations']
            report['checks']['guide'] = True
            question = request('post', prefix + '/questions', json={'topic': topic, 'format': 'typed'})
            assert question['prompt'].strip() and 'criteria' not in question
            report['checks']['scenario_question'] = True
            feedback = request('post', prefix + f'/questions/{question["id"]}/answers', json={'answer': 'I do not know. My guess is that none of the described processes are necessary.'})
            assert feedback['explanation'].strip() and feedback['next_step'].strip()
            report['feedback_verdict'] = feedback['verdict']
            report['checks']['detailed_feedback'] = True
            chat = request('post', prefix + '/chat', json={'message': 'Explain the main concept with an example grounded in this material.', 'activity_id': guide['id']})
            assert chat['content'].strip() and chat['citations']
            report['checks']['contextual_chat'] = True
            progress = request('get', prefix + '/progress')
            assert any(a['id'] == feedback['id'] for a in progress['attempts'])
            request('post', '/auth/logout')
            request('post', '/auth/login', json=credentials)
            progress = request('get', prefix + '/progress')
            assert any(a['id'] == feedback['id'] for a in progress['attempts'])
            assert request('get', prefix + '/chat')
            report['checks']['progress_and_chat_survive_login'] = True
            save()
            print('MVP VERIFIED', str(output), flush=True)
            return output
    finally:
        save()
        engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--ingestion-only', action='store_true')
    parser.add_argument('--reprocess', action='store_true')
    parser.add_argument('--subject', default='Erran business model and operations')
    parser.add_argument('--goal', choices=['exam', 'technical_interview', 'new_field'], default='new_field')
    parser.add_argument('--document-name')
    args = parser.parse_args()
    run(args.pdf, args.ingestion_only, args.reprocess, args.subject, args.goal, args.document_name)
