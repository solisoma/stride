"""Explicit local bootstrap; no default password or public admin registration."""
import argparse
from getpass import getpass
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from api.schemas.learning import Registration
from api.services.auth_service import hash_password
from core.config import Settings
from db.models import Base, User, AdminRole
from db.session import create_database


def create_admin(db, name, email, password):
    registration = Registration(name=name, email=email, password=password)
    if not registration.name.strip():
        raise ValueError('Name is required')
    if db.query(User).filter_by(email=registration.email).first():
        raise ValueError('This email already has an account. Use a separate admin email; existing passwords are never overwritten.')
    user = User(name=registration.name.strip(), email=registration.email, password_hash=hash_password(registration.password))
    db.add(user)
    try:
        db.flush()
        db.add(AdminRole(user_id=user.id))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError('An account with this email already exists')
    return user


def main():
    parser = argparse.ArgumentParser(description='Create a Stride administrator. Password is entered privately.')
    parser.add_argument('--email')
    parser.add_argument('--name', default='Administrator')
    args = parser.parse_args()
    email = args.email or input('Admin email: ').strip()
    password = getpass('Admin password (at least 15 characters): ')
    if password != getpass('Confirm password: '):
        parser.exit(1, 'Passwords do not match. No account created.\n')
    settings = Settings.load()
    engine, sessions = create_database(settings.database_url)
    try:
        Base.metadata.create_all(engine)
        with sessions() as db:
            try:
                create_admin(db, args.name, email, password)
            except ValidationError:
                parser.exit(1, 'Enter a valid email, a nonempty name, and a password with 15–128 characters.\n')
            except ValueError as exc:
                parser.exit(1, f'{exc}\n')
        print('Admin account created. Choose Admin sign in on the login page.')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
