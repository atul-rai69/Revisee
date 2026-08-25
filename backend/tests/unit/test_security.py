from src.core.security import (
    hash_password,
    is_approved_password_hash,
    verify_password,
)


def test_argon2_hash_and_verification() -> None:
    password_hash = hash_password("safe-password")

    assert password_hash != "safe-password"
    assert is_approved_password_hash(password_hash)
    assert verify_password("safe-password", password_hash) == (True, False)
    assert verify_password("wrong", password_hash) == (False, False)


def test_plaintext_is_marked_for_temporary_upgrade() -> None:
    assert verify_password("legacy", "legacy") == (True, True)
    assert verify_password("wrong", "legacy") == (False, True)


def test_unsupported_hash_is_never_treated_as_plaintext() -> None:
    assert verify_password("$2b$unsupported", "$2b$unsupported") == (False, False)
