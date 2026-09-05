"""Guarded, single-step Alembic adoption for the isolated rehearsal database."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from copy import deepcopy
import os
from pathlib import Path
import re
import sys
from typing import Any

from alembic import command
from alembic.config import Config
import psycopg
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.inspect_development_database import (  # noqa: E402
    BASELINE_COLUMNS,
    _constraint_metadata,
    _normalized_column_default,
    baseline_schema_comparison,
    schema_metadata,
)
from scripts.reconcile_legacy_schema_to_0001 import (  # noqa: E402
    ADVISORY_LOCK_KEYS,
    EXPECTED_LEGACY_TABLES,
    ReconciliationFailure,
    _adoption_url,
    _psycopg_connection_string,
    _snapshot_database,
    _target_identity_hash,
    load_snapshot,
    sanitize_catalog_definition,
    validate_target,
)
from scripts.verify_legacy_schema_reconciliation import (  # noqa: E402
    compare_preservation_snapshots,
)


REVISION_0001 = "20260824_0001"
ORDERED_UPGRADE_REVISIONS = (
    "20260825_0002",
    "20260826_0003",
    "20260826_0004",
    "20260827_0005",
    "20260829_0006",
)
REVISION_SEQUENCE = (REVISION_0001, *ORDERED_UPGRADE_REVISIONS)
PREDECESSOR = {
    revision: REVISION_SEQUENCE[position - 1]
    for position, revision in enumerate(REVISION_SEQUENCE)
    if position > 0
}

TARGET_VALIDATION = "TARGET_VALIDATION"
READ_ONLY_PREFLIGHT = "READ_ONLY_PREFLIGHT"
ACTION_PREFLIGHT = "ACTION_PREFLIGHT"
ALEMBIC_ACTION = "ALEMBIC_ACTION"
POST_ACTION = "POST_ACTION"
CONNECTION = "CONNECTION"


class AdoptionFailure(Exception):
    def __init__(self, stage: str, safe_code: str, cause: BaseException | None = None):
        super().__init__(safe_code)
        self.stage = stage
        self.safe_code = safe_code
        self.cause = cause


def _phase_columns() -> dict[str, dict[str, set[str]]]:
    baseline = {
        table_name: set(columns)
        for table_name, columns in BASELINE_COLUMNS.items()
    }
    phase_2 = deepcopy(baseline)
    phase_2["revision_sessions"].update(
        {
            "requested_strategy",
            "strategy_used",
            "status",
            "requested_question_count",
            "questions_per_label",
            "generated_question_count",
            "allow_ai_generation",
        }
    )
    phase_2["revision_session_questions"].update(
        {
            "learning_item_id",
            "session_label_id",
            "learning_item_title_snapshot",
            "question_text_snapshot",
            "option_a_snapshot",
            "option_b_snapshot",
            "option_c_snapshot",
            "option_d_snapshot",
            "correct_option_snapshot",
            "explanation_snapshot",
            "difficulty_snapshot",
            "expected_time_seconds_snapshot",
            "source_snapshot",
            "generated_for_session",
        }
    )
    phase_2["revision_session_labels"] = {
        "id",
        "session_id",
        "label_id",
        "label_name_snapshot",
        "label_order",
        "question_quota",
    }

    phase_3 = deepcopy(phase_2)
    phase_3["questions"].update(
        {"content_fingerprint", "generation_event_id"}
    )
    phase_3["ai_generation_events"] = {
        "id",
        "user_id",
        "label_id",
        "operation_type",
        "provider",
        "model",
        "prompt_template_version",
        "status",
        "requested_count",
        "valid_count",
        "persisted_count",
        "duplicate_count",
        "rejected_count",
        "excess_count",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_tokens",
        "thought_tokens",
        "tool_tokens",
        "estimated_input_tokens",
        "input_token_count_estimated",
        "response_id",
        "safe_error_code",
        "created_at",
        "started_at",
        "completed_at",
    }
    phase_3["ai_generation_calls"] = {
        "id",
        "generation_event_id",
        "learning_item_id",
        "source_identifier",
        "call_order",
        "allocated_count",
        "status",
        "valid_count",
        "persisted_count",
        "duplicate_count",
        "rejected_count",
        "excess_count",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_tokens",
        "thought_tokens",
        "tool_tokens",
        "estimated_input_tokens",
        "input_token_count_estimated",
        "provider",
        "model",
        "response_id",
        "safe_error_code",
        "created_at",
        "started_at",
        "completed_at",
    }

    phase_4 = deepcopy(phase_3)
    phase_4["user_attempts"].update(
        {"session_question_id", "time_taken_seconds", "mastery_delta"}
    )
    phase_4["question_statistics"] = {
        "question_id",
        "total_attempt_count",
        "correct_attempt_count",
        "total_time_seconds",
        "average_time_seconds",
        "last_attempted_at",
    }
    return {
        REVISION_0001: baseline,
        ORDERED_UPGRADE_REVISIONS[0]: phase_2,
        ORDERED_UPGRADE_REVISIONS[1]: phase_3,
        ORDERED_UPGRADE_REVISIONS[2]: phase_4,
        ORDERED_UPGRADE_REVISIONS[3]: deepcopy(phase_4),
        ORDERED_UPGRADE_REVISIONS[4]: deepcopy(phase_4),
    }


EXPECTED_COLUMNS = _phase_columns()


def validated_adoption_target(
    environ: Mapping[str, str],
    *,
    env_file: Path | None = None,
):
    try:
        adoption_url = _adoption_url(environ)
        return validate_target(
            adoption_url,
            environ=environ,
            env_file=env_file,
        )
    except ReconciliationFailure as exc:
        raise AdoptionFailure(exc.stage, exc.safe_code, exc.cause or exc) from None


def validate_preservation_snapshot_payload(
    snapshot: Mapping[str, object],
) -> None:
    tables = snapshot.get("tables")
    sequences = snapshot.get("sequences")
    if not isinstance(tables, Mapping) or set(tables) != set(
        EXPECTED_LEGACY_TABLES
    ):
        raise AdoptionFailure(TARGET_VALIDATION, "SNAPSHOT_FILE_STRUCTURE_INVALID")
    for table_name in EXPECTED_LEGACY_TABLES:
        signature = tables.get(table_name)
        if not isinstance(signature, Mapping) or set(signature) != {
            "row_count",
            "id_signature",
        }:
            raise AdoptionFailure(
                TARGET_VALIDATION,
                "SNAPSHOT_FILE_STRUCTURE_INVALID",
            )
        row_count = signature.get("row_count")
        id_signature = signature.get("id_signature")
        if (
            not isinstance(row_count, int)
            or isinstance(row_count, bool)
            or row_count < 0
            or not isinstance(id_signature, str)
            or re.fullmatch(r"[0-9a-f]{32}", id_signature) is None
        ):
            raise AdoptionFailure(
                TARGET_VALIDATION,
                "SNAPSHOT_FILE_STRUCTURE_INVALID",
            )
    if not isinstance(sequences, list):
        raise AdoptionFailure(TARGET_VALIDATION, "SNAPSHOT_FILE_STRUCTURE_INVALID")
    seen_sequences: set[str] = set()
    sequence_owners: set[tuple[object, object]] = set()
    for sequence in sequences:
        if not isinstance(sequence, Mapping) or set(sequence) != {
            "sequence",
            "owner_table",
            "owner_column",
            "last_value",
        }:
            raise AdoptionFailure(
                TARGET_VALIDATION,
                "SNAPSHOT_FILE_STRUCTURE_INVALID",
            )
        name = sequence.get("sequence")
        owner_table = sequence.get("owner_table")
        owner_column = sequence.get("owner_column")
        last_value = sequence.get("last_value")
        if (
            not isinstance(name, str)
            or not name
            or name in seen_sequences
            or owner_table not in EXPECTED_LEGACY_TABLES
            or not isinstance(owner_column, str)
            or not owner_column
            or (
                last_value is not None
                and (
                    not isinstance(last_value, int)
                    or isinstance(last_value, bool)
                )
            )
        ):
            raise AdoptionFailure(
                TARGET_VALIDATION,
                "SNAPSHOT_FILE_STRUCTURE_INVALID",
            )
        seen_sequences.add(name)
        sequence_owners.add((owner_table, owner_column))
    expected_owners = {(table_name, "id") for table_name in EXPECTED_LEGACY_TABLES}
    if sequence_owners != expected_owners or len(seen_sequences) != len(
        expected_owners
    ):
        raise AdoptionFailure(TARGET_VALIDATION, "SNAPSHOT_FILE_STRUCTURE_INVALID")


def retained_legacy_snapshot(snapshot: Mapping[str, object]) -> dict[str, object]:
    retained = dict(snapshot)
    sequences = snapshot.get("sequences")
    if not isinstance(sequences, list):
        return retained
    retained["sequences"] = [
        sequence
        for sequence in sequences
        if isinstance(sequence, Mapping)
        and sequence.get("owner_table") in EXPECTED_LEGACY_TABLES
    ]
    return retained


def validate_mode(args: argparse.Namespace) -> None:
    mutating = bool(args.stamp_0001 or args.upgrade_to)
    if mutating and not args.confirm_rehearsal_upgrade:
        raise AdoptionFailure(
            TARGET_VALIDATION,
            "EXPLICIT_REHEARSAL_UPGRADE_CONFIRMATION_REQUIRED",
        )


def validate_upgrade_transition(current_revision: str | None, target: str) -> None:
    if target not in ORDERED_UPGRADE_REVISIONS:
        raise AdoptionFailure(TARGET_VALIDATION, "UPGRADE_TARGET_NOT_ALLOWED")
    if current_revision != PREDECESSOR[target]:
        raise AdoptionFailure(
            ACTION_PREFLIGHT,
            "REVISION_ORDER_VIOLATION",
        )


def build_alembic_config(
    database_url: str,
    connection: Any,
) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["connection"] = connection
    config.attributes["adoption_rehearsal_database_url"] = database_url
    return config


def _current_revision(connection) -> str | None:
    exists = connection.execute(
        "SELECT to_regclass('public.alembic_version')"
    ).fetchone()
    if exists is None or exists[0] is None:
        return None
    rows = connection.execute(
        "SELECT version_num FROM public.alembic_version ORDER BY version_num"
    ).fetchall()
    if len(rows) != 1 or not rows[0][0]:
        raise AdoptionFailure(ACTION_PREFLIGHT, "AMBIGUOUS_ALEMBIC_REVISION")
    return str(rows[0][0])


def _assert_preservation_snapshot(
    connection,
    expected_snapshot: Mapping[str, object],
    target_hash: str,
    *,
    stage: str,
) -> None:
    unfiltered_snapshot = _snapshot_database(connection, target_hash)
    if not isinstance(unfiltered_snapshot.get("sequences"), list):
        raise AdoptionFailure(stage, "PRESERVATION_SNAPSHOT_MISMATCH")
    current_snapshot = retained_legacy_snapshot(unfiltered_snapshot)
    tables_match, sequences_match = compare_preservation_snapshots(
        expected_snapshot,
        current_snapshot,
    )
    if not tables_match or not sequences_match:
        raise AdoptionFailure(stage, "PRESERVATION_SNAPSHOT_MISMATCH")


def _constraint_definitions(connection) -> dict[tuple[str, str], str]:
    rows = connection.execute(
        """
        SELECT relation.relname, constraint_row.conname,
               pg_get_constraintdef(constraint_row.oid, TRUE)
        FROM pg_constraint AS constraint_row
        JOIN pg_class AS relation ON relation.oid = constraint_row.conrelid
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
        ORDER BY relation.relname, constraint_row.conname
        """
    ).fetchall()
    return {
        (str(table_name), str(constraint_name)): " ".join(str(definition).split())
        for table_name, constraint_name, definition in rows
    }


def _assert_foreign_key(
    constraints: Sequence[Mapping[str, object]],
    *,
    table: str,
    columns: tuple[str, ...],
    target: str,
    on_delete: str,
) -> None:
    matches = [
        constraint
        for constraint in constraints
        if constraint["kind"] == "f"
        and constraint["table"] == table
        and constraint["columns"] == columns
        and constraint["target_table"] == target
        and constraint["target_columns"] == ("id",)
        and constraint["on_delete"] == on_delete
    ]
    if len(matches) != 1:
        raise AdoptionFailure(ACTION_PREFLIGHT, "REVISION_SCHEMA_CONTRACT_MISMATCH")


def _assert_revision_schema(connection, revision: str) -> None:
    tables, columns = schema_metadata(connection)
    expected = EXPECTED_COLUMNS.get(revision)
    if expected is None:
        raise AdoptionFailure(ACTION_PREFLIGHT, "UNSUPPORTED_CURRENT_REVISION")
    application_tables = tables - {"alembic_version"}
    if application_tables != set(expected):
        raise AdoptionFailure(ACTION_PREFLIGHT, "REVISION_TABLE_SHAPE_MISMATCH")
    if any(
        set(columns[table_name]) != expected_columns
        for table_name, expected_columns in expected.items()
    ):
        raise AdoptionFailure(ACTION_PREFLIGHT, "REVISION_COLUMN_SHAPE_MISMATCH")

    if revision == REVISION_0001:
        structural, naming, blockers = baseline_schema_comparison(
            connection,
            application_tables,
            columns,
        )
        if structural or naming or blockers:
            raise AdoptionFailure(
                ACTION_PREFLIGHT,
                "BASELINE_0001_SCHEMA_MISMATCH",
            )
        return

    constraints = _constraint_metadata(connection)
    definitions = _constraint_definitions(connection)
    requested_strategy = definitions.get(
        ("revision_sessions", "ck_revision_session_requested_strategy")
    )
    strategy_used = definitions.get(
        ("revision_sessions", "ck_revision_session_strategy_used")
    )
    if not requested_strategy or not strategy_used:
        raise AdoptionFailure(ACTION_PREFLIGHT, "REVISION_SCHEMA_CONTRACT_MISMATCH")
    smart_expected = REVISION_SEQUENCE.index(revision) >= REVISION_SEQUENCE.index(
        ORDERED_UPGRADE_REVISIONS[3]
    )
    if ("SMART" in requested_strategy) is not smart_expected or (
        "SMART" in strategy_used
    ) is not smart_expected:
        raise AdoptionFailure(ACTION_PREFLIGHT, "STRATEGY_CONSTRAINT_MISMATCH")

    _assert_foreign_key(
        constraints,
        table="revision_session_questions",
        columns=("question_id",),
        target="questions",
        on_delete="SET NULL",
    )
    if REVISION_SEQUENCE.index(revision) >= REVISION_SEQUENCE.index(
        ORDERED_UPGRADE_REVISIONS[2]
    ):
        required_attempt_constraint = (
            "user_attempts",
            "uq_user_attempt_session_question",
        )
        if required_attempt_constraint not in definitions:
            raise AdoptionFailure(
                ACTION_PREFLIGHT,
                "SUBMISSION_SCHEMA_CONTRACT_MISMATCH",
            )

    key_point_nullable = columns["learning_item_key_points"]["learning_item_id"]
    user_session_default = columns["user_sessions"]["is_active"]
    protection_expected = revision == ORDERED_UPGRADE_REVISIONS[4]
    expected_nullable = not protection_expected
    if bool(key_point_nullable["nullable"]) is not expected_nullable:
        raise AdoptionFailure(ACTION_PREFLIGHT, "PROTECTION_NULLABILITY_MISMATCH")
    expected_default = "true" if protection_expected else None
    normalized_default = _normalized_column_default(user_session_default)
    if normalized_default in {"'true'::boolean", "true::boolean"}:
        normalized_default = "true"
    if normalized_default != expected_default:
        raise AdoptionFailure(ACTION_PREFLIGHT, "PROTECTION_DEFAULT_MISMATCH")
    _assert_foreign_key(
        constraints,
        table="learning_item_key_points",
        columns=("learning_item_id",),
        target="learning_item",
        on_delete="CASCADE" if protection_expected else "NO ACTION",
    )
    _assert_foreign_key(
        constraints,
        table="user_sessions",
        columns=("user_id",),
        target="users",
        on_delete="CASCADE" if protection_expected else "NO ACTION",
    )


def _assert_ready_to_stamp(
    connection,
    expected_snapshot: Mapping[str, object],
    target_hash: str,
) -> None:
    if _current_revision(connection) is not None:
        raise AdoptionFailure(ACTION_PREFLIGHT, "ALEMBIC_VERSION_MUST_BE_ABSENT")
    _assert_revision_schema(connection, REVISION_0001)
    _assert_preservation_snapshot(
        connection,
        expected_snapshot,
        target_hash,
        stage=ACTION_PREFLIGHT,
    )


def _assert_post_action_state(
    connection,
    expected_revision: str,
    expected_snapshot: Mapping[str, object],
    target_hash: str,
) -> None:
    if _current_revision(connection) != expected_revision:
        raise AdoptionFailure(
            POST_ACTION,
            "POST_ACTION_REVISION_MISMATCH",
        )
    _assert_revision_schema(connection, expected_revision)
    _assert_preservation_snapshot(
        connection,
        expected_snapshot,
        target_hash,
        stage=POST_ACTION,
    )


def _setup_transaction(connection, *, read_only: bool) -> None:
    if read_only:
        connection.execute(
            "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
        )
    else:
        connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
    connection.execute("SET LOCAL statement_timeout = '120s'")
    connection.execute("SET LOCAL lock_timeout = '5s'")
    connection.execute(
        "SELECT pg_advisory_xact_lock(%s, %s)",
        ADVISORY_LOCK_KEYS,
    )


def _lock_current_tables(connection) -> None:
    tables, _columns = schema_metadata(connection)
    if not tables:
        raise AdoptionFailure(ACTION_PREFLIGHT, "APPLICATION_SCHEMA_MISSING")
    table_list = sql.SQL(", ").join(
        sql.SQL("public.{}").format(sql.Identifier(table_name))
        for table_name in sorted(tables)
    )
    connection.execute(
        sql.SQL("LOCK TABLE {} IN ACCESS EXCLUSIVE MODE").format(table_list)
    )


def _run_read_only_preflight(
    parsed_url,
    expected_snapshot: Mapping[str, object],
    target_hash: str,
) -> None:
    try:
        with psycopg.connect(
            _psycopg_connection_string(parsed_url),
            connect_timeout=15,
            autocommit=False,
        ) as connection:
            with connection.transaction():
                _setup_transaction(connection, read_only=True)
                _assert_ready_to_stamp(connection, expected_snapshot, target_hash)
    except AdoptionFailure:
        raise
    except ReconciliationFailure as exc:
        raise AdoptionFailure(
            READ_ONLY_PREFLIGHT,
            "RECONCILIATION_SNAPSHOT_VALIDATION_FAILED",
            exc,
        ) from None
    except Exception as exc:
        raise AdoptionFailure(
            READ_ONLY_PREFLIGHT,
            "READ_ONLY_PREFLIGHT_FAILED",
            exc,
        ) from None


def _run_mutation(
    parsed_url,
    expected_snapshot: Mapping[str, object],
    target_hash: str,
    *,
    stamp_0001: bool,
    target_revision: str | None,
) -> None:
    database_url = _psycopg_connection_string(parsed_url)
    engine_url = parsed_url.set(drivername="postgresql+psycopg")
    engine = create_engine(engine_url, poolclass=NullPool, pool_pre_ping=True)
    action_started = False
    try:
        with engine.connect() as sqlalchemy_connection:
            with sqlalchemy_connection.begin():
                raw_connection = sqlalchemy_connection.connection.driver_connection
                _setup_transaction(raw_connection, read_only=False)
                _lock_current_tables(raw_connection)
                current = _current_revision(raw_connection)
                if stamp_0001:
                    _assert_ready_to_stamp(
                        raw_connection,
                        expected_snapshot,
                        target_hash,
                    )
                    expected_revision = REVISION_0001
                else:
                    if target_revision is None:
                        raise AdoptionFailure(
                            ACTION_PREFLIGHT,
                            "UPGRADE_TARGET_REQUIRED",
                        )
                    validate_upgrade_transition(current, target_revision)
                    _assert_revision_schema(raw_connection, str(current))
                    _assert_preservation_snapshot(
                        raw_connection,
                        expected_snapshot,
                        target_hash,
                        stage=ACTION_PREFLIGHT,
                    )
                    expected_revision = target_revision

                config = build_alembic_config(
                    database_url,
                    sqlalchemy_connection,
                )
                action_started = True
                if stamp_0001:
                    command.stamp(config, REVISION_0001)
                else:
                    command.upgrade(config, expected_revision)

                _assert_post_action_state(
                    raw_connection,
                    expected_revision,
                    expected_snapshot,
                    target_hash,
                )
    except AdoptionFailure:
        raise
    except Exception as exc:
        safe_code = (
            "ALEMBIC_ACTION_STATE_UNCERTAIN"
            if action_started
            else "ADOPTION_DATABASE_CONNECTION_FAILED"
        )
        raise AdoptionFailure(
            ALEMBIC_ACTION if action_started else CONNECTION,
            safe_code,
            exc,
        ) from None
    finally:
        engine.dispose()


def _sqlstate(exc: BaseException | None) -> str | None:
    current = exc
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        value = getattr(current, "sqlstate", None)
        if value:
            return str(value).upper()
        nested = getattr(current, "__cause__", None) or getattr(
            current,
            "__context__",
            None,
        )
        current = nested if isinstance(nested, BaseException) else None
    return None


def print_failure(failure: AdoptionFailure) -> None:
    exception_name = (
        type(failure.cause).__name__
        if failure.cause is not None
        else type(failure).__name__
    )
    print("ADOPTION_ERROR=FAILED")
    print(f"FAILURE_STAGE={sanitize_catalog_definition(failure.stage)}")
    print(f"ERROR_CODE={sanitize_catalog_definition(failure.safe_code)}")
    print(f"EXCEPTION_CLASS={sanitize_catalog_definition(exception_name)}")
    print(f"SQLSTATE={_sqlstate(failure.cause) or '<unavailable>'}")
    if failure.safe_code == "ALEMBIC_ACTION_STATE_UNCERTAIN":
        print("ACTION_STATE=UNCERTAIN_INSPECT_BEFORE_RETRY")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one guarded Alembic action on the adoption rehearsal",
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--preflight", action="store_true")
    action.add_argument("--stamp-0001", action="store_true")
    action.add_argument(
        "--upgrade-to",
        choices=ORDERED_UPGRADE_REVISIONS,
    )
    parser.add_argument("--confirm-rehearsal-upgrade", action="store_true")
    parser.add_argument("--snapshot-file", type=Path, required=True)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> int:
    args = _parser().parse_args(argv)
    active_environ = environ if environ is not None else os.environ
    try:
        validate_mode(args)
        parsed_url = validated_adoption_target(active_environ)
        target_hash = _target_identity_hash(parsed_url)
        expected_snapshot = load_snapshot(args.snapshot_file, target_hash)
        validate_preservation_snapshot_payload(expected_snapshot)
        if args.preflight:
            _run_read_only_preflight(
                parsed_url,
                expected_snapshot,
                target_hash,
            )
            print("ADOPTION_ACTION=PREFLIGHT")
            print("CURRENT_REVISION=<absent>")
            print("SCHEMA_0001_COMPATIBLE=YES")
            print("PRESERVATION_SNAPSHOT_MATCH=YES")
            print("READY_TO_STAMP_0001=YES")
            return 0

        _run_mutation(
            parsed_url,
            expected_snapshot,
            target_hash,
            stamp_0001=args.stamp_0001,
            target_revision=args.upgrade_to,
        )
        completed_revision = REVISION_0001 if args.stamp_0001 else args.upgrade_to
        print("ADOPTION_ACTION=STAMP_0001" if args.stamp_0001 else "ADOPTION_ACTION=UPGRADE")
        print(f"CURRENT_REVISION={completed_revision}")
        print("PRESERVATION_SNAPSHOT_MATCH=YES")
        print("AUTOMATIC_CONTINUATION=NO")
        return 0
    except ReconciliationFailure as exc:
        print_failure(
            AdoptionFailure(exc.stage, exc.safe_code, exc.cause or exc)
        )
        return 2
    except AdoptionFailure as failure:
        print_failure(failure)
        return 2
    except KeyboardInterrupt:
        print("ADOPTION_ERROR=INTERRUPTED")
        print("ACTION_STATE=UNCERTAIN_INSPECT_BEFORE_RETRY")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
