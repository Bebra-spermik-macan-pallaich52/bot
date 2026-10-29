from sqlmodel import SQLModel, create_engine
from app.core.config import DATABASE_URL
import app.models


engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True, pool_recycle=3600)

def init_db():
    SQLModel.metadata.create_all(engine)

def close_db():
    engine.dispose()