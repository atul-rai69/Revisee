"""One-time reconciliation of the isolated legacy rehearsal schema to 0001.

This command never stamps or runs Alembic. Its apply mode performs only the
reviewed schema reconciliation and requires a snapshot produced by dry-run mode.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

from dotenv import dotenv_values
import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.inspect_development_database import (  # noqa: E402
    BASELINE_COLUMNS,
    BASELINE_FOREIGN_KEYS,
    _constraint_metadata,
    baseline_schema_comparison,
    schema_metadata,
)


TARGET_ENVIRONMENT_VARIABLE = "ADOPTION_REHEARSAL_DATABASE_URL"
COLLISION_VARIABLES = (
    "DATABASE_URL",
    "TEST_DATABASE_URL",
    "MIGRATION_TEST_DATABASE_URL",
)
SNAPSHOT_FORMAT = 1
STATEMENT_TIMEOUT = "60s"
LOCK_TIMEOUT = "5s"
ADVISORY_LOCK_KEYS = (20260829, 1)
EXPECTED_LEGACY_TABLES = (
    "label",
    "learning_item",
    "learning_item_key_points",
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
)

TARGET_VALIDATION = "TARGET_VALIDATION"
CONNECTION = "CONNECTION"
TRANSACTION_SETUP = "TRANSACTION_SETUP"
LOCK_ACQUISITION = "LOCK_ACQUISITION"
PREFLIGHT = "PREFLIGHT"
SNAPSHOT = "SNAPSHOT"
RECONCILIATION = "RECONCILIATION"
POST_RECONCILIATION = "POST_RECONCILIATION"

DEPENDENCY_TARGETS = (
    ("media", "type"),
    ("questions", "correct_option"),
    ("user_attempts", "selected_option"),
    ("user_attempts", "question_order"),
    ("user_attempts", "time_taken_seconds"),
)
AUTOMATIC_NOT_NULL_DEPENDENCY_ALLOWANCE = frozenset(
    {
        ("media", "type"),
        ("questions", "correct_option"),
        ("user_attempts", "selected_option"),
    }
)

DEPENDENCY_QUERY = """
    SELECT
        CASE
            WHEN dependency.classid = 'pg_constraint'::regclass
                THEN 'pg_constraint'
            ELSE dependency.classid::regclass::text
        END AS object_class,
        CASE
            WHEN dependency.classid = 'pg_constraint'::regclass
                THEN 'constraint'
            WHEN dependency.classid = 'pg_class'::regclass
                 AND dependent_relation.relkind IN ('i', 'I')
                THEN 'index'
            WHEN dependency.classid = 'pg_class'::regclass
                THEN CASE dependent_relation.relkind
                    WHEN 'r' THEN 'table'
                    WHEN 'p' THEN 'partitioned_table'
                    WHEN 'v' THEN 'view'
                    WHEN 'm' THEN 'materialized_view'
                    WHEN 'S' THEN 'sequence'
                    ELSE 'relation'
                END
            WHEN dependency.classid = 'pg_rewrite'::regclass
                THEN 'rewrite_rule'
            WHEN dependency.classid = 'pg_attrdef'::regclass
                THEN 'column_default'
            WHEN dependency.classid = 'pg_trigger'::regclass
                THEN 'trigger'
            WHEN dependency.classid = 'pg_proc'::regclass
                THEN 'function'
            WHEN dependency.classid = 'pg_type'::regclass
                THEN 'type'
            ELSE 'catalog_object'
        END AS object_type,
        COALESCE(
            constraint_namespace.nspname,
            dependent_namespace.nspname,
            rewrite_namespace.nspname,
            default_namespace.nspname,
            trigger_namespace.nspname,
            function_namespace.nspname,
            type_namespace.nspname,
            'pg_catalog'
        ) AS object_schema,
        COALESCE(
            constraint_row.conname,
            dependent_relation.relname,
            rewrite_row.rulename,
            default_attribute.attname || '_default',
            trigger_row.tgname,
            function_row.proname,
            type_row.typname,
            'object_' || dependency.objid::text
        ) AS object_name,
        CASE constraint_row.contype
            WHEN 'c' THEN 'CHECK'
            WHEN 'f' THEN 'FOREIGN_KEY'
            WHEN 'n' THEN 'NOT_NULL'
            WHEN 'p' THEN 'PRIMARY_KEY'
            WHEN 'u' THEN 'UNIQUE'
            WHEN 'x' THEN 'EXCLUSION'
            ELSE NULL
        END AS constraint_type,
        CASE
            WHEN dependent_index.indexrelid IS NULL THEN NULL
            WHEN dependent_index.indisprimary THEN 'PRIMARY_KEY'
            WHEN dependent_index.indisexclusion THEN 'EXCLUSION'
            WHEN dependent_index.indisunique THEN 'UNIQUE'
            ELSE 'NONUNIQUE'
        END AS index_type,
        dependency.deptype,
        CASE
            WHEN dependency.classid = 'pg_constraint'::regclass
                THEN pg_get_constraintdef(constraint_row.oid, TRUE)
            WHEN dependency.classid = 'pg_class'::regclass
                 AND dependent_relation.relkind IN ('i', 'I')
                THEN pg_get_indexdef(dependent_relation.oid)
            WHEN dependency.classid = 'pg_class'::regclass
                 AND dependent_relation.relkind IN ('v', 'm')
                THEN pg_get_viewdef(dependent_relation.oid, TRUE)
            WHEN dependency.classid = 'pg_rewrite'::regclass
                THEN pg_get_ruledef(rewrite_row.oid, TRUE)
            WHEN dependency.classid = 'pg_attrdef'::regclass
                THEN pg_get_expr(
                    default_row.adbin,
                    default_row.adrelid,
                    TRUE
                )
            WHEN dependency.classid = 'pg_trigger'::regclass
                THEN pg_get_triggerdef(trigger_row.oid, TRUE)
            WHEN dependency.classid = 'pg_proc'::regclass
                THEN 'FUNCTION ' || quote_ident(function_row.proname)
                     || '(' || pg_get_function_identity_arguments(function_row.oid)
                     || ')'
            WHEN dependency.classid = 'pg_type'::regclass
                THEN 'TYPE ' || quote_ident(type_namespace.nspname)
                     || '.' || quote_ident(type_row.typname)
            ELSE dependency.classid::regclass::text
                 || ' object ' || dependency.objid::text
        END AS object_definition,
        constraint_namespace.nspname AS constraint_table_schema,
        constraint_relation.relname AS constraint_table_name,
        ARRAY(
            SELECT constrained_attribute.attname
            FROM unnest(constraint_row.conkey) WITH ORDINALITY
                 AS constrained_key(attnum, position)
            JOIN pg_attribute AS constrained_attribute
              ON constrained_attribute.attrelid = constraint_row.conrelid
             AND constrained_attribute.attnum = constrained_key.attnum
            ORDER BY constrained_key.position
        ) AS constrained_columns,
        COALESCE(
            constraint_row.conrelid = referenced_relation.oid
            AND cardinality(constraint_row.conkey) = 1
            AND constraint_row.conkey[1] = referenced_attribute.attnum,
            FALSE
        ) AS constrains_exact_target_column,
        referenced_attribute.attnotnull AS target_column_not_null,
        COALESCE(
            constraint_row.convalidated
            AND constraint_row.conenforced
            AND constraint_row.conislocal
            AND constraint_row.coninhcount = 0
            AND NOT constraint_row.connoinherit
            AND constraint_row.conparentid = 0,
            FALSE
        ) AS standard_local_constraint
    FROM pg_depend AS dependency
    JOIN pg_class AS referenced_relation
      ON referenced_relation.oid = dependency.refobjid
    JOIN pg_namespace AS referenced_namespace
      ON referenced_namespace.oid = referenced_relation.relnamespace
    JOIN pg_attribute AS referenced_attribute
      ON referenced_attribute.attrelid = referenced_relation.oid
     AND referenced_attribute.attnum = dependency.refobjsubid
    LEFT JOIN pg_constraint AS constraint_row
      ON dependency.classid = 'pg_constraint'::regclass
     AND constraint_row.oid = dependency.objid
    LEFT JOIN pg_class AS constraint_relation
      ON constraint_relation.oid = constraint_row.conrelid
    LEFT JOIN pg_namespace AS constraint_namespace
      ON constraint_namespace.oid = constraint_relation.relnamespace
    LEFT JOIN pg_class AS dependent_relation
      ON dependency.classid = 'pg_class'::regclass
     AND dependent_relation.oid = dependency.objid
    LEFT JOIN pg_namespace AS dependent_namespace
      ON dependent_namespace.oid = dependent_relation.relnamespace
    LEFT JOIN pg_index AS dependent_index
      ON dependent_index.indexrelid = dependent_relation.oid
    LEFT JOIN pg_rewrite AS rewrite_row
      ON dependency.classid = 'pg_rewrite'::regclass
     AND rewrite_row.oid = dependency.objid
    LEFT JOIN pg_class AS rewrite_relation
      ON rewrite_relation.oid = rewrite_row.ev_class
    LEFT JOIN pg_namespace AS rewrite_namespace
      ON rewrite_namespace.oid = rewrite_relation.relnamespace
    LEFT JOIN pg_attrdef AS default_row
      ON dependency.classid = 'pg_attrdef'::regclass
     AND default_row.oid = dependency.objid
    LEFT JOIN pg_class AS default_relation
      ON default_relation.oid = default_row.adrelid
    LEFT JOIN pg_namespace AS default_namespace
      ON default_namespace.oid = default_relation.relnamespace
    LEFT JOIN pg_attribute AS default_attribute
      ON default_attribute.attrelid = default_row.adrelid
     AND default_attribute.attnum = default_row.adnum
    LEFT JOIN pg_trigger AS trigger_row
      ON dependency.classid = 'pg_trigger'::regclass
     AND trigger_row.oid = dependency.objid
    LEFT JOIN pg_class AS trigger_relation
      ON trigger_relation.oid = trigger_row.tgrelid
    LEFT JOIN pg_namespace AS trigger_namespace
      ON trigger_namespace.oid = trigger_relation.relnamespace
    LEFT JOIN pg_proc AS function_row
      ON dependency.classid = 'pg_proc'::regclass
     AND function_row.oid = dependency.objid
    LEFT JOIN pg_namespace AS function_namespace
      ON function_namespace.oid = function_row.pronamespace
    LEFT JOIN pg_type AS type_row
      ON dependency.classid = 'pg_type'::regclass
     AND type_row.oid = dependency.objid
    LEFT JOIN pg_namespace AS type_namespace
      ON type_namespace.oid = type_row.typnamespace
    WHERE referenced_namespace.nspname = 'public'
      AND dependency.refclassid = 'pg_class'::regclass
      AND referenced_relation.relname = %s
      AND referenced_attribute.attname = %s
    ORDER BY object_class, object_schema, object_name, dependency.objid
