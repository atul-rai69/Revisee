import json
import os
from collections.abc import Generator
from pathlib import Path
import pytest
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


INTEGRATION_SKIP_REASON = (
    "integration tests require --run-integration and a safe TEST_DATABASE_URL"
)
MIGRATION_SKIP_REASON = (
    "migration tests additionally require --run-migration-tests and a safe "
    "MIGRATION_TEST_DATABASE_URL"
)


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run tests that require the dedicated PostgreSQL test database",
    )
    parser.addoption(
        "--run-migration-tests",
        action="store_true",
        default=False,
        help="run destructive tests against the separate migration-test database",
    )


def pytest_configure(config) -> None:
    config.addinivalue_line("markers", "unit: database-independent unit test")
    config.addinivalue_line(
        "markers",
        "integration: requires the dedicated PostgreSQL test database",
    )
    config.addinivalue_line(
        "markers",
        "migration: destructively exercises the separate migration-test database",
    )
    if config.getoption("--run-migration-tests") and not config.getoption(
        "--run-integration"
    ):
        raise pytest.UsageError(
            "--run-migration-tests also requires --run-integration"
        )
    if config.getoption("--run-integration"):
        _configure_integration_environment()
    if config.getoption("--run-migration-tests"):
        _validated_migration_test_database_url()


def pytest_collection_modifyitems(config, items) -> None:
    run_integration = config.getoption("--run-integration")
    run_migration = config.getoption("--run-migration-tests")
    skip_integration = pytest.mark.skip(reason=INTEGRATION_SKIP_REASON)
    skip_migration = pytest.mark.skip(reason=MIGRATION_SKIP_REASON)
    for item in items:
        is_migration = "migration" in item.keywords
        if "integration" in Path(str(item.path)).parts:
            item.add_marker(pytest.mark.integration)
            if is_migration and not run_migration:
                item.add_marker(skip_migration)
            elif not run_integration:
                item.add_marker(skip_integration)
        else:
            item.add_marker(pytest.mark.unit)


def _validated_test_database_url() -> str:
    test_database_url = os.environ.get("TEST_DATABASE_URL")
    if not test_database_url:
        raise pytest.UsageError(
            "--run-integration requires TEST_DATABASE_URL; no fallback is allowed"
        )

    parsed_test_url = _validated_postgresql_url(
        test_database_url,
        variable_name="TEST_DATABASE_URL",
        required_name_parts=("test",),
    )

    backend_env = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
    normal_database_url = os.environ.get("DATABASE_URL") or backend_env.get(
        "DATABASE_URL"
    )
    if normal_database_url:
        try:
            parsed_normal_url = make_url(str(normal_database_url))
            same_as_normal = _database_identity(parsed_test_url) == (
                _database_identity(parsed_normal_url)
            )
        except ArgumentError:
            same_as_normal = test_database_url == normal_database_url
        if same_as_normal:
            raise pytest.UsageError("TEST_DATABASE_URL must not equal DATABASE_URL")
    return test_database_url


def _validated_migration_test_database_url() -> str:
    migration_database_url = os.environ.get("MIGRATION_TEST_DATABASE_URL")
    if not migration_database_url:
        raise pytest.UsageError(
            "--run-migration-tests requires MIGRATION_TEST_DATABASE_URL; "
            "no fallback is allowed"
        )

    parsed_migration_url = _validated_postgresql_url(
        migration_database_url,
        variable_name="MIGRATION_TEST_DATABASE_URL",
        required_name_parts=("test", "migration"),
    )
    integration_database_url = _validated_test_database_url()
    parsed_integration_url = make_url(integration_database_url)
    if _database_identity(parsed_migration_url) == _database_identity(
        parsed_integration_url
    ):
        raise pytest.UsageError(
            "MIGRATION_TEST_DATABASE_URL must target a different database "
            "from TEST_DATABASE_URL"
        )

    backend_env = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
    normal_database_url = os.environ.get("DATABASE_URL") or backend_env.get(
        "DATABASE_URL"
    )
    if normal_database_url:
        try:
            parsed_normal_url = make_url(str(normal_database_url))
            same_as_normal = _database_identity(parsed_migration_url) == (
                _database_identity(parsed_normal_url)
            )
        except ArgumentError:
            same_as_normal = migration_database_url == normal_database_url
        if same_as_normal:
            raise pytest.UsageError(
                "MIGRATION_TEST_DATABASE_URL must not equal DATABASE_URL"
            )
    return migration_database_url


def _validated_postgresql_url(
    value: str,
    *,
    variable_name: str,
    required_name_parts: tuple[str, ...],
):
    try:
        parsed = make_url(value)
    except ArgumentError as exc:
        raise pytest.UsageError(f"{variable_name} is not a valid database URL") from exc
    if not parsed.drivername.startswith("postgresql"):
        raise pytest.UsageError(f"{variable_name} must use PostgreSQL")
    database_name = (parsed.database or "").casefold()
    if not database_name or any(part not in database_name for part in required_name_parts):
        expected = " and ".join(repr(part) for part in required_name_parts)
        raise pytest.UsageError(
            f"{variable_name} database name must clearly contain {expected}"
        )
    return parsed


def _database_identity(parsed_url) -> tuple[str, int, str]:
    host = (parsed_url.host or "").casefold().rstrip(".")
    if host in {"localhost", "127.0.0.1", "::1"}:
        host = "loopback"
    return (
        host,
        parsed_url.port or 5432,
        (parsed_url.database or "").casefold(),
    )


def _configure_integration_environment() -> None:
    _validated_test_database_url()
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
def test_database_url() -> str:
    return _validated_test_database_url()


@pytest.fixture(scope="session")
def migration_test_database_url() -> str:
    return _validated_migration_test_database_url()


@pytest.fixture(scope="session")
def migrated_database(test_database_url: str) -> Generator[None, None, None]:
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
