from scripts.migrate_plaintext_passwords import classify_password
from src.core.security import hash_password


def test_password_migration_classification() -> None:
    assert classify_password(hash_password("secret")) == "approved"
    assert classify_password("legacy plaintext") == "plaintext"
    assert classify_password("$2b$unsupported") == "ambiguous"
