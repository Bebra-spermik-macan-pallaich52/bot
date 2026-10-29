from sqlmodel import Session
from app.db.database import engine


def get_session():
    with Session(engine) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
