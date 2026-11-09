import os
from pathlib import Path

from dotenv import load_dotenv
from sqlmodel import Session, SQLModel, create_engine
import app.entities

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_FILE)
url = os.getenv("DATABASE_URL")
if not url:
    raise RuntimeError(f"Заполните DATABASE_URL в {ENV_FILE}. Скопируйте .env.example в .env и укажите данные PostgreSQL.")
engine = create_engine(url, pool_pre_ping=True)


def init_db():
    SQLModel.metadata.create_all(engine)


def close_db():
    engine.dispose()


def get_session():
    with Session(engine) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
