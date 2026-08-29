"""Destructive migration verification for a separate disposable database.

These tests DROP and recreate the public schema before and after every test.
They must never receive TEST_DATABASE_URL or a development/production target.
The conftest guards require both explicit execution flags and a distinct,
test-and-migration-named MIGRATION_TEST_DATABASE_URL.
"""

from __future__ import annotations

import hashlib
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection, Engine

from src.core.config import get_settings
from src.db.base import Base
import src.db.models  # noqa: F401


pytestmark = [pytest.mark.integration, pytest.mark.migration]

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
REVISION_0001 = "20260824_0001"
REVISION_0002 = "20260825_0002"
REVISION_0003 = "20260826_0003"
REVISION_0004 = "20260826_0004"
REVISION_0005 = "20260827_0005"
REVISION_0006 = "20260829_0006"


class MigrationHarness:
    def __init__(self, database_url: str, engine: Engine) -> None:
        self.database_url = database_url
        self.engine = engine

    def upgrade(self, revision: str) -> None:
        self._run(command.upgrade, revision)

    def downgrade(self, revision: str) -> None:
        self._run(command.downgrade, revision)

    def check(self) -> None:
        self._run(command.check)

    def current_revision(self) -> str | None:
        with self.engine.connect() as connection:
            exists = connection.scalar(text("SELECT to_regclass('public.alembic_version')"))
            if exists is None:
                return None
            return connection.scalar(text("SELECT version_num FROM alembic_version"))

    def schema_signature(self) -> str:
        inspector = inspect(self.engine)
        payload: list[object] = []
        for table_name in sorted(inspector.get_table_names()):
            payload.append(("table", table_name))
            payload.append(("columns", table_name, inspector.get_columns(table_name)))
            payload.append(
                ("checks", table_name, inspector.get_check_constraints(table_name))
            )
            payload.append(
                ("foreign_keys", table_name, inspector.get_foreign_keys(table_name))
            )
            payload.append(
                ("indexes", table_name, inspector.get_indexes(table_name))
            )
            payload.append(
                ("primary_key", table_name, inspector.get_pk_constraint(table_name))
            )
            payload.append(
                ("unique", table_name, inspector.get_unique_constraints(table_name))
            )
        return _safe_hash(payload)

    def data_signature(self) -> str:
        inspector = inspect(self.engine)
        payload: list[object] = []
        with self.engine.connect() as connection:
            for table_name in sorted(inspector.get_table_names()):
                quoted = connection.dialect.identifier_preparer.quote(table_name)
                rows = connection.execute(
                    text(f"SELECT * FROM {quoted} ORDER BY 1")
                ).all()
                payload.append((table_name, rows))
        return _safe_hash(payload)

    def _run(self, operation: Callable[..., None], *args: str) -> None:
        config = Config(str(ALEMBIC_INI))
        with _migration_environment(self.database_url):
            operation(config, *args)


@pytest.fixture
def migration_harness(migration_test_database_url: str) -> Iterator[MigrationHarness]:
    engine = create_engine(migration_test_database_url, pool_pre_ping=True)
    _reset_public_schema(engine)
    harness = MigrationHarness(migration_test_database_url, engine)
    try:
        yield harness
    finally:
        # This intentionally destroys every object and row in public.
        _reset_public_schema(engine)
        engine.dispose()


