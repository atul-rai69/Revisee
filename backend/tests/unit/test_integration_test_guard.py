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


def test_migration_database_guard_never_falls_back(monkeypatch) -> None:
    monkeypatch.delenv("MIGRATION_TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://tester:secret@localhost/revisee_test",
    )
    with pytest.raises(pytest.UsageError, match="no fallback"):
        conftest._validated_migration_test_database_url()


def test_migration_database_requires_explicit_migration_test_name(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://tester:secret@localhost/revisee_test",
    )
    monkeypatch.setenv(
        "MIGRATION_TEST_DATABASE_URL",
        "postgresql+psycopg://tester:secret@localhost/revisee_test_other",
    )
    with pytest.raises(pytest.UsageError, match="'test' and 'migration'"):
        conftest._validated_migration_test_database_url()


def test_migration_and_integration_targets_must_differ_after_normalization(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://integration:one@localhost/revisee_migration_test",
    )
    monkeypatch.setenv(
        "MIGRATION_TEST_DATABASE_URL",
        "postgresql://migration:two@127.0.0.1/revisee_migration_test",
    )
    with pytest.raises(pytest.UsageError, match="different database"):
        conftest._validated_migration_test_database_url()


def test_migration_target_must_not_match_normal_database(monkeypatch) -> None:
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://integration:one@localhost/revisee_test",
    )
    monkeypatch.setenv(
        "MIGRATION_TEST_DATABASE_URL",
        "postgresql+psycopg://migration:two@localhost/revisee_migration_test",
    )
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://normal:three@127.0.0.1/revisee_migration_test",
    )
    with pytest.raises(pytest.UsageError, match="must not equal"):
        conftest._validated_migration_test_database_url()
