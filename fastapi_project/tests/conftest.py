"""HTTP tests: in-memory SQLite by default, or an isolated PostgreSQL test schema."""
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
TEST_URL = os.getenv("TEST_DATABASE_URL", "sqlite://")
url = make_url(TEST_URL)
if url.get_backend_name() != "sqlite" and not (url.database or "").endswith("_test"):
    raise RuntimeError("TEST_DATABASE_URL must point to a dedicated *_test database")
# Never use an existing application's DATABASE_URL for tests.
os.environ["DATABASE_URL"] = TEST_URL

import app.main as main
from app.database import get_session


@pytest.fixture
def api(monkeypatch):
    schema = None
    admin = None
    if url.get_backend_name() == "sqlite":
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    else:
        schema = "telecom_test_" + uuid4().hex
        admin = create_engine(TEST_URL)
        with admin.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        engine = create_engine(TEST_URL, connect_args={"options": f"-csearch_path={schema}"})

    def session_override():
        with Session(engine) as session:
            try:
                yield session
            except Exception:
                session.rollback()
                raise

    monkeypatch.setattr(main, "init_db", lambda: SQLModel.metadata.create_all(engine))
    monkeypatch.setattr(main, "close_db", engine.dispose)
    main.main_app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(main.main_app) as client:
            client.test_engine = engine
            yield client
    finally:
        main.main_app.dependency_overrides.clear()
        engine.dispose()
        if admin is not None:
            with admin.begin() as connection:
                connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
            admin.dispose()
