"""Read-only production configuration and schema readiness checks."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from src.core.config import get_settings
from src.core.exceptions import CredentialConfigurationError
from src.modules.ai_credentials.crypto import CredentialCipher


REQUIRED_TABLES = {
    "mastery_history",
    "ai_credentials",
    "ai_credential_usage",
    "pdf_notes",
}


def main() -> int:
    try:
        settings = get_settings()
    except Exception:
        print("configuration=invalid")
        return 1

    failures: list[str] = []
    print(f"environment={settings.ENVIRONMENT}")
    print("database_url=configured")
    print("jwt_secret=configured")
    print("gemini_key=configured")
    print("cloudinary_credentials=configured")

    if settings.BYOK_ENCRYPTION_KEYS:
        try:
            CredentialCipher(settings)
        except CredentialConfigurationError:
            print("byok_keyring=invalid")
            failures.append("BYOK keyring is invalid")
        else:
            print("byok_keyring=configured_and_valid")
    else:
        print("byok_keyring=not_configured")

    alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
    repository_heads = set(
        ScriptDirectory.from_config(alembic_config).get_heads()
    )

    database_url = make_url(settings.active_database_url)
    print(f"database_driver={database_url.drivername}")
    print(f"database_host={database_url.host or 'unknown'}")
    print(f"database_name={database_url.database or 'unknown'}")

    engine = create_engine(settings.active_database_url)
    try:
        with engine.connect() as connection:
            schema = inspect(connection).default_schema_name
            current_heads = set(
                MigrationContext.configure(connection).get_current_heads()
            )
            inspector = inspect(connection)
            tables = set(inspector.get_table_names(schema=schema))
            media_columns = {
                column["name"]
                for column in inspector.get_columns("media", schema=schema)
            }
            has_stored_ai_credentials = (
                bool(
                    connection.execute(
                        text("SELECT EXISTS (SELECT 1 FROM ai_credentials)")
                    ).scalar_one()
                )
                if "ai_credentials" in tables
                else False
            )
    finally:
        engine.dispose()

    print(f"database_schema={schema}")
    print("repository_heads=" + ",".join(sorted(repository_heads)))
    print("database_heads=" + ",".join(sorted(current_heads)))
    print(
        "stored_ai_credentials="
        + ("present" if has_stored_ai_credentials else "none")
    )

    if has_stored_ai_credentials and not settings.BYOK_ENCRYPTION_KEYS:
        failures.append("stored AI credentials require the existing BYOK keyring")

    if current_heads != repository_heads:
        failures.append("database Alembic revision does not match repository head")

    for table in sorted(REQUIRED_TABLES):
        present = table in tables
        print(f"table_{table}={'present' if present else 'missing'}")
        if not present:
            failures.append(f"required table {table} is missing")

    original_filename_present = "original_filename" in media_columns
    print(
        "media_original_filename="
        + ("present" if original_filename_present else "missing")
    )
    if not original_filename_present:
        failures.append("media.original_filename is missing")

    if failures:
        for failure in failures:
            print(f"failure={failure}")
        return 1

    print("deployment_readiness=ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
