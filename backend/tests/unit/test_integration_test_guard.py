import pytest

import conftest


def test_database_guard_never_falls_back(monkeypatch) -> None:
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://normal:secret@localhost/revisee_development",
    )
    with pytest.raises(pytest.UsageError, match="no fallback"):
        conftest._validated_test_database_url()


def test_database_guard_requires_postgresql_and_test_name(monkeypatch) -> None:
    monkeypatch.setenv("TEST_DATABASE_URL", "sqlite:///revisee_test.db")
    with pytest.raises(pytest.UsageError, match="PostgreSQL"):
        conftest._validated_test_database_url()

    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://tester:secret@localhost/revisee_development",
    )
    with pytest.raises(pytest.UsageError, match="contain 'test'"):
        conftest._validated_test_database_url()


def test_database_guard_rejects_same_target_with_different_driver(monkeypatch) -> None:
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://tester:one@localhost/revisee_test",
    )
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://owner:two@localhost/revisee_test",
    )
    with pytest.raises(pytest.UsageError, match="must not equal"):
        conftest._validated_test_database_url()
