from sqlalchemy import delete, insert, select

from scripts.migrate_plaintext_passwords import run_migration
from src.core.security import hash_password, is_approved_password_hash
from src.modules.auth.models import User


def test_password_migration_is_dry_run_safe_and_idempotent(migrated_database) -> None:
    from src.core.config import get_settings
    from src.db.session import engine

    settings = get_settings()
    database_url = settings.active_database_url
    approved_hash = hash_password("already-safe")
    emails = ["migration-plain@example.test", "migration-hash@example.test"]

    try:
        with engine.begin() as connection:
            connection.execute(
                insert(User),
                [
                    {
                        "username": "migration-plain",
                        "email": emails[0],
                        "password_hash": "legacy-value",
                    },
                    {
                        "username": "migration-hash",
                        "email": emails[1],
                        "password_hash": approved_hash,
                    },
                ],
            )

        dry_run = run_migration(database_url, apply_changes=False, batch_size=10)
        assert dry_run.plaintext_candidates == 1
        assert dry_run.migrated == 0

        with engine.connect() as connection:
            value = connection.scalar(
                select(User.password_hash).where(User.email == emails[0])
            )
            assert value == "legacy-value"

        applied = run_migration(database_url, apply_changes=True, batch_size=10)
        assert applied.migrated == 1

        with engine.connect() as connection:
            value = connection.scalar(
                select(User.password_hash).where(User.email == emails[0])
            )
            assert value is not None and is_approved_password_hash(value)

        second_run = run_migration(database_url, apply_changes=True, batch_size=10)
        assert second_run.migrated == 0
        assert second_run.plaintext_candidates == 0
    finally:
        with engine.begin() as connection:
            connection.execute(delete(User).where(User.email.in_(emails)))
