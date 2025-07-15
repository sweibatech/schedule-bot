from contextlib import contextmanager
from db_setup import SessionLocal

@contextmanager
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()