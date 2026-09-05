from argparse import Namespace
from dataclasses import replace
from pathlib import Path

import pytest

import scripts.reconcile_legacy_schema_to_0001 as reconciliation
from scripts.reconcile_legacy_schema_to_0001 import (
    AUTOMATIC_NOT_NULL_DEPENDENCY_ALLOWANCE,
    COLLISION_VARIABLES,
    DEPENDENCY_QUERY,
    DDL_MANIFEST,
    EXPECTED_LEGACY_TABLES,
    EXPECTED_NAMING_DIFFERENCES,
    EXPECTED_STRUCTURAL_DIFFERENCES,
    ReconciliationFailure,
    _adoption_url,
    dependency_diagnostic_from_row,
    is_expected_automatic_not_null_dependency,
    manifest_sql_text,
    print_dependency_diagnostics,
    print_failure,
    run_in_transaction,
    sanitize_catalog_definition,
    unexpected_column_dependencies,
    validate_mode,
    validate_target,
)
from scripts.verify_legacy_schema_reconciliation import (
    compare_preservation_snapshots,
)


DIRECT_REHEARSAL_URL = (
    "postgresql+psycopg://rehearsal-user:secret@"
    "ep-revisee-rehearsal.eu-central-1.aws.neon.tech/revisee_rehearsal"
)


def _empty_env_file(tmp_path: Path) -> Path:
    path = tmp_path / "missing.env"
    assert not path.exists()
    return path


def _dependency_row(
    *,
    object_class: str = "pg_constraint",
    object_type: str = "constraint",
    schema: str = "public",
    object_name: str = "generated_not_null_name",
    constraint_type: str | None = "NOT_NULL",
    index_type: str | None = None,
    dependency_code: str = "a",
    definition: str = "NOT NULL type",
    constraint_table_schema: str | None = "public",
    constraint_table_name: str | None = "media",
    constrained_columns: tuple[str, ...] = ("type",),
    exact_target: bool = True,
    target_not_null: bool = True,
    standard_local: bool = True,
) -> tuple[object, ...]:
    return (
        object_class,
        object_type,
        schema,
        object_name,
        constraint_type,
        index_type,
        dependency_code,
        definition,
        constraint_table_schema,
        constraint_table_name,
        constrained_columns,
        exact_target,
        target_not_null,
        standard_local,
    )


def test_target_never_falls_back_to_normal_or_test_urls() -> None:
    with pytest.raises(ReconciliationFailure) as failure:
        _adoption_url(
            {
                "DATABASE_URL": "postgresql://normal/normal",
                "TEST_DATABASE_URL": "postgresql://test/test",
                "MIGRATION_TEST_DATABASE_URL": "postgresql://migration/test",
            }
        )

    assert failure.value.safe_code == "ADOPTION_REHEARSAL_TARGET_REQUIRED"


def test_apply_requires_explicit_rehearsal_confirmation() -> None:
    with pytest.raises(ReconciliationFailure) as failure:
        validate_mode(
            Namespace(
                apply=True,
                dry_run=False,
                confirm_rehearsal_reconciliation=False,
            )
        )

    assert failure.value.safe_code == "EXPLICIT_REHEARSAL_CONFIRMATION_REQUIRED"


def test_dry_run_does_not_require_apply_confirmation() -> None:
    validate_mode(
        Namespace(
            apply=False,
            dry_run=True,
            confirm_rehearsal_reconciliation=False,
        )
    )


def test_pooled_neon_target_is_rejected(tmp_path: Path) -> None:
    pooled_url = (
        "postgresql://user:secret@"
        "ep-revisee-rehearsal-pooler.eu-central-1.aws.neon.tech/db"
    )

    with pytest.raises(ReconciliationFailure) as failure:
        validate_target(pooled_url, environ={}, env_file=_empty_env_file(tmp_path))

    assert failure.value.safe_code == "POOLED_NEON_TARGET_REFUSED"


@pytest.mark.parametrize("collision_variable", COLLISION_VARIABLES)
def test_rehearsal_target_must_not_match_any_normal_or_test_target(
    collision_variable: str,
    tmp_path: Path,
) -> None:
    same_normalized_target = (
        "postgresql://different-user:different-secret@"
        "EP-REVISEE-REHEARSAL.EU-CENTRAL-1.AWS.NEON.TECH:5432/"
        "REVISEE_REHEARSAL"
    )
    with pytest.raises(ReconciliationFailure) as failure:
        validate_target(
            DIRECT_REHEARSAL_URL,
            environ={collision_variable: same_normalized_target},
            env_file=_empty_env_file(tmp_path),
        )

    assert failure.value.safe_code == f"TARGET_COLLIDES_WITH_{collision_variable}"