"""


class ReconciliationFailure(Exception):
    def __init__(self, stage: str, safe_code: str, cause: BaseException | None = None):
        super().__init__(safe_code)
        self.stage = stage
        self.safe_code = safe_code
        self.cause = cause


@dataclass(frozen=True)
class DependencyDiagnostic:
    object_class: str
    object_type: str
    schema: str
    object_name: str
    constraint_type: str | None
    index_type: str | None
    dependency_code: str
    dependency_type: str
    automatically_created: bool | None
    definition: str
    constraint_table_schema: str | None
    constraint_table_name: str | None
    constrained_columns: tuple[str, ...]
    constrains_exact_target_column: bool
    target_column_not_null: bool
    standard_local_constraint: bool


_SQL_LITERAL = "<redacted_literal>"
_MAX_DIAGNOSTIC_TEXT = 500
_URI_CREDENTIALS = re.compile(
    r"(?i)\b([a-z][a-z0-9+.-]*://)([^\s/@]+(?::[^\s/@]*)?)@"
)
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key)\b"
    r"\s*(?:=|=>|:)\s*[^\s,;)]+"
)


def sanitize_catalog_definition(value: object | None) -> str:
    """Redact literals/comments while retaining catalog structure for diagnosis."""

    if value is None:
        return "<unavailable>"
    text = str(value)
    output: list[str] = []
    position = 0
    while position < len(text):
        if text.startswith("--", position):
            newline = text.find("\n", position + 2)
            output.append(" <redacted_comment> ")
            position = len(text) if newline < 0 else newline + 1
            continue
        if text.startswith("/*", position):
            end = text.find("*/", position + 2)
            output.append(" <redacted_comment> ")
            position = len(text) if end < 0 else end + 2
            continue
        if text[position] == "'":
            position += 1
            while position < len(text):
                if text[position] != "'":
                    position += 1
                    continue
                if position + 1 < len(text) and text[position + 1] == "'":
                    position += 2
                    continue
                position += 1
                break
            output.append(_SQL_LITERAL)
            continue
        if text[position] == "$":
            delimiter_match = re.match(
                r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$",
                text[position:],
            )
            if delimiter_match:
                delimiter = delimiter_match.group(0)
                closing = text.find(delimiter, position + len(delimiter))
                output.append(_SQL_LITERAL)
                position = (
                    len(text) if closing < 0 else closing + len(delimiter)
                )
                continue
        output.append(text[position])
        position += 1

    sanitized = "".join(output)
    sanitized = _URI_CREDENTIALS.sub(r"\1<redacted_credentials>@", sanitized)
    sanitized = _SENSITIVE_ASSIGNMENT.sub(r"\1=<redacted_value>", sanitized)
    sanitized = " ".join(sanitized.split())
    if len(sanitized) > _MAX_DIAGNOSTIC_TEXT:
        sanitized = sanitized[: _MAX_DIAGNOSTIC_TEXT - 15] + "...<truncated>"
    return sanitized or "<empty>"


def _dependency_type_name(dependency_type: str) -> str:
    return {
        "a": "AUTOMATIC",
        "e": "EXTENSION",
        "i": "INTERNAL",
        "n": "NORMAL",
        "p": "PINNED",
        "x": "AUTO_EXTENSION",
    }.get(dependency_type, "UNKNOWN")


def _automatically_created(dependency_type: str) -> bool | None:
    if dependency_type in {"a", "i"}:
        return True
    if dependency_type == "n":
        return False
    return None


def dependency_diagnostic_from_row(row: Sequence[object]) -> DependencyDiagnostic:
    dependency_type = str(row[6])
    return DependencyDiagnostic(
        object_class=sanitize_catalog_definition(row[0]),
        object_type=sanitize_catalog_definition(row[1]),
        schema=sanitize_catalog_definition(row[2]),
        object_name=sanitize_catalog_definition(row[3]),
        constraint_type=(
            sanitize_catalog_definition(row[4]) if row[4] is not None else None
        ),
        index_type=(
            sanitize_catalog_definition(row[5]) if row[5] is not None else None
        ),
        dependency_code=dependency_type,
        dependency_type=_dependency_type_name(dependency_type),
        automatically_created=_automatically_created(dependency_type),
        definition=sanitize_catalog_definition(row[7]),
        constraint_table_schema=(
            sanitize_catalog_definition(row[8]) if row[8] is not None else None
        ),
        constraint_table_name=(
            sanitize_catalog_definition(row[9]) if row[9] is not None else None
        ),
        constrained_columns=tuple(
            sanitize_catalog_definition(column) for column in (row[10] or ())
        ),
        constrains_exact_target_column=bool(row[11]),
        target_column_not_null=bool(row[12]),
        standard_local_constraint=bool(row[13]),
    )


def is_expected_automatic_not_null_dependency(
    table_name: str,
    column_name: str,
    dependency: DependencyDiagnostic,
) -> bool:
    target = (table_name, column_name)
    baseline_column = BASELINE_COLUMNS.get(table_name, {}).get(column_name)
    baseline_requires_not_null = (
        baseline_column is not None and baseline_column[1] is False
    )
    return (
        target in AUTOMATIC_NOT_NULL_DEPENDENCY_ALLOWANCE
        and baseline_requires_not_null
        and dependency.object_class == "pg_constraint"
        and dependency.object_type == "constraint"
        and dependency.schema == "public"
        and dependency.constraint_type == "NOT_NULL"
        and dependency.index_type is None
        and dependency.dependency_code == "a"
        and dependency.automatically_created is True
        and dependency.constraint_table_schema == "public"
        and dependency.constraint_table_name == table_name
        and dependency.constrained_columns == (column_name,)
        and dependency.constrains_exact_target_column
        and dependency.target_column_not_null
        and dependency.standard_local_constraint
    )


def unexpected_column_dependencies(
    table_name: str,
    column_name: str,
    dependencies: Sequence[DependencyDiagnostic],
) -> list[DependencyDiagnostic]:
    if len(dependencies) == 1 and is_expected_automatic_not_null_dependency(
        table_name,
        column_name,
        dependencies[0],
    ):
        return []
    return list(dependencies)


def inspect_column_dependencies(
    connection,
    table_name: str,
    column_name: str,
) -> list[DependencyDiagnostic]:
    rows = connection.execute(
        DEPENDENCY_QUERY,
        (table_name, column_name),
    ).fetchall()
    return [dependency_diagnostic_from_row(row) for row in rows]


def print_dependency_diagnostics(
    table_name: str,
    column_name: str,
    dependencies: Sequence[DependencyDiagnostic],
) -> None:
    safe_target = sanitize_catalog_definition(f"{table_name}.{column_name}")
    print(f"DEPENDENCY_TARGET={safe_target}")
    print(f"UNEXPECTED_DEPENDENCY_COUNT={len(dependencies)}")
    for position, dependency in enumerate(dependencies, start=1):
        prefix = f"UNEXPECTED_DEPENDENCY[{position}]"
        print(f"{prefix}.OBJECT_CLASS={dependency.object_class}")
        print(f"{prefix}.OBJECT_TYPE={dependency.object_type}")
        print(f"{prefix}.SCHEMA={dependency.schema}")
        print(f"{prefix}.OBJECT_NAME={dependency.object_name}")
        print(
            f"{prefix}.CONSTRAINT_TYPE="
            f"{dependency.constraint_type or '<not_applicable>'}"
        )
        print(
            f"{prefix}.INDEX_TYPE="
            f"{dependency.index_type or '<not_applicable>'}"
        )
        print(f"{prefix}.DEPENDENCY_TYPE={dependency.dependency_type}")
        automatic = dependency.automatically_created
        automatic_text = "UNKNOWN" if automatic is None else ("YES" if automatic else "NO")
        print(f"{prefix}.AUTOMATICALLY_CREATED={automatic_text}")
        print(
            f"{prefix}.CONSTRAINT_TABLE="
            f"{dependency.constraint_table_schema or '<not_applicable>'}."
            f"{dependency.constraint_table_name or '<not_applicable>'}"
        )
        constrained_columns = (
            ",".join(dependency.constrained_columns)
            if dependency.constrained_columns
            else "<not_applicable>"
        )
        print(f"{prefix}.CONSTRAINED_COLUMNS={constrained_columns}")
        print(
            f"{prefix}.EXACT_TARGET_COLUMN="
            f"{'YES' if dependency.constrains_exact_target_column else 'NO'}"
        )
        print(
            f"{prefix}.TARGET_COLUMN_NOT_NULL="
            f"{'YES' if dependency.target_column_not_null else 'NO'}"
        )
        print(f"{prefix}.DEFINITION={dependency.definition}")


EXPECTED_STRUCTURAL_DIFFERENCES = (
    "nullability learning_item_key_points.learning_item_id:"
    "expected=True,actual=False",
    "type media.type:expected=ENUM(media_type_enum),actual=VARCHAR(20)",
    "type questions.correct_option:expected=VARCHAR(1),actual=CHARACTER",
    "extra column user_attempts.question_order",
    "extra column user_attempts.time_taken_seconds",
    "type user_attempts.selected_option:"
    "expected=ENUM(answer_option_enum),actual=CHARACTER",
    "default user_label_mastery.correct_attempts:expected=None,actual=0",
    "default user_label_mastery.mastery_score:expected=None,actual=50",
    "default user_label_mastery.total_attempts:expected=None,actual=0",
    "default user_learning_item_mastery.correct_attempts:"
    "expected=None,actual=0",
    "default user_learning_item_mastery.mastery_score:expected=None,actual=50",
    "default user_learning_item_mastery.total_attempts:expected=None,actual=0",
    "default user_sessions.is_active:expected=None,actual=true",
    "extra unique constraint user_attempts('session_id', 'question_id')",
    "missing foreign key ('learning_item_key_points', ('learning_item_id',), "
    "'learning_item', ('id',), 'NO ACTION')",
    "extra foreign key ('learning_item_key_points', ('learning_item_id',), "
    "'learning_item', ('id',), 'CASCADE')",
    "missing foreign key ('user_sessions', ('user_id',), 'users', ('id',), "
    "'NO ACTION')",
    "extra foreign key ('user_sessions', ('user_id',), 'users', ('id',), "
    "'CASCADE')",
    "missing index ('label', ('id',), False, None)",
    "missing index ('learning_item', ('id',), False, None)",
    "missing index ('learning_item_label', ('id',), False, None)",
    "missing index ('media', ('id',), False, None)",
    "missing index ('questions', ('id',), False, None)",
    "missing index ('revision_session_questions', ('id',), False, None)",
    "missing index ('revision_sessions', ('id',), False, None)",
    "missing index ('user_attempts', ('id',), False, None)",
    "missing index ('user_label_mastery', ('id',), False, None)",
    "missing index ('user_learning_item_mastery', ('id',), False, None)",
    "missing index ('user_sessions', ('id',), False, None)",
    "missing index ('users', ('id',), False, None)",
    "enum answer_option_enum:expected=('A', 'B', 'C', 'D'),actual=None",
    "enum media_type_enum:expected=('image', 'video', 'pdf'),actual=None",
)

EXPECTED_NAMING_DIFFERENCES = (
    "unique constraint revision_session_questions('session_id', 'question_id'):"
    "expected=uq_revision_session_question,actual=uq_session_question",
    "unique constraint user_label_mastery('user_id', 'label_id'):"
    "expected=uq_user_label_mastery,actual=uq_user_label",
    "unique constraint user_learning_item_mastery"
    "('user_id', 'learning_item_id'):"
    "expected=uq_user_learning_item_mastery,actual=uq_user_learning_item",
)

assert len(EXPECTED_STRUCTURAL_DIFFERENCES) == 32
assert len(EXPECTED_NAMING_DIFFERENCES) == 3
assert set(EXPECTED_LEGACY_TABLES) == set(BASELINE_COLUMNS)


DDL_MANIFEST = (
    (
        "temporarily relax key-point ownership nullability",
        "ALTER TABLE public.learning_item_key_points "
        "ALTER COLUMN learning_item_id DROP NOT NULL",
    ),
    (
        "replace key-point cascade foreign key",
        "ALTER TABLE public.learning_item_key_points "
        "DROP CONSTRAINT {key_point_fk}",
    ),
    (
        "create baseline key-point foreign key",
        "ALTER TABLE public.learning_item_key_points "
        "ADD CONSTRAINT {key_point_fk} FOREIGN KEY (learning_item_id) "
        "REFERENCES public.learning_item (id)",
    ),
    (
        "replace user-session cascade foreign key",
        "ALTER TABLE public.user_sessions DROP CONSTRAINT {user_session_fk}",
    ),
    (
        "create baseline user-session foreign key",
        "ALTER TABLE public.user_sessions ADD CONSTRAINT {user_session_fk} "
        "FOREIGN KEY (user_id) REFERENCES public.users (id)",
    ),
    (
        "remove user-session active server default",
        "ALTER TABLE public.user_sessions ALTER COLUMN is_active DROP DEFAULT",
    ),
    (
        "create answer option enum",
        "CREATE TYPE public.answer_option_enum AS ENUM ('A', 'B', 'C', 'D')",
    ),
    (
        "convert selected answer to enum",
        "ALTER TABLE public.user_attempts ALTER COLUMN selected_option "
        "TYPE public.answer_option_enum "
        "USING BTRIM(selected_option)::public.answer_option_enum",
    ),
    (
        "create media type enum",
        "CREATE TYPE public.media_type_enum AS ENUM ('image', 'video', 'pdf')",
    ),
    (
        "convert media type to enum",
        "ALTER TABLE public.media ALTER COLUMN type TYPE public.media_type_enum "
        "USING type::text::public.media_type_enum",
    ),
    (
        "normalize question correct option type",
        "ALTER TABLE public.questions ALTER COLUMN correct_option TYPE VARCHAR(1) "
        "USING BTRIM(correct_option)::VARCHAR(1)",
    ),
    (
        "remove empty legacy attempt order",
        "ALTER TABLE public.user_attempts DROP COLUMN question_order",
    ),
    (
        "remove colliding empty legacy attempt time",
        "ALTER TABLE public.user_attempts DROP COLUMN time_taken_seconds",
    ),
    (
        "remove legacy live-question attempt uniqueness",
        "ALTER TABLE public.user_attempts DROP CONSTRAINT {attempt_unique}",
    ),
    (
        "remove label mastery correct default",
        "ALTER TABLE public.user_label_mastery "
        "ALTER COLUMN correct_attempts DROP DEFAULT",
    ),
    (
        "remove label mastery score default",
        "ALTER TABLE public.user_label_mastery "
        "ALTER COLUMN mastery_score DROP DEFAULT",
    ),
    (
        "remove label mastery attempt default",
        "ALTER TABLE public.user_label_mastery "
        "ALTER COLUMN total_attempts DROP DEFAULT",
    ),
    (
        "remove item mastery correct default",
        "ALTER TABLE public.user_learning_item_mastery "
        "ALTER COLUMN correct_attempts DROP DEFAULT",
    ),
    (
        "remove item mastery score default",
        "ALTER TABLE public.user_learning_item_mastery "
        "ALTER COLUMN mastery_score DROP DEFAULT",
    ),
    (
        "remove item mastery attempt default",
        "ALTER TABLE public.user_learning_item_mastery "
        "ALTER COLUMN total_attempts DROP DEFAULT",
    ),
    *tuple(
        (
            f"create baseline ID index for {table_name}",
            f"CREATE INDEX ix_{table_name}_id ON public.{table_name} (id)",
        )
        for table_name in EXPECTED_LEGACY_TABLES
        if table_name != "learning_item_key_points"
    ),
    (
        "rename revision-session question uniqueness",
        "ALTER TABLE public.revision_session_questions "
        "RENAME CONSTRAINT {session_question_unique} "
        "TO uq_revision_session_question",
    ),
    (
        "rename label mastery uniqueness",
        "ALTER TABLE public.user_label_mastery "
        "RENAME CONSTRAINT {label_mastery_unique} TO uq_user_label_mastery",
    ),
    (
        "rename item mastery uniqueness",
        "ALTER TABLE public.user_learning_item_mastery "
        "RENAME CONSTRAINT {item_mastery_unique} "
        "TO uq_user_learning_item_mastery",
    ),
)


def manifest_sql_text() -> str:
    return "\n".join(statement for _operation, statement in DDL_MANIFEST)


def _case_insensitive_value(
    mapping: Mapping[str, object],
    name: str,
) -> object | None:
    expected = name.casefold()
    for key, value in mapping.items():
        if key.casefold() == expected:
            return value
    return None


def _adoption_url(environ: Mapping[str, str] | None = None) -> str:
    values = environ if environ is not None else os.environ
    value = _case_insensitive_value(values, TARGET_ENVIRONMENT_VARIABLE)
    if not value:
        raise ReconciliationFailure(
            TARGET_VALIDATION,
            "ADOPTION_REHEARSAL_TARGET_REQUIRED",
        )
    return str(value)


def _parse_postgresql_url(value: str, variable_name: str):
    try:
        parsed = make_url(value)
    except ArgumentError as exc:
        raise ReconciliationFailure(
            TARGET_VALIDATION,
            f"MALFORMED_{variable_name}",
            exc,
        ) from None
    if parsed.get_backend_name() != "postgresql" or not parsed.host or not parsed.database:
        raise ReconciliationFailure(
            TARGET_VALIDATION,
            f"MALFORMED_{variable_name}",
        )
    return parsed


def _database_identity(parsed_url) -> tuple[str, int, str]:
    host = (parsed_url.host or "").casefold().rstrip(".")
    if host in {"localhost", "127.0.0.1", "::1"}:
        host = "loopback"
    return host, parsed_url.port or 5432, (parsed_url.database or "").casefold()


def _is_pooled_neon_host(host: str) -> bool:
    normalized = host.casefold().rstrip(".")
    return normalized.endswith(".neon.tech") and any(
        label.endswith("-pooler") or label == "pooler"
        for label in normalized.split(".")
    )


def _configured_collision_values(
    environ: Mapping[str, str] | None = None,
    env_file: Path | None = None,
) -> dict[str, str]:
    values = environ if environ is not None else os.environ
    file_values = dotenv_values(env_file or BACKEND_DIR / ".env")
    configured: dict[str, str] = {}
    for variable_name in COLLISION_VARIABLES:
        value = _case_insensitive_value(values, variable_name)
        if value is None:
            value = _case_insensitive_value(file_values, variable_name)
        if value:
            configured[variable_name] = str(value)
    return configured


def validate_target(
    adoption_url: str,
    *,
    environ: Mapping[str, str] | None = None,
    env_file: Path | None = None,
):
    parsed = _parse_postgresql_url(adoption_url, TARGET_ENVIRONMENT_VARIABLE)
    if _is_pooled_neon_host(str(parsed.host)):
        raise ReconciliationFailure(TARGET_VALIDATION, "POOLED_NEON_TARGET_REFUSED")

    target_identity = _database_identity(parsed)
    for variable_name, value in _configured_collision_values(
        environ,
        env_file,
    ).items():
        candidate = _parse_postgresql_url(value, variable_name)
        if _database_identity(candidate) == target_identity:
            raise ReconciliationFailure(
                TARGET_VALIDATION,
                f"TARGET_COLLIDES_WITH_{variable_name}",
            )
    return parsed


def validate_mode(args: argparse.Namespace) -> None:
    if args.apply and not args.confirm_rehearsal_reconciliation:
        raise ReconciliationFailure(
            TARGET_VALIDATION,
            "EXPLICIT_REHEARSAL_CONFIRMATION_REQUIRED",
        )


def _target_identity_hash(parsed_url) -> str:
    identity = "|".join(str(part) for part in _database_identity(parsed_url))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _snapshot_database(connection, target_hash: str) -> dict[str, object]:
    table_snapshot: dict[str, dict[str, object]] = {}
    for table_name in EXPECTED_LEGACY_TABLES:
        statement = sql.SQL(
            "SELECT COUNT(*), "
            "MD5(COALESCE(STRING_AGG(id::text, ',' ORDER BY id), '')) "
            "FROM public.{}"
        ).format(sql.Identifier(table_name))
        row = connection.execute(statement).fetchone()
        if row is None:
            raise ReconciliationFailure(SNAPSHOT, "TABLE_SIGNATURE_UNAVAILABLE")
        table_snapshot[table_name] = {
            "row_count": int(row[0]),
            "id_signature": str(row[1]),
        }

    sequence_rows = connection.execute(
        """
        SELECT
            sequence_relation.relname,
            owner_relation.relname,
            owner_attribute.attname,
            sequence_view.last_value
        FROM pg_class AS sequence_relation
        JOIN pg_namespace AS sequence_namespace
          ON sequence_namespace.oid = sequence_relation.relnamespace
        JOIN pg_depend AS dependency
          ON dependency.classid = 'pg_class'::regclass
         AND dependency.objid = sequence_relation.oid
         AND dependency.deptype IN ('a', 'i')
        JOIN pg_class AS owner_relation
          ON owner_relation.oid = dependency.refobjid
        JOIN pg_attribute AS owner_attribute
          ON owner_attribute.attrelid = owner_relation.oid
         AND owner_attribute.attnum = dependency.refobjsubid
        LEFT JOIN pg_sequences AS sequence_view
          ON sequence_view.schemaname = sequence_namespace.nspname
         AND sequence_view.sequencename = sequence_relation.relname
        WHERE sequence_namespace.nspname = 'public'
          AND sequence_relation.relkind = 'S'
        ORDER BY sequence_relation.relname
        """
    ).fetchall()
    sequences = [
        {
            "sequence": row[0],
            "owner_table": row[1],
            "owner_column": row[2],
            "last_value": row[3],
        }
        for row in sequence_rows
    ]
    return {
        "format": SNAPSHOT_FORMAT,
        "target_identity_hash": target_hash,
        "tables": table_snapshot,
        "sequences": sequences,
    }


def _write_snapshot(path: Path, snapshot: dict[str, object]) -> None:
    if path.exists():
        raise ReconciliationFailure(SNAPSHOT, "SNAPSHOT_FILE_ALREADY_EXISTS")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as snapshot_file:
            json.dump(snapshot, snapshot_file, indent=2, sort_keys=True)
            snapshot_file.write("\n")
    except Exception as exc:
        raise ReconciliationFailure(SNAPSHOT, "SNAPSHOT_WRITE_FAILED", exc) from None


def load_snapshot(path: Path, target_hash: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReconciliationFailure(SNAPSHOT, "SNAPSHOT_READ_FAILED", exc) from None
    if not isinstance(payload, dict) or payload.get("format") != SNAPSHOT_FORMAT:
        raise ReconciliationFailure(SNAPSHOT, "SNAPSHOT_FORMAT_INVALID")
    if payload.get("target_identity_hash") != target_hash:
        raise ReconciliationFailure(SNAPSHOT, "SNAPSHOT_TARGET_MISMATCH")
    return payload


def _require_zero(
    connection,
    code: str,
    statement,
    parameters: object | None = None,
) -> None:
    row = connection.execute(statement, parameters).fetchone()
    if row is None or int(row[0]) != 0:
        raise ReconciliationFailure(PREFLIGHT, code)


def _assert_exact_legacy_schema(connection) -> None:
    tables, columns = schema_metadata(connection)
    if "alembic_version" in tables:
        raise ReconciliationFailure(PREFLIGHT, "ALEMBIC_VERSION_MUST_BE_ABSENT")
    if tables != set(EXPECTED_LEGACY_TABLES):
        raise ReconciliationFailure(PREFLIGHT, "LEGACY_TABLE_SHAPE_MISMATCH")

    structural, naming, blockers = baseline_schema_comparison(
        connection,
        tables,
        columns,
    )
    if Counter(structural) != Counter(EXPECTED_STRUCTURAL_DIFFERENCES):
        raise ReconciliationFailure(PREFLIGHT, "UNEXPECTED_STRUCTURAL_DIFFERENCES")
    if Counter(naming) != Counter(EXPECTED_NAMING_DIFFERENCES):
        raise ReconciliationFailure(PREFLIGHT, "UNEXPECTED_NAMING_DIFFERENCES")
    if blockers:
        raise ReconciliationFailure(PREFLIGHT, "UPGRADE_NAME_BLOCKERS_PRESENT")


def _assert_baseline_schema(connection) -> None:
    tables, columns = schema_metadata(connection)
    if "alembic_version" in tables:
        raise ReconciliationFailure(
            POST_RECONCILIATION,
            "ALEMBIC_VERSION_CREATED_UNEXPECTEDLY",
        )
    structural, naming, blockers = baseline_schema_comparison(
        connection,
        tables,
        columns,
    )
    if structural or naming or blockers:
        raise ReconciliationFailure(
            POST_RECONCILIATION,
            "BASELINE_RECONCILIATION_INCOMPLETE",
        )


def _assert_converted_columns_remain_not_null(connection) -> None:
    _tables, columns = schema_metadata(connection)
    invalid = [
        f"{table_name}.{column_name}"
        for table_name, column_name in sorted(
            AUTOMATIC_NOT_NULL_DEPENDENCY_ALLOWANCE
        )
        if table_name not in columns
        or column_name not in columns[table_name]
        or columns[table_name][column_name]["nullable"] is not False
    ]
    if invalid:
        raise ReconciliationFailure(
            POST_RECONCILIATION,
            "TYPE_CONVERSION_NULLABILITY_CHANGED",
        )


def _orphan_guard_statement(
    child_table: str,
    child_columns: Sequence[str],
    parent_table: str,
    parent_columns: Sequence[str],
):
    join_parts = [
        sql.SQL("parent.{} = child.{}").format(
            sql.Identifier(parent_column),
            sql.Identifier(child_column),
        )
        for child_column, parent_column in zip(
            child_columns,
            parent_columns,
            strict=True,
        )
    ]
    nonnull_parts = [
        sql.SQL("child.{} IS NOT NULL").format(sql.Identifier(column))
        for column in child_columns
    ]
    return sql.SQL(
        "SELECT COUNT(*) FROM public.{} AS child "
        "LEFT JOIN public.{} AS parent ON {} "
        "WHERE ({}) AND parent.{} IS NULL"
    ).format(
        sql.Identifier(child_table),
        sql.Identifier(parent_table),
        sql.SQL(" AND ").join(join_parts),
        sql.SQL(" OR ").join(nonnull_parts),
        sql.Identifier(parent_columns[0]),
    )


def _duplicate_guard_statement(
    table_name: str,
    columns: Sequence[str],
):
    identifiers = [sql.Identifier(column) for column in columns]
    nonnull = sql.SQL(" AND ").join(
        sql.SQL("{} IS NOT NULL").format(identifier)
        for identifier in identifiers
    )
    return sql.SQL(
        "SELECT COUNT(*) FROM ("
        "SELECT {columns} FROM public.{table} "
        "WHERE {nonnull} GROUP BY {columns} HAVING COUNT(*) > 1"
        ") AS duplicate_groups"
    ).format(
        columns=sql.SQL(", ").join(identifiers),
        table=sql.Identifier(table_name),
        nonnull=nonnull,
    )


def _run_preflight_guards(connection) -> None:
    _assert_exact_legacy_schema(connection)
    _require_zero(
        connection,
        "LEGACY_ATTEMPTS_PRESENT",
        "SELECT COUNT(*) FROM public.user_attempts",
    )
    _require_zero(
        connection,
        "LEGACY_SESSIONS_PRESENT",
        "SELECT COUNT(*) FROM public.revision_sessions",
    )
    _require_zero(
        connection,
        "ENDED_LEGACY_SESSIONS_PRESENT",
        "SELECT COUNT(*) FROM public.revision_sessions WHERE ended_at IS NOT NULL",
    )
    _require_zero(
        connection,
        "INVALID_MEDIA_ENUM_VALUES",
        """
        SELECT COUNT(*) FROM public.media
        WHERE type IS NULL OR type::text NOT IN ('image', 'video', 'pdf')
        """,
    )
    _require_zero(
        connection,
        "INVALID_QUESTION_ANSWER_VALUES",
        """
        SELECT COUNT(*) FROM public.questions
        WHERE correct_option IS NULL
           OR LENGTH(BTRIM(correct_option)) <> 1
           OR UPPER(BTRIM(correct_option))
              NOT IN ('0', '1', '2', '3', 'A', 'B', 'C', 'D')
        """,
    )
    _require_zero(
        connection,
        "INVALID_SELECTED_OPTION_ENUM_VALUES",
        """
        SELECT COUNT(*) FROM public.user_attempts
        WHERE selected_option IS NULL
           OR UPPER(BTRIM(selected_option)) NOT IN ('A', 'B', 'C', 'D')
        """,
    )
    _require_zero(
        connection,
        "G0002_INVALID_SESSION_BACKFILL",
        """
        SELECT COUNT(*)
        FROM (
            SELECT session.id, UPPER(session.quiz_type) AS strategy,
                   COUNT(selected.id) AS question_count
            FROM public.revision_sessions AS session
            LEFT JOIN public.revision_session_questions AS selected
              ON selected.session_id = session.id
            GROUP BY session.id, session.quiz_type
        ) AS candidate
        WHERE strategy IS NULL
           OR strategy NOT IN ('RANDOM', 'LABEL')
           OR question_count NOT BETWEEN 1 AND 50
        """,
    )
    _require_zero(
        connection,
        "G0002_DUPLICATE_ORDER_GROUPS",
        """
        SELECT COUNT(*) FROM (
            SELECT session_id, question_order
            FROM public.revision_session_questions
            GROUP BY session_id, question_order
            HAVING COUNT(*) > 1
        ) AS duplicates
        """,
    )
    _require_zero(
        connection,
        "G0002_INCOMPLETE_SNAPSHOT_SOURCES",
        """
        SELECT COUNT(*)
        FROM public.revision_session_questions AS selected
        LEFT JOIN public.questions AS question ON question.id = selected.question_id
        LEFT JOIN public.learning_item AS item ON item.id = question.learning_item_id
        WHERE question.id IS NULL
           OR item.id IS NULL
           OR item.title IS NULL
           OR question.question_text IS NULL
           OR question.option_a IS NULL
           OR question.option_b IS NULL
           OR question.option_c IS NULL
           OR question.option_d IS NULL
           OR question.correct_option IS NULL
           OR question.difficulty IS NULL
           OR question.expected_time_seconds IS NULL
        """,
    )

    for table_name in ("user_label_mastery", "user_learning_item_mastery"):
        _require_zero(
            connection,
            f"INVALID_MASTERY_VALUES_{table_name.upper()}",
            sql.SQL(
                "SELECT COUNT(*) FROM public.{} "
                "WHERE (mastery_score IS NOT NULL "
                "AND mastery_score NOT BETWEEN 0 AND 100) "
                "OR (total_attempts IS NOT NULL AND total_attempts < 0) "
                "OR (correct_attempts IS NOT NULL AND correct_attempts < 0) "
                "OR COALESCE(correct_attempts, 0) > COALESCE(total_attempts, 0)"
            ).format(sql.Identifier(table_name)),
        )

    unique_value_guards = (
        ("users", ("email",)),
        ("learning_item_label", ("learning_item_id", "label_id")),
        ("user_sessions", ("session_id",)),
        (
            "revision_session_questions",
            ("session_id", "question_id"),
        ),
        ("user_label_mastery", ("user_id", "label_id")),
        (
            "user_learning_item_mastery",
            ("user_id", "learning_item_id"),
        ),
        ("user_attempts", ("session_id", "question_id")),
    )
    for table_name, columns in unique_value_guards:
        _require_zero(
            connection,
            f"DUPLICATE_VALUES_{table_name.upper()}_{'_'.join(columns).upper()}",
            _duplicate_guard_statement(table_name, columns),
        )

    orphan_structures = {
        (child, child_columns, parent, parent_columns)
        for child, child_columns, parent, parent_columns, _on_delete in (
            BASELINE_FOREIGN_KEYS
        )
    }
    for child, child_columns, parent, parent_columns in sorted(
        orphan_structures,
        key=repr,
    ):
        _require_zero(
            connection,
            f"ORPHAN_REFERENCE_{child.upper()}_{'_'.join(child_columns).upper()}",
            _orphan_guard_statement(
                child,
                child_columns,
                parent,
                parent_columns,
            ),
        )

    for table_name, column_name in DEPENDENCY_TARGETS:
        dependencies = inspect_column_dependencies(
            connection,
            table_name,
            column_name,
        )
        unexpected = unexpected_column_dependencies(
            table_name,
            column_name,
            dependencies,
        )
        if unexpected:
            print_dependency_diagnostics(table_name, column_name, unexpected)
            raise ReconciliationFailure(
                PREFLIGHT,
                f"UNEXPECTED_DEPENDENCY_{table_name.upper()}_{column_name.upper()}",
            )


def _discover_constraint_names(connection) -> dict[str, str]:
    constraints = _constraint_metadata(connection)

    def one(
        *,
        table: str,
        kind: str,
        columns: tuple[str, ...],
        target_table: str | None = None,
        target_columns: tuple[str, ...] = (),
        on_delete: str | None = None,
    ) -> str:
        matches = [
            row
            for row in constraints
            if row["table"] == table
            and row["kind"] == kind
            and row["columns"] == columns
            and (target_table is None or row["target_table"] == target_table)
            and (not target_columns or row["target_columns"] == target_columns)
            and (on_delete is None or row["on_delete"] == on_delete)
        ]
        if len(matches) != 1 or not isinstance(matches[0]["name"], str):
            raise ReconciliationFailure(PREFLIGHT, "CONSTRAINT_DISCOVERY_MISMATCH")
        return str(matches[0]["name"])

    names = {
        "key_point_fk": one(
            table="learning_item_key_points",
            kind="f",
            columns=("learning_item_id",),
            target_table="learning_item",
            target_columns=("id",),
            on_delete="CASCADE",
        ),
        "user_session_fk": one(
            table="user_sessions",
            kind="f",
            columns=("user_id",),
            target_table="users",
            target_columns=("id",),
            on_delete="CASCADE",
        ),
        "attempt_unique": one(
            table="user_attempts",
            kind="u",
            columns=("session_id", "question_id"),
        ),
        "session_question_unique": one(
            table="revision_session_questions",
            kind="u",
            columns=("session_id", "question_id"),
        ),
        "label_mastery_unique": one(
            table="user_label_mastery",
            kind="u",
            columns=("user_id", "label_id"),
        ),
        "item_mastery_unique": one(
            table="user_learning_item_mastery",
            kind="u",
            columns=("user_id", "learning_item_id"),
        ),
    }
    expected_names = {
        "key_point_fk": "learning_item_key_points_learning_item_id_fkey",
        "user_session_fk": "user_sessions_user_id_fkey",
        "session_question_unique": "uq_session_question",
        "label_mastery_unique": "uq_user_label",
        "item_mastery_unique": "uq_user_learning_item",
    }
    if any(names[key] != value for key, value in expected_names.items()):
        raise ReconciliationFailure(PREFLIGHT, "UNEXPECTED_CONSTRAINT_NAME")
    return names


def _render_ddl_statements(constraint_names: Mapping[str, str]):
    identifier_mapping = {
        key: sql.Identifier(value) for key, value in constraint_names.items()
    }
    return [
        (
            operation,
            sql.SQL(statement).format(**identifier_mapping),
        )
        for operation, statement in DDL_MANIFEST
    ]


def _lock_legacy_tables(connection) -> None:
    table_list = sql.SQL(", ").join(
        sql.SQL("public.{}").format(sql.Identifier(table_name))
        for table_name in EXPECTED_LEGACY_TABLES
    )
    connection.execute(
        sql.SQL("LOCK TABLE {} IN ACCESS EXCLUSIVE MODE").format(table_list)
    )


def _setup_transaction(connection, *, read_only: bool) -> None:
    if read_only:
        connection.execute(
            "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
        )
    else:
        connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
    connection.execute(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'")
    connection.execute(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'")


def _acquire_advisory_lock(connection) -> None:
    connection.execute(
        "SELECT pg_advisory_xact_lock(%s, %s)",
        ADVISORY_LOCK_KEYS,
    )


def run_in_transaction(connection, operation: Callable[[Any], Any]):
    with connection.transaction():
        return operation(connection)


def _dry_run_transaction(
    connection,
    *,
    target_hash: str,
) -> dict[str, object]:
    try:
        _setup_transaction(connection, read_only=True)
    except Exception as exc:
        raise ReconciliationFailure(
            TRANSACTION_SETUP,
            "READ_ONLY_TRANSACTION_SETUP_FAILED",
            exc,
        ) from None
    try:
        _acquire_advisory_lock(connection)
    except Exception as exc:
        raise ReconciliationFailure(
            LOCK_ACQUISITION,
            "ADVISORY_LOCK_FAILED",
            exc,
        ) from None
    try:
        _run_preflight_guards(connection)
        _discover_constraint_names(connection)
    except ReconciliationFailure:
        raise
    except Exception as exc:
        raise ReconciliationFailure(PREFLIGHT, "PREFLIGHT_QUERY_FAILED", exc) from None
    return _snapshot_database(connection, target_hash)


def _apply_transaction(
    connection,
    *,
    target_hash: str,
    expected_snapshot: dict[str, object],
) -> None:
    try:
        _setup_transaction(connection, read_only=False)
        _acquire_advisory_lock(connection)
        _lock_legacy_tables(connection)
    except Exception as exc:
        raise ReconciliationFailure(
            LOCK_ACQUISITION,
            "EXCLUSIVE_LOCK_SETUP_FAILED",
            exc,
        ) from None

    try:
        _run_preflight_guards(connection)
        constraint_names = _discover_constraint_names(connection)
        current_snapshot = _snapshot_database(connection, target_hash)
        if current_snapshot != expected_snapshot:
            raise ReconciliationFailure(SNAPSHOT, "DATABASE_CHANGED_SINCE_DRY_RUN")
    except ReconciliationFailure:
        raise
    except Exception as exc:
        raise ReconciliationFailure(PREFLIGHT, "PREFLIGHT_QUERY_FAILED", exc) from None

    try:
        for _operation, statement in _render_ddl_statements(constraint_names):
            connection.execute(statement)
    except Exception as exc:
        raise ReconciliationFailure(
            RECONCILIATION,
            "RECONCILIATION_DDL_FAILED",
            exc,
        ) from None

    try:
        _assert_baseline_schema(connection)
        _assert_converted_columns_remain_not_null(connection)
        final_snapshot = _snapshot_database(connection, target_hash)
        if final_snapshot != expected_snapshot:
            raise ReconciliationFailure(
                POST_RECONCILIATION,
                "RETAINED_DATA_OR_SEQUENCE_CHANGED",
            )
    except ReconciliationFailure:
        raise
    except Exception as exc:
        raise ReconciliationFailure(
            POST_RECONCILIATION,
            "POST_RECONCILIATION_VERIFICATION_FAILED",
            exc,
        ) from None


def _psycopg_connection_string(parsed_url) -> str:
    return parsed_url.set(drivername="postgresql").render_as_string(
        hide_password=False
    )


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


def print_failure(failure: ReconciliationFailure) -> None:
    cause = failure.cause
    exception_name = type(cause).__name__ if cause is not None else type(failure).__name__
    safe_exception = "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in exception_name
    )
    print("RECONCILIATION_ERROR=FAILED")
    print(f"FAILURE_STAGE={failure.stage}")
    print(f"ERROR_CODE={failure.safe_code}")
    print(f"EXCEPTION_CLASS={safe_exception or 'UNKNOWN'}")
    print(f"SQLSTATE={_sqlstate(cause) or '<unavailable>'}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reconcile the isolated legacy rehearsal schema to Alembic 0001",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-rehearsal-reconciliation", action="store_true")
    parser.add_argument("--snapshot-file", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        validate_mode(args)
        adoption_url = _adoption_url()
        parsed_url = validate_target(adoption_url)
        target_hash = _target_identity_hash(parsed_url)
        expected_snapshot = (
            load_snapshot(args.snapshot_file, target_hash) if args.apply else None
        )
    except ReconciliationFailure as failure:
        print_failure(failure)
        return 2

    try:
        with psycopg.connect(
            _psycopg_connection_string(parsed_url),
            connect_timeout=15,
            autocommit=False,
        ) as connection:
            if args.dry_run:
                snapshot = run_in_transaction(
                    connection,
                    lambda active_connection: _dry_run_transaction(
                        active_connection,
                        target_hash=target_hash,
                    ),
                )
                _write_snapshot(args.snapshot_file, snapshot)
                print("RECONCILIATION_MODE=DRY_RUN")
                print("DATABASE_TRANSACTION=READ_ONLY")
                print("LEGACY_SCHEMA_PREFLIGHT=PASS")
                print("SNAPSHOT_WRITTEN=YES")
            else:
                run_in_transaction(
                    connection,
                    lambda active_connection: _apply_transaction(
                        active_connection,
                        target_hash=target_hash,
                        expected_snapshot=expected_snapshot,
                    ),
                )
                print("RECONCILIATION_MODE=APPLY")
                print("BASELINE_STRUCTURAL_DIFFERENCE_COUNT=0")
                print("BASELINE_NAMING_ONLY_DIFFERENCE_COUNT=0")
                print("BASELINE_UPGRADE_NAME_BLOCKER_COUNT=0")
                print("BASELINE_SAFE_TO_STAMP_0001=YES")
                print("ALEMBIC_VERSION_ABSENT=YES")
                print("RETAINED_DATA_AND_SEQUENCES_MATCH=YES")
    except KeyboardInterrupt:
        print("RECONCILIATION_ERROR=INTERRUPTED")
        return 130
    except ReconciliationFailure as failure:
        print_failure(failure)
        return 2
    except Exception as exc:
        print_failure(
            ReconciliationFailure(CONNECTION, "DATABASE_CONNECTION_FAILED", exc)
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