def test_blank_chain_downgrade_reupgrade_and_orm_consistency(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    assert inspect(harness.engine).get_table_names() == []

    harness.upgrade("head")
    assert harness.current_revision() == REVISION_0006
    _assert_0006_protection_contract(harness.engine)
    _assert_orm_schema_consistency(harness.engine)
    harness.check()

    harness.downgrade(REVISION_0005)
    assert harness.current_revision() == REVISION_0005
    _assert_0005_protection_contract(harness.engine)
    harness.upgrade("head")
    assert harness.current_revision() == REVISION_0006

    harness.downgrade(REVISION_0004)
    assert harness.current_revision() == REVISION_0004
    harness.upgrade("head")
    assert harness.current_revision() == REVISION_0006

    # downgrade base drops every application table and is safe only here.
    harness.downgrade("base")
    remaining = set(inspect(harness.engine).get_table_names())
    assert remaining <= {"alembic_version"}
    assert harness.current_revision() is None

    harness.upgrade("head")
    assert harness.current_revision() == REVISION_0006
    _assert_0006_protection_contract(harness.engine)
    _assert_orm_schema_consistency(harness.engine)
    harness.check()


def test_0002_upgrade_refuses_invalid_session_backfill(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    harness.upgrade(REVISION_0001)
    with harness.engine.begin() as connection:
        user_id = _seed_user(connection)
        _seed_legacy_session(connection, user_id, quiz_type="SMART")
    _assert_refusal(
        harness,
        lambda: harness.upgrade(REVISION_0002),
        REVISION_0001,
        "revision session backfill requires manual reconciliation",
    )


def test_0002_upgrade_refuses_duplicate_question_order(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    harness.upgrade(REVISION_0001)
    with harness.engine.begin() as connection:
        user_id = _seed_user(connection)
        item_id = _seed_item(connection, user_id)
        first_question = _seed_question(connection, item_id, "First?")
        second_question = _seed_question(connection, item_id, "Second?")
        session_id = _seed_legacy_session(connection, user_id)
        _seed_legacy_selection(connection, session_id, first_question, order=1)
        _seed_legacy_selection(connection, session_id, second_question, order=1)
    _assert_refusal(
        harness,
        lambda: harness.upgrade(REVISION_0002),
        REVISION_0001,
        "duplicate revision-session question order requires reconciliation",
    )


def test_0002_upgrade_refuses_incomplete_snapshot_backfill(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    harness.upgrade(REVISION_0001)
    with harness.engine.begin() as connection:
        user_id = _seed_user(connection)
        session_id = _seed_legacy_session(connection, user_id)
        connection.execute(
            text(
                "ALTER TABLE revision_session_questions DROP CONSTRAINT "
                "revision_session_questions_question_id_fkey"
            )
        )
        _seed_legacy_selection(connection, session_id, 999_999, order=1)
    _assert_refusal(
        harness,
        lambda: harness.upgrade(REVISION_0002),
        REVISION_0001,
        "revision-session snapshot backfill is incomplete",
    )


def test_0002_downgrade_refuses_phase1_history(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    harness.upgrade(REVISION_0002)
    with harness.engine.begin() as connection:
        seeded = _seed_snapshot_session(connection)
        label_id = connection.scalar(
            text(
                "INSERT INTO label (user_id, label_name) "
                "VALUES (:user_id, 'History') RETURNING id"
            ),
            {"user_id": seeded["user_id"]},
        )
        connection.execute(
            text(
                "INSERT INTO revision_session_labels "
                "(session_id, label_id, label_name_snapshot, label_order, question_quota) "
                "VALUES (:session_id, :label_id, 'History', 1, 1)"
            ),
            {"session_id": seeded["session_id"], "label_id": label_id},
        )
    _assert_refusal(
        harness,
        lambda: harness.downgrade(REVISION_0001),
        REVISION_0002,
        "downgrade refused: Phase 1 historical data is not representable",
    )


def test_0003_downgrade_refuses_generation_history(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    harness.upgrade(REVISION_0003)
    with harness.engine.begin() as connection:
        seeded = _seed_snapshot_session(connection)
        connection.execute(
            text(
                "UPDATE questions SET content_fingerprint = :fingerprint "
                "WHERE id = :question_id"
            ),
            {"fingerprint": "a" * 64, "question_id": seeded["question_id"]},
        )
    _assert_refusal(
        harness,
        lambda: harness.downgrade(REVISION_0002),
        REVISION_0003,
        "downgrade refused: Phase 2A operational history exists",
    )


def test_0004_upgrade_refuses_legacy_attempts(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    harness.upgrade(REVISION_0003)
    with harness.engine.begin() as connection:
        seeded = _seed_snapshot_session(connection)
        connection.execute(
            text(
                "INSERT INTO user_attempts "
                "(user_id, question_id, session_id, selected_option, is_correct) "
                "VALUES (:user_id, :question_id, :session_id, 'A', TRUE)"
            ),
            seeded,
        )
    _assert_refusal(
        harness,
        lambda: harness.upgrade(REVISION_0004),
        REVISION_0003,
        "upgrade refused: legacy attempts require reviewed reconciliation",
    )


def test_0004_upgrade_refuses_completed_sessions(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    harness.upgrade(REVISION_0003)
    with harness.engine.begin() as connection:
        _seed_snapshot_session(connection, status="COMPLETED", ended=True)
    _assert_refusal(
        harness,
        lambda: harness.upgrade(REVISION_0004),
        REVISION_0003,
        "upgrade refused: completed sessions require reviewed reconciliation",
    )


def test_0004_upgrade_refuses_invalid_lifecycle_or_snapshot_count(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    harness.upgrade(REVISION_0003)
    with harness.engine.begin() as connection:
        _seed_snapshot_session(connection, status="IN_PROGRESS", ended=True)
    _assert_refusal(
        harness,
        lambda: harness.upgrade(REVISION_0004),
        REVISION_0003,
        "upgrade refused: revision session lifecycle or snapshot count is invalid",
    )


def test_0004_upgrade_refuses_unusable_snapshot_answer(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    harness.upgrade(REVISION_0003)
    with harness.engine.begin() as connection:
        _seed_snapshot_session(connection, correct_option="Z")
    _assert_refusal(
        harness,
        lambda: harness.upgrade(REVISION_0004),
        REVISION_0003,
        "upgrade refused: a snapshot answer cannot be normalized",
    )


def test_0004_upgrade_refuses_invalid_mastery(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    harness.upgrade(REVISION_0003)
    with harness.engine.begin() as connection:
        user_id = _seed_user(connection)
        item_id = _seed_item(connection, user_id)
        connection.execute(
            text(
                "INSERT INTO user_learning_item_mastery "
                "(user_id, learning_item_id, mastery_score, total_attempts, correct_attempts) "
                "VALUES (:user_id, :item_id, 101, 0, 0)"
            ),
            {"user_id": user_id, "item_id": item_id},
        )
    _assert_refusal(
        harness,
        lambda: harness.upgrade(REVISION_0004),
        REVISION_0003,
        "upgrade refused: existing mastery values violate Phase 3 constraints",
    )


def test_0004_downgrade_refuses_completed_history(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    harness.upgrade(REVISION_0004)
    with harness.engine.begin() as connection:
        _seed_snapshot_session(connection, status="COMPLETED", ended=True)
    _assert_refusal(
        harness,
        lambda: harness.downgrade(REVISION_0003),
        REVISION_0004,
        "downgrade refused: Phase 3 completion, attempt, or statistics history exists",
    )


def test_0004_downgrade_refuses_fractional_mastery(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    harness.upgrade(REVISION_0004)
    with harness.engine.begin() as connection:
        user_id = _seed_user(connection)
        item_id = _seed_item(connection, user_id)
        connection.execute(
            text(
                "INSERT INTO user_learning_item_mastery "
                "(user_id, learning_item_id, mastery_score, total_attempts, correct_attempts) "
                "VALUES (:user_id, :item_id, 50.50, 0, 0)"
            ),
            {"user_id": user_id, "item_id": item_id},
        )
    _assert_refusal(
        harness,
        lambda: harness.downgrade(REVISION_0003),
        REVISION_0004,
        "downgrade refused: Decimal mastery cannot be restored losslessly",
    )


def test_0005_downgrade_refuses_smart_history(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    harness.upgrade(REVISION_0005)
    with harness.engine.begin() as connection:
        _seed_snapshot_session(
            connection,
            requested_strategy="SMART",
            strategy_used="SMART",
            quiz_type="SMART",
        )
    _assert_refusal(
        harness,
        lambda: harness.downgrade(REVISION_0004),
        REVISION_0005,
        "downgrade refused: SMART revision-session history exists",
    )


def test_0006_upgrade_refuses_null_key_point_reference(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    harness.upgrade(REVISION_0005)
    with harness.engine.begin() as connection:
        key_point_id = connection.scalar(
            text(
                "INSERT INTO learning_item_key_points (learning_item_id, key_point) "
                "VALUES (NULL, 'Unowned key point') RETURNING id"
            )
        )
    _assert_refusal(
        harness,
        lambda: harness.upgrade(REVISION_0006),
        REVISION_0005,
        "upgrade refused: null key-point references require reconciliation",
    )
    with harness.engine.connect() as connection:
        assert connection.scalar(
            text("SELECT COUNT(*) FROM learning_item_key_points WHERE id = :id"),
            {"id": key_point_id},
        ) == 1


def test_0006_upgrade_refuses_orphan_key_point_reference(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    harness.upgrade(REVISION_0005)
    with harness.engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE learning_item_key_points DROP CONSTRAINT "
                "learning_item_key_points_learning_item_id_fkey"
            )
        )
        key_point_id = connection.scalar(
            text(
                "INSERT INTO learning_item_key_points (learning_item_id, key_point) "
                "VALUES (999999, 'Orphan key point') RETURNING id"
            )
        )
    _assert_refusal(
        harness,
        lambda: harness.upgrade(REVISION_0006),
        REVISION_0005,
        "upgrade refused: orphan key-point references require reconciliation",
    )
    with harness.engine.connect() as connection:
        assert connection.scalar(
            text("SELECT learning_item_id FROM learning_item_key_points WHERE id = :id"),
            {"id": key_point_id},
        ) == 999999


def test_0006_upgrade_refuses_orphan_user_session_reference(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    harness.upgrade(REVISION_0005)
    with harness.engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE user_sessions DROP CONSTRAINT "
                "user_sessions_user_id_fkey"
            )
        )
        user_session_id = connection.scalar(
            text(
                "INSERT INTO user_sessions (user_id, session_id, is_active) "
                "VALUES (999999, 'orphan-session', TRUE) RETURNING id"
            )
        )
    _assert_refusal(
        harness,
        lambda: harness.upgrade(REVISION_0006),
        REVISION_0005,
        "upgrade refused: orphan user-session references require reconciliation",
    )
    with harness.engine.connect() as connection:
        assert connection.scalar(
            text("SELECT user_id FROM user_sessions WHERE id = :id"),
            {"id": user_session_id},
        ) == 999999


def test_0006_upgrade_refuses_missing_expected_foreign_key(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    harness.upgrade(REVISION_0005)
    with harness.engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE learning_item_key_points DROP CONSTRAINT "
                "learning_item_key_points_learning_item_id_fkey"
            )
        )
    _assert_refusal(
        harness,
        lambda: harness.upgrade(REVISION_0006),
        REVISION_0005,
        "upgrade refused: expected 0005 foreign-key definitions are missing "
        "or incompatible",
    )


def test_0006_upgrade_refuses_wrong_expected_foreign_key_definition(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    harness.upgrade(REVISION_0005)
    with harness.engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE user_sessions DROP CONSTRAINT "
                "user_sessions_user_id_fkey"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE user_sessions ADD CONSTRAINT user_sessions_user_id_fkey "
                "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE"
            )
        )
    _assert_refusal(
        harness,
        lambda: harness.upgrade(REVISION_0006),
        REVISION_0005,
        "upgrade refused: expected 0005 foreign-key definitions are missing "
        "or incompatible",
    )


def test_0006_database_cascades_and_server_default(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    harness.upgrade(REVISION_0006)
    _assert_0006_protection_contract(harness.engine)

    with harness.engine.begin() as connection:
        key_point_user_id = _seed_user(connection, suffix="key-point-cascade")
        item_id = _seed_item(connection, key_point_user_id)
        key_point_id = connection.scalar(
            text(
                "INSERT INTO learning_item_key_points (learning_item_id, key_point) "
                "VALUES (:item_id, 'Cascade key point') RETURNING id"
            ),
            {"item_id": item_id},
        )
        connection.execute(
            text("DELETE FROM learning_item WHERE id = :item_id"),
            {"item_id": item_id},
        )
        assert connection.scalar(
            text("SELECT COUNT(*) FROM learning_item_key_points WHERE id = :id"),
            {"id": key_point_id},
        ) == 0

        session_user_id = _seed_user(connection, suffix="session-cascade")
        defaulted_session_id = connection.scalar(
            text(
                "INSERT INTO user_sessions (user_id, session_id) "
                "VALUES (:user_id, 'defaulted-session') RETURNING id"
            ),
            {"user_id": session_user_id},
        )
        assert connection.scalar(
            text("SELECT is_active FROM user_sessions WHERE id = :id"),
            {"id": defaulted_session_id},
        ) is True

        nullable_session_id = connection.scalar(
            text(
                "INSERT INTO user_sessions (user_id, session_id, is_active) "
                "VALUES (:user_id, 'nullable-session', NULL) RETURNING id"
            ),
            {"user_id": session_user_id},
        )
        assert connection.scalar(
            text("SELECT is_active FROM user_sessions WHERE id = :id"),
            {"id": nullable_session_id},
        ) is None

        connection.execute(
            text("DELETE FROM users WHERE id = :user_id"),
            {"user_id": session_user_id},
        )
        assert connection.scalar(
            text("SELECT COUNT(*) FROM user_sessions WHERE id = :id"),
            {"id": defaulted_session_id},
        ) == 0
        assert connection.scalar(
            text("SELECT COUNT(*) FROM user_sessions WHERE id = :id"),
            {"id": nullable_session_id},
        ) == 0


def test_0006_downgrade_restores_0005_contract_without_losing_rows(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness
    harness.upgrade(REVISION_0006)
    with harness.engine.begin() as connection:
        user_id = _seed_user(connection, suffix="downgrade")
        item_id = _seed_item(connection, user_id)
        key_point_id = connection.scalar(
            text(
                "INSERT INTO learning_item_key_points (learning_item_id, key_point) "
                "VALUES (:item_id, 'Retained key point') RETURNING id"
            ),
            {"item_id": item_id},
        )
        user_session_id = connection.scalar(
            text(
                "INSERT INTO user_sessions (user_id, session_id) "
                "VALUES (:user_id, 'retained-session') RETURNING id"
            ),
            {"user_id": user_id},
        )

    harness.downgrade(REVISION_0005)
    assert harness.current_revision() == REVISION_0005
    _assert_0005_protection_contract(harness.engine)
    with harness.engine.connect() as connection:
        assert connection.scalar(
            text("SELECT learning_item_id FROM learning_item_key_points WHERE id = :id"),
            {"id": key_point_id},
        ) == item_id
        assert connection.scalar(
            text("SELECT user_id FROM user_sessions WHERE id = :id"),
            {"id": user_session_id},
        ) == user_id

    harness.upgrade(REVISION_0006)
    assert harness.current_revision() == REVISION_0006
    _assert_0006_protection_contract(harness.engine)


def _assert_refusal(
    harness: MigrationHarness,
    operation: Callable[[], None],
    expected_revision: str,
    expected_guard_message: str,
) -> None:
    assert harness.current_revision() == expected_revision
    schema_before = harness.schema_signature()
    data_before = harness.data_signature()

    with pytest.raises(Exception) as caught:
        operation()
    messages = _exception_messages(caught.value)
    assert expected_guard_message in messages, (
        "Expected migration refusal guard was not observed; provider output withheld"
    )

    assert harness.current_revision() == expected_revision
    assert harness.schema_signature() == schema_before
    assert harness.data_signature() == data_before


def _assert_orm_schema_consistency(engine: Engine) -> None:
    inspector = inspect(engine)
    actual_tables = set(inspector.get_table_names()) - {"alembic_version"}
    expected_tables = set(Base.metadata.tables)
    assert actual_tables == expected_tables
    for table_name, table in Base.metadata.tables.items():
        actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
        assert actual_columns == {column.name for column in table.columns}


def _assert_0005_protection_contract(engine: Engine) -> None:
    inspector = inspect(engine)
    key_point_column = _column(inspector, "learning_item_key_points", "learning_item_id")
    session_active_column = _column(inspector, "user_sessions", "is_active")

    assert key_point_column["nullable"] is True
    assert session_active_column["nullable"] is True
    assert session_active_column["default"] is None
    assert _foreign_key_ondelete(
        inspector,
        "learning_item_key_points",
        ["learning_item_id"],
    ) == "NO ACTION"
    assert _foreign_key_ondelete(
        inspector,
        "user_sessions",
        ["user_id"],
    ) == "NO ACTION"


def _assert_0006_protection_contract(engine: Engine) -> None:
    inspector = inspect(engine)
    key_point_column = _column(inspector, "learning_item_key_points", "learning_item_id")
    session_active_column = _column(inspector, "user_sessions", "is_active")

    assert key_point_column["nullable"] is False
    assert session_active_column["nullable"] is True
    assert str(session_active_column["default"]).casefold() in {
        "true",
        "true::boolean",
    }
    assert _foreign_key_ondelete(
        inspector,
        "learning_item_key_points",
        ["learning_item_id"],
    ) == "CASCADE"
    assert _foreign_key_ondelete(
        inspector,
        "user_sessions",
        ["user_id"],
    ) == "CASCADE"


def _column(inspector, table_name: str, column_name: str) -> dict[str, object]:
    return next(
        column
        for column in inspector.get_columns(table_name)
        if column["name"] == column_name
    )


def _foreign_key_ondelete(
    inspector,
    table_name: str,
    constrained_columns: list[str],
) -> str:
    foreign_key = next(
        candidate
        for candidate in inspector.get_foreign_keys(table_name)
        if candidate["constrained_columns"] == constrained_columns
    )
    ondelete = foreign_key.get("options", {}).get("ondelete")
    return str(ondelete or "NO ACTION").upper()


def _seed_user(connection: Connection, *, suffix: str = "default") -> int:
    return connection.scalar(
        text(
            "INSERT INTO users (username, email, password_hash) "
            "VALUES (:username, :email, 'test-only') "
            "RETURNING id"
        ),
        {
            "username": f"migration-user-{suffix}",
            "email": f"migration-user-{suffix}@example.test",
        },
    )


def _seed_item(connection: Connection, user_id: int) -> int:
    return connection.scalar(
        text(
            "INSERT INTO learning_item (user_id, title, description_text) "
            "VALUES (:user_id, 'Migration item', 'notes') RETURNING id"
        ),
        {"user_id": user_id},
    )


def _seed_question(
    connection: Connection,
    item_id: int,
    question_text: str = "Migration question?",
    correct_option: str = "0",
) -> int:
    return connection.scalar(
        text(
            "INSERT INTO questions "
            "(learning_item_id, question_text, option_a, option_b, option_c, option_d, "
            "correct_option, explanation, difficulty, expected_time_seconds, source) "
            "VALUES (:item_id, :question_text, 'A', 'B', 'C', 'D', "
            ":correct_option, 'Explanation', 1, 20, 'stored') RETURNING id"
        ),
        {
            "item_id": item_id,
            "question_text": question_text,
            "correct_option": correct_option,
        },
    )


def _seed_legacy_session(
    connection: Connection,
    user_id: int,
    quiz_type: str = "RANDOM",
) -> int:
    return connection.scalar(
        text(
            "INSERT INTO revision_sessions (user_id, quiz_type) "
            "VALUES (:user_id, :quiz_type) RETURNING id"
        ),
        {"user_id": user_id, "quiz_type": quiz_type},
    )


def _seed_legacy_selection(
    connection: Connection,
    session_id: int,
    question_id: int,
    *,
    order: int,
) -> int:
    return connection.scalar(
        text(
            "INSERT INTO revision_session_questions "
            "(session_id, question_id, question_order) "
            "VALUES (:session_id, :question_id, :question_order) RETURNING id"
        ),
        {
            "session_id": session_id,
            "question_id": question_id,
            "question_order": order,
        },
    )


def _seed_snapshot_session(
    connection: Connection,
    *,
    status: str = "IN_PROGRESS",
    ended: bool = False,
    correct_option: str = "0",
    requested_strategy: str = "RANDOM",
    strategy_used: str = "RANDOM",
    quiz_type: str = "RANDOM",
) -> dict[str, int]:
    user_id = _seed_user(connection)
    item_id = _seed_item(connection, user_id)
    question_id = _seed_question(
        connection,
        item_id,
        correct_option=correct_option,
    )
    session_id = connection.scalar(
        text(
            "INSERT INTO revision_sessions "
            "(user_id, quiz_type, requested_strategy, strategy_used, status, "
            "requested_question_count, questions_per_label, generated_question_count, "
            "allow_ai_generation, ended_at) "
            "VALUES (:user_id, :quiz_type, :requested_strategy, :strategy_used, "
            ":status, 1, NULL, 0, FALSE, "
            "CASE WHEN :ended THEN CURRENT_TIMESTAMP ELSE NULL END) RETURNING id"
        ),
        {
            "user_id": user_id,
            "quiz_type": quiz_type,
            "requested_strategy": requested_strategy,
            "strategy_used": strategy_used,
            "status": status,
            "ended": ended,
        },
    )
    session_question_id = connection.scalar(
        text(
            "INSERT INTO revision_session_questions "
            "(session_id, question_id, learning_item_id, question_order, "
            "learning_item_title_snapshot, question_text_snapshot, "
            "option_a_snapshot, option_b_snapshot, option_c_snapshot, option_d_snapshot, "
            "correct_option_snapshot, explanation_snapshot, difficulty_snapshot, "
            "expected_time_seconds_snapshot, source_snapshot, generated_for_session) "
            "VALUES (:session_id, :question_id, :item_id, 1, 'Migration item', "
            "'Migration question?', 'A', 'B', 'C', 'D', :correct_option, "
            "'Explanation', 1, 20, 'stored', FALSE) RETURNING id"
        ),
        {
            "session_id": session_id,
            "question_id": question_id,
            "item_id": item_id,
            "correct_option": correct_option,
        },
    )
    return {
        "user_id": user_id,
        "item_id": item_id,
        "question_id": question_id,
        "session_id": session_id,
        "session_question_id": session_question_id,
    }


def _reset_public_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))


@contextmanager
def _migration_environment(database_url: str) -> Iterator[None]:
    replacements = {
        "ENVIRONMENT": "test",
        "TEST_DATABASE_URL": database_url,
        "SECRET_KEY": "migration-test-secret-key-that-is-never-used-outside-tests",
        "GOOGLE_API_KEY": "migration-test-google-key",
        "CLOUDINARY_CLOUD_NAME": "migration-test-cloud",
        "CLOUDINARY_API_KEY": "migration-test-cloudinary-key",
        "CLOUDINARY_API_SECRET": "migration-test-cloudinary-secret",
    }
    previous = {key: os.environ.get(key) for key in replacements}
    os.environ.update(replacements)
    get_settings.cache_clear()
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def _exception_messages(error: BaseException) -> str:
    messages: list[str] = []
    current: BaseException | None = error
    while current is not None:
        messages.append(str(current))
        current = current.__cause__ or current.__context__
    return "\n".join(messages)


def _safe_hash(value: object) -> str:
    return hashlib.sha256(repr(value).encode("utf-8")).hexdigest()
