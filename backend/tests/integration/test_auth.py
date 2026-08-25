from src.core.security import is_approved_password_hash
from src.core.security import create_access_token, decode_access_token
from src.modules.auth.models import User


def test_registration_hashes_password_and_preserves_response(client, db_session) -> None:
    response = client.post(
        "/register",
        params={
            "username": "new-user",
            "email": "new-user@example.test",
            "password": "safe-password",
        },
    )
    assert response.status_code == 200
    assert response.json()["message"] == "registration successfull"
    assert response.json()["token_type"] == "bearer"

    user = db_session.query(User).filter(User.username == "new-user").one()
    assert user.password_hash != "safe-password"
    assert is_approved_password_hash(user.password_hash)


def test_login_upgrades_legacy_plaintext(client, db_session) -> None:
    user = User(
        username="legacy",
        email="legacy@example.test",
        password_hash="legacy-password",
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/login",
        json={"username": "legacy", "password": "legacy-password"},
    )
    assert response.status_code == 200
    db_session.refresh(user)
    assert is_approved_password_hash(user.password_hash)


def test_protected_endpoint_requires_bearer_token(client) -> None:
    response = client.get("/labels")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_session_cannot_be_reused_with_another_user_id(client, registered_user) -> None:
    payload = decode_access_token(registered_user["token"])
    forged_subject_token = create_access_token(
        {"sub": "999999", "session_id": payload["session_id"]}
    )
    response = client.get(
        "/labels",
        headers={"Authorization": f"Bearer {forged_subject_token}"},
    )
    assert response.status_code == 401
