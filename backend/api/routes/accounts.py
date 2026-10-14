import hashlib
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError
from db.models import User, LoginSession, Journey, Ownership
from api.schemas.learning import Credentials, Registration, ClaimInput
from api.services.auth_service import COOKIE, DUMMY_HASH, AuthLimiter, hash_password, verify_password, start_session, public_user, is_admin, require_admin


def account_router(db_session, current_user, settings):
    router = APIRouter()
    limiter = AuthLimiter()

    @router.post('/auth/register', status_code=201)
    def register(body: Registration, request: Request, response: Response, db=Depends(db_session)):
        limiter.check(request.client.host if request.client else 'unknown')
        if not body.name.strip():
            raise HTTPException(422, 'Name is required')
        user = User(name=body.name.strip(), email=body.email, password_hash=hash_password(body.password))
        db.add(user)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, 'Unable to register this account. Try signing in.')
        start_session(db, user, response, settings.session_secure)
        return public_user(user, db)

    def authenticate(body, request, response, db, admin_only=False):
        limiter.check(request.client.host if request.client else 'unknown')
        user = db.query(User).filter_by(email=body.email).first()
        valid = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
        if not user or not valid or (admin_only and not is_admin(db, user)):
            raise HTTPException(401, 'Invalid email or password')
        start_session(db, user, response, settings.session_secure)
        return public_user(user, db)

    @router.post('/auth/login')
    def login(body: Credentials, request: Request, response: Response, db=Depends(db_session)):
        return authenticate(body, request, response, db)

    @router.post('/auth/admin/login')
    def admin_login(body: Credentials, request: Request, response: Response, db=Depends(db_session)):
        return authenticate(body, request, response, db, admin_only=True)

    @router.get('/admin/me')
    def admin_me(user=Depends(current_user), db=Depends(db_session)):
        require_admin(db, user)
        return public_user(user, db)

    @router.get('/auth/me')
    def me(user=Depends(current_user), db=Depends(db_session)):
        return public_user(user, db)

    @router.post('/auth/logout')
    def logout(request: Request, response: Response, db=Depends(db_session)):
        token = request.cookies.get(COOKIE)
        if token:
            db.query(LoginSession).filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest()).delete()
            db.commit()
        response.delete_cookie(COOKIE, path='/')
        return {'ok': True}

    @router.get('/journeys')
    def journeys(user=Depends(current_user), db=Depends(db_session)):
        return [{'id': j.id, 'goal': j.goal, 'subject': j.subject} for j in db.query(Journey).join(Ownership, Ownership.journey_id == Journey.id).filter(Ownership.user_id == user.id).order_by(Journey.id.desc()).all()]

    @router.post('/journeys/claim')
    def claim(body: ClaimInput, user=Depends(current_user), db=Depends(db_session)):
        journey = db.get(Journey, body.journey_id)
        if db.get(Ownership, body.journey_id) or not journey or not secrets.compare_digest(journey.access_token, body.access_token):
            raise HTTPException(404, 'Unclaimed journey not found')
        db.add(Ownership(journey_id=journey.id, user_id=user.id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, 'Journey already claimed')
        return {'id': journey.id, 'goal': journey.goal, 'subject': journey.subject}

    return router