@pytest.mark.parametrize(
    "invalid_url",
    ("not-a-url", "sqlite:///rehearsal.db", "postgresql:///missing-host"),
)
def test_missing_or_malformed_postgresql_targets_are_rejected(
    invalid_url: str,
    tmp_path: Path,
) -> None:
    with pytest.raises(ReconciliationFailure):
        validate_target(
            invalid_url,
            environ={},
            env_file=_empty_env_file(tmp_path),
        )


def test_manifest_matches_the_approved_35_difference_reconciliation() -> None:
    assert len(EXPECTED_STRUCTURAL_DIFFERENCES) == 32
    assert len(EXPECTED_NAMING_DIFFERENCES) == 3
    assert len(EXPECTED_LEGACY_TABLES) == 13
    assert len(DDL_MANIFEST) == 35

    statements = manifest_sql_text().upper()
    required_fragments = (
        "LEARNING_ITEM_KEY_POINTS ALTER COLUMN LEARNING_ITEM_ID DROP NOT NULL",
        "REFERENCES PUBLIC.LEARNING_ITEM (ID)",
        "REFERENCES PUBLIC.USERS (ID)",
        "USER_SESSIONS ALTER COLUMN IS_ACTIVE DROP DEFAULT",
        "CREATE TYPE PUBLIC.ANSWER_OPTION_ENUM",
        "SELECTED_OPTION TYPE PUBLIC.ANSWER_OPTION_ENUM",
        "CREATE TYPE PUBLIC.MEDIA_TYPE_ENUM",
        "MEDIA ALTER COLUMN TYPE TYPE PUBLIC.MEDIA_TYPE_ENUM",
        "QUESTIONS ALTER COLUMN CORRECT_OPTION TYPE VARCHAR(1)",
        "USER_ATTEMPTS DROP COLUMN QUESTION_ORDER",
        "USER_ATTEMPTS DROP COLUMN TIME_TAKEN_SECONDS",
        "USER_ATTEMPTS DROP CONSTRAINT {ATTEMPT_UNIQUE}",
        "USER_LABEL_MASTERY ALTER COLUMN CORRECT_ATTEMPTS DROP DEFAULT",
        "USER_LABEL_MASTERY ALTER COLUMN MASTERY_SCORE DROP DEFAULT",
        "USER_LABEL_MASTERY ALTER COLUMN TOTAL_ATTEMPTS DROP DEFAULT",
        "USER_LEARNING_ITEM_MASTERY ALTER COLUMN CORRECT_ATTEMPTS DROP DEFAULT",
        "USER_LEARNING_ITEM_MASTERY ALTER COLUMN MASTERY_SCORE DROP DEFAULT",
        "USER_LEARNING_ITEM_MASTERY ALTER COLUMN TOTAL_ATTEMPTS DROP DEFAULT",
        "TO UQ_REVISION_SESSION_QUESTION",
        "TO UQ_USER_LABEL_MASTERY",
        "TO UQ_USER_LEARNING_ITEM_MASTERY",
    )
    for fragment in required_fragments:
        assert fragment in statements

    expected_index_tables = {
        "label",
        "learning_item",
        "learning_item_label",
        "media",
        "questions",
        "revision_session_questions",
        "revision_sessions",
        "user_attempts",
        "user_label_mastery",
        "user_learning_item_mastery",
        "user_sessions",
        "users",
    }
    index_operations = {
        operation.removeprefix("create baseline ID index for ")
        for operation, _statement in DDL_MANIFEST
        if operation.startswith("create baseline ID index for ")
    }
    assert index_operations == expected_index_tables


def test_manifest_contains_no_stamp_migration_or_destructive_table_operation() -> None:
    statements = manifest_sql_text().upper()
    for forbidden in (
        "ALEMBIC",
        "STAMP",
        "UPGRADE",
        "CREATE TABLE",
        "DROP TABLE",
        "TRUNCATE",
        "DELETE FROM",
    ):
        assert forbidden not in statements


def test_failures_are_sanitized(capsys) -> None:
    secret = "postgresql://user:top-secret@example.invalid/private"
    print_failure(
        ReconciliationFailure(
            "CONNECTION",
            "DATABASE_CONNECTION_FAILED",
            RuntimeError(secret),
        )
    )

    output = capsys.readouterr().out
    assert "FAILURE_STAGE=CONNECTION" in output
    assert "ERROR_CODE=DATABASE_CONNECTION_FAILED" in output
    assert "EXCEPTION_CLASS=RuntimeError" in output
    assert secret not in output
    assert "top-secret" not in output


