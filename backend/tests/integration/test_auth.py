from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import text

from src.core.exceptions import AuthenticationError
from src.core.security import is_approved_password_hash
from src.core.security import create_access_token, decode_access_token
from src.modules.auth.models import User, UserSession
from src.modules.auth.service import AuthService, hash_refresh_token


COOKIE_REQUEST_HEADERS = {
    "Origin": "http://localhost:4200",
    "X-Revisee-CSRF": "spa",
}


def test_registration_hashes_password_and_preserves_response(client, db_session) -> None:
    response = client.post(
        "/register",
        json={
            "username": "new-user",
            "email": "new-user@example.test",
            "password": "safe-password",
        },
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Registration successful"
    assert response.json()["token_type"] == "bearer"

    user = db_session.query(User).filter(User.username == "new-user").one()
    assert user.password_hash != "safe-password"
    assert is_approved_password_hash(user.password_hash)
    session_user_id, token_hash = db_session.execute(
        text(
            "SELECT user_id, token_hash FROM user_sessions "
            "WHERE user_id = :user_id"
        ),
        {"user_id": user.id},
    ).one()
    assert session_user_id == user.id
    assert len(token_hash) == 64
    assert "revisee_refresh" not in response.json()
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "Path=/auth" in cookie
    assert "SameSite=lax" in cookie


def test_registration_rejects_legacy_query_parameter_credentials(client) -> None:
    response = client.post(
        "/register",
        params={
            "username": "query-user",
            "email": "query-user@example.test",
            "password": "safe-password",
        },
    )
    assert response.status_code == 422


def test_registration_validates_public_account_fields(client) -> None:
    response = client.post(
        "/register",
        json={
            "username": "x",
            "email": "not-an-email",
            "password": "short",
        },
    )
    assert response.status_code == 422


def test_registration_rejects_duplicate_identity(client) -> None:
    payload = {
        "username": "duplicate-user",
        "email": "duplicate@example.test",
        "password": "safe-password",
    }
    assert client.post("/register", json=payload).status_code == 200
    response = client.post("/register", json=payload)
    assert response.status_code == 400
    assert "username or email" in response.json()["detail"].casefold()


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


def test_login_stores_only_refresh_hash_and_returns_safe_user(client, db_session) -> None:
    client.post(
        "/register",
        json={"username": "hash-user", "email": "hash@example.test", "password": "safe-password"},
    )
    response = client.post(
        "/login", json={"username": "hash-user", "password": "safe-password"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["expires_in"] > 0
    assert payload["user"]["username"] == "hash-user"
    assert "refresh_token" not in payload
    raw_token = response.cookies["revisee_refresh"]
    session = db_session.query(UserSession).filter(
        UserSession.token_hash == hash_refresh_token(raw_token)
    ).one()
    assert session.token_hash != raw_token


def test_refresh_rotates_token_in_the_same_family(client, db_session) -> None:
    registered = client.post(
        "/register",
        json={"username": "rotate", "email": "rotate@example.test", "password": "safe-password"},
    )
    old_raw = registered.cookies["revisee_refresh"]
    old = db_session.query(UserSession).filter(
        UserSession.token_hash == hash_refresh_token(old_raw)
    ).one()
    response = client.post("/auth/refresh", headers=COOKIE_REQUEST_HEADERS)
    assert response.status_code == 200
    new_raw = response.cookies["revisee_refresh"]
    assert new_raw != old_raw
    db_session.refresh(old)
    replacement = db_session.query(UserSession).filter(
        UserSession.token_hash == hash_refresh_token(new_raw)
    ).one()
    assert old.revoked_at is not None
    assert old.replaced_by_session_id == replacement.id
    assert replacement.parent_session_id == old.id
    assert replacement.family_id == old.family_id


def test_reused_refresh_token_revokes_the_complete_family(client, db_session) -> None:
    registered = client.post(
        "/register",
        json={"username": "replay", "email": "replay@example.test", "password": "safe-password"},
    )
    stolen_old_token = registered.cookies["revisee_refresh"]
    assert client.post("/auth/refresh", headers=COOKIE_REQUEST_HEADERS).status_code == 200
    client.cookies.set("revisee_refresh", stolen_old_token, path="/auth")
    replay = client.post("/auth/refresh", headers=COOKIE_REQUEST_HEADERS)
    assert replay.status_code == 401
    assert "Max-Age=0" in replay.headers["set-cookie"]
    family_id = db_session.query(UserSession).filter(
        UserSession.token_hash == hash_refresh_token(stolen_old_token)
    ).one().family_id
    assert all(
        session.revoked_at is not None
        for session in db_session.query(UserSession).filter(
            UserSession.family_id == family_id
        ).all()
    )


def test_missing_expired_absolute_and_revoked_refresh_tokens_fail(client, db_session) -> None:
    client.cookies.clear()
    missing = client.post("/auth/refresh", headers=COOKIE_REQUEST_HEADERS)
    assert missing.status_code == 401
    assert "Max-Age=0" in missing.headers["set-cookie"]

    for field in ("expires_at", "absolute_expires_at", "revoked_at"):
        response = client.post(
            "/register",
            json={
                "username": f"expired-{field}",
                "email": f"expired-{field}@example.test",
                "password": "safe-password",
            },
        )
        raw = response.cookies["revisee_refresh"]
        session = db_session.query(UserSession).filter(
            UserSession.token_hash == hash_refresh_token(raw)
        ).one()
        setattr(session, field, datetime.now(timezone.utc) - timedelta(seconds=1))
        db_session.commit()
        assert client.post("/auth/refresh", headers=COOKIE_REQUEST_HEADERS).status_code == 401


def test_logout_revokes_family_clears_cookie_and_is_idempotent(client, db_session) -> None:
    response = client.post(
        "/register",
        json={"username": "logout", "email": "logout@example.test", "password": "safe-password"},
    )
    raw = response.cookies["revisee_refresh"]
    session = db_session.query(UserSession).filter(
        UserSession.token_hash == hash_refresh_token(raw)
    ).one()
    first = client.post("/auth/logout", headers=COOKIE_REQUEST_HEADERS)
    assert first.status_code == 200
    assert "Max-Age=0" in first.headers["set-cookie"]
    db_session.refresh(session)
    assert session.revoked_at is not None
    assert client.post("/auth/logout", headers=COOKIE_REQUEST_HEADERS).status_code == 200


def test_access_and_refresh_tokens_are_not_interchangeable(client) -> None:
    response = client.post(
        "/register",
        json={"username": "types", "email": "types@example.test", "password": "safe-password"},
    )
    access_token = response.json()["access_token"]
    refresh_token = response.cookies["revisee_refresh"]
    assert client.get(
        "/labels", headers={"Authorization": f"Bearer {refresh_token}"}
    ).status_code == 401
    client.cookies.set("revisee_refresh", access_token, path="/auth")
    assert client.post("/auth/refresh", headers=COOKIE_REQUEST_HEADERS).status_code == 401


def test_refresh_and_logout_require_trusted_origin_and_custom_header(client) -> None:
    client.post(
        "/register",
        json={"username": "csrf", "email": "csrf@example.test", "password": "safe-password"},
    )
    assert client.post("/auth/refresh").status_code == 403
    assert client.post(
        "/auth/refresh",
        headers={"Origin": "https://attacker.example", "X-Revisee-CSRF": "spa"},
    ).status_code == 403


def test_concurrent_refresh_cannot_create_multiple_valid_children(
    migrated_database,
) -> None:
    from sqlalchemy.orm import Session

    from src.db.session import engine

    setup = Session(bind=engine)
    try:
        _, issued = AuthService(setup).register(
            "concurrent-refresh",
            "concurrent-refresh@example.test",
            "safe-password",
        )
        raw_token = issued.refresh_token
        family_id = decode_access_token(issued.access_token)["sid"]
    finally:
        setup.close()

    barrier = Barrier(2)

    def rotate() -> str:
        session = Session(bind=engine)
        try:
            barrier.wait(timeout=5)
            AuthService(session).refresh(raw_token)
            return "success"
        except AuthenticationError:
            return "rejected"
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _index: rotate(), range(2)))
        assert sorted(outcomes) == ["rejected", "success"]

        verification = Session(bind=engine)
        try:
            family = verification.query(UserSession).filter(
                UserSession.family_id == family_id
            ).all()
            assert len(family) == 2
            assert all(session.revoked_at is not None for session in family)
        finally:
            verification.close()
    finally:
        cleanup = Session(bind=engine)
        try:
            user = cleanup.query(User).filter(
                User.username == "concurrent-refresh"
            ).one_or_none()
            if user is not None:
                cleanup.delete(user)
                cleanup.commit()
        finally:
            cleanup.close()


def test_protected_endpoint_requires_bearer_token(client) -> None:
    response = client.get("/labels")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_session_cannot_be_reused_with_another_user_id(client, registered_user) -> None:
    payload = decode_access_token(registered_user["token"])
    forged_subject_token = create_access_token(
        {"sub": "999999", "sid": payload["sid"]}
    )
    response = client.get(
        "/labels",
        headers={"Authorization": f"Bearer {forged_subject_token}"},
    )
    assert response.status_code == 401
