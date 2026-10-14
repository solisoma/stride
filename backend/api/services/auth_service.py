import hashlib
import secrets
import time
from collections import defaultdict
from threading import Lock
from fastapi import HTTPException
from db.models import LoginSession, User, AdminRole

COOKIE = 'learnforward_session'
LIFETIME = 7 * 24 * 3600


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=5, dklen=32).hex()
    return f'{salt}:{digest}'


def verify_password(password, stored):
    salt, _ = stored.split(':', 1)
    return secrets.compare_digest(hash_password(password, salt), stored)


DUMMY_HASH = hash_password('a dummy password for timing equality')


def session_user(db, token):
    if not token:
        raise HTTPException(401, 'Please sign in')
    session = db.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
    if not session or session.expires_at <= time.time():
        raise HTTPException(401, 'Session expired. Please sign in')
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(401, 'Please sign in')
    return user


def start_session(db, user, response, secure=False):
    token = secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id, expires_at=time.time() + LIFETIME))
    db.commit()
    response.set_cookie(COOKIE, token, httponly=True, samesite='lax', secure=secure, max_age=LIFETIME, path='/')


def is_admin(db, user):
    return db.get(AdminRole, user.id) is not None


def require_admin(db, user):
    if not is_admin(db, user):
        raise HTTPException(403, 'Administrator access required')
    return user


def public_user(user, db):
    return {'id': user.id, 'name': user.name, 'email': user.email, 'role': 'admin' if is_admin(db, user) else 'learner'}


class AuthLimiter:
    """Bounded per-process login throttling; use shared limits when scaling."""
    def __init__(self):
        self.entries = defaultdict(list)
        self.lock = Lock()

    def check(self, key):
        now = time.time()
        with self.lock:
            if len(self.entries) > 10000:
                self.entries = defaultdict(list, {k: v for k, v in self.entries.items() if v and v[-1] > now - 300})
            attempts = [t for t in self.entries[key] if t > now - 300]
            if len(attempts) >= 20:
                raise HTTPException(429, 'Too many sign-in attempts. Try again in five minutes.')
            self.entries[key] = attempts + [now]