def test_transaction_context_receives_failure_and_does_not_commit() -> None:
    class FakeTransaction:
        def __init__(self) -> None:
            self.committed = False
            self.rolled_back = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, _exc, _traceback) -> bool:
            self.committed = exc_type is None
            self.rolled_back = exc_type is not None
            return False

    class FakeConnection:
        def __init__(self) -> None:
            self.active_transaction = FakeTransaction()

        def transaction(self):
            return self.active_transaction

    connection = FakeConnection()

    with pytest.raises(RuntimeError, match="synthetic DDL failure"):
        run_in_transaction(
            connection,
            lambda _connection: (_ for _ in ()).throw(
                RuntimeError("synthetic DDL failure")
            ),
        )

    assert connection.active_transaction.rolled_back is True
    assert connection.active_transaction.committed is False


def test_snapshot_comparison_checks_rows_ids_and_sequences_separately() -> None:
    before = {
        "tables": {"users": {"row_count": 2, "id_signature": "abc"}},
        "sequences": [{"sequence": "users_id_seq", "last_value": 2}],
    }

    assert compare_preservation_snapshots(before, dict(before)) == (True, True)
    assert compare_preservation_snapshots(
        before,
        {**before, "tables": {}},
    ) == (False, True)
    assert compare_preservation_snapshots(
        before,
        {**before, "sequences": []},
    ) == (True, False)


def test_not_null_dependency_allowance_is_limited_to_converted_required_columns() -> None:
    assert AUTOMATIC_NOT_NULL_DEPENDENCY_ALLOWANCE == {
        ("media", "type"),
        ("questions", "correct_option"),
        ("user_attempts", "selected_option"),
    }
    assert all(
        reconciliation.BASELINE_COLUMNS[table_name][column_name][1] is False
        for table_name, column_name in AUTOMATIC_NOT_NULL_DEPENDENCY_ALLOWANCE
    )


def test_dependency_diagnostic_classifies_automatic_not_null_constraint() -> None:
    diagnostic = dependency_diagnostic_from_row(_dependency_row())

    assert diagnostic.object_class == "pg_constraint"
    assert diagnostic.object_type == "constraint"
    assert diagnostic.constraint_type == "NOT_NULL"
    assert diagnostic.index_type is None
    assert diagnostic.dependency_type == "AUTOMATIC"
    assert diagnostic.automatically_created is True
    assert diagnostic.definition == "NOT NULL type"
    assert diagnostic.constraint_table_name == "media"
    assert diagnostic.constrained_columns == ("type",)
    assert diagnostic.constrains_exact_target_column is True
    assert diagnostic.target_column_not_null is True
    assert diagnostic.standard_local_constraint is True


def test_dependency_diagnostic_classifies_user_created_unique_index() -> None:
    diagnostic = dependency_diagnostic_from_row(
        _dependency_row(
            object_class="pg_class",
            object_type="index",
            object_name="ix_media_type",
            constraint_type=None,
            index_type="UNIQUE",
            dependency_code="n",
            definition=(
                "CREATE UNIQUE INDEX ix_media_type ON media USING btree (type)"
            ),
            constraint_table_schema=None,
            constraint_table_name=None,
            constrained_columns=(),
            exact_target=False,
            standard_local=False,
        )
    )

    assert diagnostic.object_type == "index"
    assert diagnostic.index_type == "UNIQUE"
    assert diagnostic.dependency_type == "NORMAL"
    assert diagnostic.automatically_created is False


