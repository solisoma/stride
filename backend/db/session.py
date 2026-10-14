from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def create_database(database_url):
    engine = create_engine(database_url, connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {})
    return engine, sessionmaker(bind=engine)
