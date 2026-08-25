import json
import os
from collections.abc import Generator
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from dotenv import dotenv_values


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise pytest.UsageError("TEST_DATABASE_URL is required; no database fallback is allowed")

database_name = urlsplit(TEST_DATABASE_URL).path.rsplit("/", 1)[-1]
if "test" not in database_name.lower():
    raise pytest.UsageError("TEST_DATABASE_URL database name must contain 'test'")

backend_env = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
normal_database_url = os.environ.get("DATABASE_URL") or backend_env.get("DATABASE_URL")
if normal_database_url and TEST_DATABASE_URL == normal_database_url:
    raise pytest.UsageError("TEST_DATABASE_URL must not equal DATABASE_URL")

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test-only-secret-key-that-is-never-used-outside-tests"
os.environ["GOOGLE_API_KEY"] = "test-google-key"
os.environ["CLOUDINARY_CLOUD_NAME"] = "test-cloud"
os.environ["CLOUDINARY_API_KEY"] = "test-cloudinary-key"
os.environ["CLOUDINARY_API_SECRET"] = "test-cloudinary-secret"


class FakeAIProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.raw_response = json.dumps(
            {
                "theory": "Generated theory",
                "key_points": ["Point one", "Point two"],
                "questions": [
                    {
                        "question": "Question?",
                        "options": ["A1", "B1", "C1", "D1"],
                        "correct_answer": 1,
                        "explanation": "Because B1 is correct",
                        "expected_time": 30,
                        "difficulty_level": 2,
                    }
                ],
            }
        )

    def generate(self, _prompt: str) -> str:
        self.calls += 1
        return self.raw_response


class FakeStorageProvider:
    def __init__(self) -> None:
        self.uploads: list[object] = []
        self.deletes: list[tuple[str, str]] = []
        self.fail_on_upload_number: int | None = None

    def upload(self, file: object, resource_type: str):
        from src.core.exceptions import ProviderUnavailableError
        from src.integrations.storage.base import UploadedAsset

        next_number = len(self.uploads) + 1
        if self.fail_on_upload_number == next_number:
            raise ProviderUnavailableError("Synthetic storage failure")
        self.uploads.append(file)
        number = len(self.uploads)
        return UploadedAsset(
            url=f"https://storage.test/{number}",
            public_id=f"test-{number}",
            resource_type=resource_type,
        )

    def delete(self, public_id: str, resource_type: str) -> None:
        self.deletes.append((public_id, resource_type))


@pytest.fixture(scope="session")
def migrated_database() -> Generator[None, None, None]:
    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    command.upgrade(config, "head")
    from src.db.base import Base
    from src.db.session import engine
    import src.db.models  # noqa: F401

    def clean_tables() -> None:
        with engine.begin() as connection:
            for table in reversed(Base.metadata.sorted_tables):
                connection.execute(table.delete())

    clean_tables()
    try:
        yield
    finally:
        clean_tables()


@pytest.fixture
def db_session(migrated_database):
    from sqlalchemy.orm import Session

    from src.db.session import engine

    connection = engine.connect()
    outer_transaction = connection.begin()
    session = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()


@pytest.fixture
def fake_ai() -> FakeAIProvider:
    return FakeAIProvider()


@pytest.fixture
def fake_storage() -> FakeStorageProvider:
    return FakeStorageProvider()


@pytest.fixture
def client(db_session, fake_ai, fake_storage):
    from fastapi.testclient import TestClient

    from src.api.dependencies import get_ai_provider, get_storage_provider
    from src.db.session import get_db
    from src.main import app

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_storage_provider] = lambda: fake_storage
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def registered_user(client):
    response = client.post(
        "/register",
        params={
            "username": "atul",
            "email": "atul@example.test",
            "password": "safe-password",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    return {
        "username": "atul",
        "password": "safe-password",
        "token": payload["access_token"],
        "headers": {"Authorization": f"Bearer {payload['access_token']}"},
    }