@pytest.mark.parametrize(
    ("table_name", "column_name", "definition"),
    (
        ("media", "type", "NOT NULL type"),
        ("questions", "correct_option", "NOT NULL correct_option"),
        ("user_attempts", "selected_option", "NOT NULL selected_option"),
    ),
)
def test_exact_automatic_not_null_dependency_is_structurally_allowed(
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    dependency = dependency_diagnostic_from_row(
        _dependency_row(
            object_name="arbitrary_generated_name",
            definition=definition,
            constraint_table_name=table_name,
            constrained_columns=(column_name,),
        )
    )

    assert is_expected_automatic_not_null_dependency(
        table_name,
        column_name,
        dependency,
    )
    assert unexpected_column_dependencies(
        table_name,
        column_name,
        [dependency],
    ) == []


@pytest.mark.parametrize(
    "change",
    (
        {"object_class": "pg_class"},
        {"object_type": "index"},
        {"schema": "private"},
        {"constraint_type": "CHECK"},
        {"index_type": "UNIQUE"},
        {"dependency_code": "n", "automatically_created": False},
        {"constraint_table_schema": "private"},
        {"constraint_table_name": "questions"},
        {"constrained_columns": ("url",)},
        {"constrains_exact_target_column": False},
        {"target_column_not_null": False},
        {"standard_local_constraint": False},
    ),
)
def test_differently_structured_not_null_dependencies_are_refused(
    change: dict[str, object],
) -> None:
    dependency = dependency_diagnostic_from_row(_dependency_row())
    changed = replace(dependency, **change)

    assert not is_expected_automatic_not_null_dependency(
        "media",
        "type",
        changed,
    )
    assert unexpected_column_dependencies("media", "type", [changed]) == [
        changed
    ]


def test_not_null_dependency_is_refused_for_nonbaseline_extra_column() -> None:
    dependency = dependency_diagnostic_from_row(
        _dependency_row(
            constraint_table_name="user_attempts",
            constrained_columns=("question_order",),
            definition="NOT NULL question_order",
        )
    )

    assert not is_expected_automatic_not_null_dependency(
        "user_attempts",
        "question_order",
        dependency,
    )


def test_multiple_or_additional_dependencies_remain_ambiguous_and_refused() -> None:
    allowed = dependency_diagnostic_from_row(_dependency_row())
    additional = dependency_diagnostic_from_row(
        _dependency_row(object_name="second_not_null_constraint")
    )

    assert unexpected_column_dependencies(
        "media",
        "type",
        [allowed, additional],
    ) == [allowed, additional]


def test_postcheck_requires_all_converted_columns_to_remain_not_null(
    monkeypatch,
) -> None:
    columns = {
        table_name: {column_name: {"nullable": False}}
        for table_name, column_name in AUTOMATIC_NOT_NULL_DEPENDENCY_ALLOWANCE
    }
    monkeypatch.setattr(
        reconciliation,
        "schema_metadata",
        lambda _connection: (set(columns), columns),
    )
    reconciliation._assert_converted_columns_remain_not_null(object())

    columns["media"]["type"]["nullable"] = True
    with pytest.raises(ReconciliationFailure) as failure:
        reconciliation._assert_converted_columns_remain_not_null(object())

    assert failure.value.safe_code == "TYPE_CONVERSION_NULLABILITY_CHANGED"


def test_catalog_definition_redacts_literals_comments_credentials_and_secrets() -> None:
    definition = (
        "CHECK (type <> 'postgresql://user:password@example.test/db') "
        "/* token=very-secret */ OR note = $$raw private note$$ "
        "OR api_key=unquoted-secret"
    )

    sanitized = sanitize_catalog_definition(definition)

    assert "password" not in sanitized
    assert "very-secret" not in sanitized
    assert "raw private note" not in sanitized
    assert "unquoted-secret" not in sanitized
    assert "<redacted_literal>" in sanitized
    assert "<redacted_comment>" in sanitized
    assert "api_key=<redacted_value>" in sanitized


def test_dependency_output_contains_safe_catalog_metadata_only(capsys) -> None:
    diagnostic = dependency_diagnostic_from_row(
        _dependency_row(
            object_name="media_type_check",
            constraint_type="CHECK",
            dependency_code="i",
            definition=(
                "CHECK (type <> 'postgresql://user:password@example.test/db')"
            ),
        )
    )

    print_dependency_diagnostics("media", "type", [diagnostic])
    output = capsys.readouterr().out

    assert "DEPENDENCY_TARGET=media.type" in output
    assert "UNEXPECTED_DEPENDENCY_COUNT=1" in output
    assert "OBJECT_CLASS=pg_constraint" in output
    assert "OBJECT_TYPE=constraint" in output
    assert "SCHEMA=public" in output
    assert "OBJECT_NAME=media_type_check" in output
    assert "CONSTRAINT_TYPE=CHECK" in output
    assert "INDEX_TYPE=<not_applicable>" in output
    assert "DEPENDENCY_TYPE=INTERNAL" in output
    assert "AUTOMATICALLY_CREATED=YES" in output
    assert "CONSTRAINT_TABLE=public.media" in output
    assert "CONSTRAINED_COLUMNS=type" in output
    assert "EXACT_TARGET_COLUMN=YES" in output
    assert "TARGET_COLUMN_NOT_NULL=YES" in output
    assert "<redacted_literal>" in output
    assert "password" not in output


def test_dependency_inventory_reads_only_postgresql_catalogs() -> None:
    normalized = " ".join(DEPENDENCY_QUERY.casefold().split())

    assert "from pg_depend" in normalized
    assert "join pg_attribute" in normalized
    assert "dependency.refclassid = 'pg_class'::regclass" in normalized
    assert "referenced_relation.relname = %s" in normalized
    assert "referenced_attribute.attname = %s" in normalized
    for forbidden in (" insert ", " update ", " delete ", " alter ", " drop "):
        assert forbidden not in f" {normalized} "
