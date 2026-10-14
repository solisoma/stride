import tempfile
import unittest
import io
from contextlib import redirect_stderr
from unittest.mock import patch
from pathlib import Path
from fastapi.testclient import TestClient
from api.main import create_app
from core.config import Settings
from db.models import User, AdminRole
from db.session import create_database
from scripts.create_admin import create_admin
from scripts.create_admin import main as admin_cli


class AdminTests(unittest.TestCase):
    def test_cli_does_not_print_invalid_password(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(f'sqlite:///{Path(directory) / "test.db"}', Path(directory), '', None, '')
            output = io.StringIO()
            with patch('sys.argv', ['create_admin', '--email', 'learnforward@gmail.com']), patch('scripts.create_admin.getpass', side_effect=['secret', 'secret']), patch('scripts.create_admin.Settings.load', return_value=settings), redirect_stderr(output):
                with self.assertRaises(SystemExit):
                    admin_cli()
            self.assertNotIn('secret', output.getvalue())

    def test_admin_login_role_isolation_and_duplicate_bootstrap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(f'sqlite:///{root / "test.db"}', root / 'uploads', '', None, '')
            app = create_app(settings)
            with TestClient(app) as client:
                client.headers['X-Stride-Request'] = '1'
                engine, sessions = create_database(settings.database_url)
                with sessions() as db:
                    admin = create_admin(db, 'Administrator', 'learnforward@gmail.com', 'a private long admin password')
                    self.assertIsNotNone(db.get(AdminRole, admin.id))
                    self.assertNotEqual(admin.password_hash, 'a private long admin password')
                    with self.assertRaises(ValueError):
                        create_admin(db, 'Administrator', 'learnforward@gmail.com', 'a different long password')
                    self.assertEqual(db.query(User).count(), 1)
                denied = client.post('/auth/admin/login', json={'email': 'learnforward@gmail.com', 'password': 'wrong'})
                self.assertEqual(denied.status_code, 401)
                self.assertEqual(client.get('/admin/me').status_code, 401)
                login = client.post('/auth/admin/login', json={'email': 'learnforward@gmail.com', 'password': 'a private long admin password'})
                self.assertEqual(login.status_code, 200)
                self.assertEqual(login.json()['role'], 'admin')
                self.assertIn('HttpOnly', login.headers['set-cookie'])
                self.assertEqual(client.get('/admin/me').status_code, 200)
                self.assertEqual(client.get('/auth/me').json()['role'], 'admin')
                client.post('/auth/logout')
                registration = client.post('/auth/register', json={'name': 'Learner', 'email': 'learner@example.com', 'password': 'a private long learner password', 'role': 'admin'})
                self.assertEqual(registration.json()['role'], 'learner')
                self.assertEqual(client.get('/admin/me').status_code, 403)
                client.post('/auth/logout')
                self.assertEqual(client.post('/auth/admin/login', json={'email': 'learner@example.com', 'password': 'a private long learner password'}).status_code, 401)
                self.assertEqual(client.get('/auth/me').status_code, 401)
                engine.dispose()
