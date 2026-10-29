"""Только PostgreSQL с именем БД, оканчивающимся на _test."""
import os

import pytest
from sqlalchemy.engine import make_url
from sqlmodel import Session
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def application():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.fail("Задайте TEST_DATABASE_URL для отдельной PostgreSQL с именем *_test", pytrace=False)
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or not (parsed.database or "").endswith("_test"):
        pytest.fail("Тестам разрешена только PostgreSQL с именем БД *_test", pytrace=False)
    # Импорт после установки URL: рабочий DATABASE_URL из .env не используется.
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DATABASE_URL", url)
        from app.main import main_app, app_v1
        from app.db.database import engine
        from app.db.session import get_session
        with TestClient(main_app) as lifecycle:
            yield main_app, app_v1, engine, get_session


@pytest.fixture
def api(application):
    main_app, app_v1, engine, get_session = application
    # Контроллер может делать commit, но внешний transaction откатывает весь тест.
    with engine.connect() as connection:
        transaction = connection.begin()

        def test_session():
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                try:
                    yield session
                except Exception:
                    session.rollback()
                    raise

        app_v1.dependency_overrides[get_session] = test_session
        try:
            with TestClient(main_app, base_url="http://testserver") as client:
                yield client, connection
        finally:
            app_v1.dependency_overrides.pop(get_session, None)
            if transaction.is_active:
                transaction.rollback()


@pytest.fixture
def client(api):
    return api[0]
