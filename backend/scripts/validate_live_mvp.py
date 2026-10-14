"""Exercise the running Docker API and RabbitMQ worker with a real uploaded PDF."""
import json
import secrets
import time
import uuid
from pathlib import Path
import httpx


def run():
    root = Path(__file__).resolve().parents[1]
    source = root / 'uploads' / '043e8b7f8bbe7e176bee6a5a2a439494.pdf'
    output = root / '.mvp-validation' / 'live'
    output.mkdir(parents=True, exist_ok=True)
    email = f'mvp-{uuid.uuid4().hex[:10]}@stride.invalid'
    password = secrets.token_urlsafe(24)
    (output / 'demo-login.json').write_text(json.dumps({'email': email, 'password': password}, indent=2))
    report = {'checks': {}, 'email': email}
    def save():
        (output / 'report.json').write_text(json.dumps(report, indent=2))
    with httpx.Client(base_url='http://127.0.0.1:8001', timeout=120,
                      headers={'X-Stride-Request': '1'}) as client:
        def request(method, path, **kwargs):
            response = getattr(client, method)(path, **kwargs)
            if not 200 <= response.status_code < 300:
                report['failure'] = {'endpoint': path, 'status': response.status_code, 'response': response.json()}
                save()
                raise RuntimeError(f'{path}: HTTP {response.status_code}')
            return response.json()
        request('post', '/auth/register', json={'name': 'Stride MVP Demo', 'email': email, 'password': password})
        journey = request('post', '/journeys', json={'goal': 'new_field', 'subject': 'Erran business model and operations'})
        report['journey_id'] = journey['id']
        prefix = f'/journeys/{journey["id"]}'
        document = request('post', prefix + '/documents', files={'file': ('Erran-business-summary.pdf', source.read_bytes(), 'application/pdf')})
        assert document['status'] == 'queued'
        report['document_id'] = document['id']
        deadline = time.monotonic() + 600
        previous = None
        while time.monotonic() < deadline:
            material = next(m for m in request('get', prefix + '/documents') if m['id'] == document['id'])
            progress = material.get('progress')
            if progress != previous:
                print(material['status'], progress, flush=True)
                previous = progress
            if material['status'] == 'failed':
                report['failure'] = {'stage': 'worker', 'message': material.get('error')}
                save()
                raise RuntimeError('Live ingestion failed')
            if material['status'] == 'ready' and not material.get('plan_pending'):
                break
            time.sleep(3)
        else:
            raise TimeoutError('Worker did not finish in ten minutes')
        assert material['passages'] > 0
        report['passages'] = material['passages']
        report['checks']['rabbitmq_ingestion'] = True
        save()
        plan = request('get', prefix + '/plan')
        if plan['status'] != 'ready':
            plan = request('post', prefix + '/plan', json={})
        assert plan['topics']
        report['checks']['plan'] = True
        topic = plan['topics'][0]['title']
        guide = request('post', prefix + '/guides', json={'topic': topic})
        assert guide['content'].strip() and guide['citations']
        report['checks']['guide'] = True
        question = request('post', prefix + '/questions', json={'topic': topic, 'format': 'typed'})
        assert question['prompt'].strip() and 'criteria' not in question
        report['checks']['practice'] = True
        feedback = request('post', prefix + f'/questions/{question["id"]}/answers', json={'answer': 'I do not know. My guess is that the platform runs its own warehouses and none of the described processes are needed.'})
        assert feedback['explanation'].strip() and feedback['next_step'].strip()
        report['checks']['feedback'] = True
        report['feedback_verdict'] = feedback['verdict']
        chat = request('post', prefix + '/chat', json={'message': 'Explain the main concept using an example grounded in this material.', 'activity_id': guide['id']})
        assert chat['content'].strip() and chat['citations']
        report['checks']['chat'] = True
        request('post', '/auth/logout')
        request('post', '/auth/login', json={'email': email, 'password': password})
        progress = request('get', prefix + '/progress')
        assert any(a['id'] == feedback['id'] for a in progress['attempts'])
        assert request('get', prefix + '/chat')
        report['checks']['saved_progress_after_login'] = True
        save()
        print('LIVE MVP VERIFIED', str(output), flush=True)


if __name__ == '__main__':
    run()
