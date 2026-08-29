"""Read-only development database migration and schema assessment.

This diagnostic prints schema metadata and aggregate reconciliation counts only.
It never runs migrations or reads application record contents.
"""

from __future__ import annotations

import os
from pathlib import Path
import socket
import sys
from typing import Mapping

from dotenv import dotenv_values
import psycopg
from sqlalchemy.engine import make_url


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.db.base import Base  # noqa: E402
import src.db.models  # noqa: E402, F401


URL_PARSING = "URL_PARSING"
DNS = "DNS"
CONNECTION = "CONNECTION"
READ_ONLY_SETUP = "READ_ONLY_SETUP"
INSPECTION = "INSPECTION"


class InspectionFailure(Exception):
    def __init__(self, stage: str, cause: BaseException) -> None:
        super().__init__(stage)
        self.stage = stage
        self.cause = cause


def _column(
    data_type: str,
    nullable: bool,
    default: str | None = None,
) -> tuple[str, bool, str | None]:
    return data_type, nullable, default


BASELINE_COLUMNS = {
    "users": {
        "id": _column("INTEGER", False, "AUTO_INCREMENT"),
        "username": _column("VARCHAR(100)", False),
        "email": _column("VARCHAR(100)", False),
        "password_hash": _column("VARCHAR(255)", False),
        "created_at": _column("TIMESTAMP", True, "CURRENT_TIMESTAMP"),
    },
    "learning_item": {
        "id": _column("INTEGER", False, "AUTO_INCREMENT"),
        "user_id": _column("INTEGER", False),
        "title": _column("VARCHAR(100)", False),
        "description_text": _column("TEXT", True),
        "theory": _column("TEXT", True),
        "created_at": _column("TIMESTAMP", True, "CURRENT_TIMESTAMP"),
        "updated_at": _column("TIMESTAMP", True, "CURRENT_TIMESTAMP"),
    },
    "learning_item_key_points": {
        "id": _column("INTEGER", False, "AUTO_INCREMENT"),
        "learning_item_id": _column("INTEGER", True),
        "key_point": _column("TEXT", False),
    },
    "label": {
        "id": _column("INTEGER", False, "AUTO_INCREMENT"),
        "user_id": _column("INTEGER", False),
        "label_name": _column("VARCHAR(200)", False),
    },
    "learning_item_label": {
        "id": _column("INTEGER", False, "AUTO_INCREMENT"),
        "learning_item_id": _column("INTEGER", False),
        "label_id": _column("INTEGER", False),
    },
    "questions": {
        "id": _column("INTEGER", False, "AUTO_INCREMENT"),
        "learning_item_id": _column("INTEGER", False),
        "question_text": _column("TEXT", False),
        "option_a": _column("VARCHAR(255)", False),
        "option_b": _column("VARCHAR(255)", False),
        "option_c": _column("VARCHAR(255)", False),
        "option_d": _column("VARCHAR(255)", False),
        "correct_option": _column("VARCHAR(1)", False),
        "explanation": _column("TEXT", True),
        "difficulty": _column("INTEGER", False),
        "expected_time_seconds": _column("INTEGER", False),
        "source": _column("VARCHAR(20)", True),
        "created_at": _column("TIMESTAMP", True, "CURRENT_TIMESTAMP"),
    },
    "revision_sessions": {
        "id": _column("INTEGER", False, "AUTO_INCREMENT"),
        "user_id": _column("INTEGER", False),
        "quiz_type": _column("VARCHAR(20)", False),
        "started_at": _column("TIMESTAMP", True, "CURRENT_TIMESTAMP"),
        "ended_at": _column("TIMESTAMP", True),
    },
    "user_attempts": {
        "id": _column("INTEGER", False, "AUTO_INCREMENT"),
        "user_id": _column("INTEGER", False),
        "question_id": _column("INTEGER", False),
        "session_id": _column("INTEGER", False),
        "selected_option": _column("ENUM(answer_option_enum)", False),
        "is_correct": _column("BOOLEAN", False),
        "attempted_at": _column("TIMESTAMP", True, "CURRENT_TIMESTAMP"),
    },
    "media": {
        "id": _column("INTEGER", False, "AUTO_INCREMENT"),
        "learning_item_id": _column("INTEGER", False),
        "type": _column("ENUM(media_type_enum)", False),
        "url": _column("VARCHAR(500)", False),
        "public_id": _column("VARCHAR(300)", False),
    },
    "user_sessions": {
        "id": _column("INTEGER", False, "AUTO_INCREMENT"),
        "user_id": _column("INTEGER", False),
        "session_id": _column("VARCHAR(255)", False),
        "is_active": _column("BOOLEAN", True),
        "created_at": _column("TIMESTAMP", True, "CURRENT_TIMESTAMP"),
        "expires_at": _column("TIMESTAMP", True),
        "last_used_at": _column("TIMESTAMP", True, "CURRENT_TIMESTAMP"),
    },
    "revision_session_questions": {
        "id": _column("INTEGER", False, "AUTO_INCREMENT"),
        "session_id": _column("INTEGER", False),
        "question_id": _column("INTEGER", False),
        "question_order": _column("INTEGER", False),
    },
    "user_label_mastery": {
        "id": _column("INTEGER", False, "AUTO_INCREMENT"),
        "user_id": _column("INTEGER", False),
        "label_id": _column("INTEGER", False),
        "mastery_score": _column("INTEGER", True),
        "total_attempts": _column("INTEGER", True),
        "correct_attempts": _column("INTEGER", True),
        "last_attempt_at": _column("TIMESTAMP", True),
        "last_reviewed_at": _column("TIMESTAMP", True),
        "next_review_at": _column("TIMESTAMP", True),
    },
    "user_learning_item_mastery": {
        "id": _column("INTEGER", False, "AUTO_INCREMENT"),
        "user_id": _column("INTEGER", False),
        "learning_item_id": _column("INTEGER", False),
        "mastery_score": _column("INTEGER", True),
        "total_attempts": _column("INTEGER", True),
        "correct_attempts": _column("INTEGER", True),
        "last_attempt_at": _column("TIMESTAMP", True),
        "last_reviewed_at": _column("TIMESTAMP", True),
        "next_review_at": _column("TIMESTAMP", True),
    },
}

BASELINE_PRIMARY_KEYS = {
    table_name: (("id",), f"{table_name}_pkey")
    for table_name in BASELINE_COLUMNS
}

BASELINE_UNIQUE_CONSTRAINTS = {
    "users": [(('email',), "users_email_key")],
    "learning_item_label": [
        (("learning_item_id", "label_id"), "uq_learning_item_label")
    ],
    "user_sessions": [(('session_id',), "user_sessions_session_id_key")],
    "revision_session_questions": [
        (("session_id", "question_id"), "uq_revision_session_question")
    ],
    "user_label_mastery": [
        (("user_id", "label_id"), "uq_user_label_mastery")
    ],
    "user_learning_item_mastery": [
        (
            ("user_id", "learning_item_id"),
            "uq_user_learning_item_mastery",
        )
    ],
}

BASELINE_FOREIGN_KEYS = [
    ("learning_item", ("user_id",), "users", ("id",), "CASCADE"),
    (
        "learning_item_key_points",
        ("learning_item_id",),
        "learning_item",
        ("id",),
        "NO ACTION",
    ),
    ("label", ("user_id",), "users", ("id",), "CASCADE"),
    (
        "learning_item_label",
        ("learning_item_id",),
        "learning_item",
        ("id",),
        "CASCADE",
    ),
    ("learning_item_label", ("label_id",), "label", ("id",), "CASCADE"),
    (
        "questions",
        ("learning_item_id",),
        "learning_item",
        ("id",),
        "CASCADE",
    ),
    ("revision_sessions", ("user_id",), "users", ("id",), "CASCADE"),
    ("user_attempts", ("user_id",), "users", ("id",), "CASCADE"),
    (
        "user_attempts",
        ("question_id",),
        "questions",
        ("id",),
        "CASCADE",
    ),
    (
        "user_attempts",
        ("session_id",),
        "revision_sessions",
        ("id",),
        "CASCADE",
    ),
    (
        "media",
        ("learning_item_id",),
        "learning_item",
        ("id",),
        "CASCADE",
    ),
    ("user_sessions", ("user_id",), "users", ("id",), "NO ACTION"),
    (
        "revision_session_questions",
        ("session_id",),
        "revision_sessions",
        ("id",),
        "CASCADE",
    ),
    (
        "revision_session_questions",
        ("question_id",),
        "questions",
        ("id",),
        "CASCADE",
    ),
    (
        "user_label_mastery",
        ("user_id",),
        "users",
        ("id",),
        "CASCADE",
    ),
    (
        "user_label_mastery",
        ("label_id",),
        "label",
        ("id",),
        "CASCADE",
    ),
    (
        "user_learning_item_mastery",
        ("user_id",),
        "users",
        ("id",),
        "CASCADE",
    ),
    (
        "user_learning_item_mastery",
        ("learning_item_id",),
        "learning_item",
        ("id",),
        "CASCADE",
    ),
]

BASELINE_REQUIRED_FK_NAMES = {
    (
        "revision_session_questions",
        ("question_id",),
    ): "revision_session_questions_question_id_fkey",
    ("user_attempts", ("question_id",)): "user_attempts_question_id_fkey",
}

BASELINE_INDEXES = {
    table_name: (f"ix_{table_name}_id", ("id",), False)
    for table_name in BASELINE_COLUMNS
    if table_name != "learning_item_key_points"
}

BASELINE_ENUMS = {
    "answer_option_enum": ("A", "B", "C", "D"),
    "media_type_enum": ("image", "video", "pdf"),
}


def _case_insensitive_value(
    mapping: Mapping[str, object],
    name: str,
) -> object | None:
    expected = name.casefold()
    for key, value in mapping.items():
        if key.casefold() == expected:
            return value
    return None


def _configured_database_url() -> str | None:
    configured = _case_insensitive_value(os.environ, "DATABASE_URL")
    if configured is None:
        env_values = dotenv_values(BACKEND_DIR / ".env")
        configured = _case_insensitive_value(env_values, "DATABASE_URL")
    return str(configured) if configured else None


def _run_inspection(database_url: str) -> None:
    stage = URL_PARSING
    connection = None
    try:
        parsed_url = make_url(database_url)
        if parsed_url.get_backend_name() != "postgresql":
            raise ValueError("configured database is not PostgreSQL")
        if not parsed_url.host or not parsed_url.database:
            raise ValueError("configured PostgreSQL URL is incomplete")

        stage = DNS
        socket.getaddrinfo(
            parsed_url.host,
            parsed_url.port or 5432,
            type=socket.SOCK_STREAM,
        )

        psycopg_url = parsed_url.set(drivername="postgresql").render_as_string(
            hide_password=False
        )
        stage = CONNECTION
        connection = psycopg.connect(psycopg_url, connect_timeout=15)

        stage = READ_ONLY_SETUP
        connection.execute("SET TRANSACTION READ ONLY")
        read_only_row = connection.execute("SHOW transaction_read_only").fetchone()
        if read_only_row is None or read_only_row[0] != "on":
            raise RuntimeError("read-only transaction could not be verified")

        stage = INSPECTION
        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            ).fetchall()
        }
        columns: dict[str, dict[str, object]] = {table: {} for table in tables}
        for row in connection.execute(
            """
            SELECT
                table_name,
                column_name,
                data_type,
                udt_name,
                character_maximum_length,
                numeric_precision,
                numeric_scale,
                is_nullable,
                column_default,
                is_identity
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
            """
        ).fetchall():
            columns[row[0]][row[1]] = {
                "data_type": row[2],
                "udt_name": row[3],
                "length": row[4],
                "precision": row[5],
                "scale": row[6],
                "nullable": row[7] == "YES",
                "default": row[8],
                "identity": row[9] == "YES",
            }

        print("TRANSACTION_READ_ONLY=on")
        print(f"PUBLIC_TABLE_COUNT={len(tables)}")
        print("PUBLIC_TABLES=" + ",".join(sorted(tables)))

        if "alembic_version" in tables:
            revisions = [
                row[0]
                for row in connection.execute(
                    "SELECT version_num FROM alembic_version ORDER BY version_num"
                ).fetchall()
            ]
            print(
                "ALEMBIC_REVISIONS="
                + (",".join(revisions) if revisions else "<empty>")
            )
        else:
            print("ALEMBIC_REVISIONS=<table-missing>")

        _print_baseline_schema_comparison(connection, tables, columns)
        _print_head_schema_comparison(tables, columns)
        _print_reconciliation_counts(connection, tables, columns)
    except Exception as exc:
        raise InspectionFailure(stage, exc) from None
    finally:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
            try:
                connection.close()
            except Exception:
                pass


def _normalized_column_type(metadata: dict[str, object]) -> str:
    data_type = str(metadata["data_type"]).casefold()
    if data_type == "integer":
        return "INTEGER"
    if data_type == "text":
        return "TEXT"
    if data_type == "boolean":
        return "BOOLEAN"
    if data_type == "character varying":
        return f"VARCHAR({metadata['length']})"
    if data_type.startswith("timestamp"):
        return "TIMESTAMP"
    if data_type == "user-defined":
        return f"ENUM({metadata['udt_name']})"
    if data_type == "numeric":
        return f"NUMERIC({metadata['precision']},{metadata['scale']})"
    return data_type.upper()


def _normalized_column_default(metadata: dict[str, object]) -> str | None:
    if metadata["identity"]:
        return "AUTO_INCREMENT"
    default = metadata["default"]
    if default is None:
        return None
    normalized = "".join(str(default).casefold().split())
    if normalized.startswith("nextval("):
        return "AUTO_INCREMENT"
    if normalized in {
        "now()",
        "current_timestamp",
        "transaction_timestamp()",
    }:
        return "CURRENT_TIMESTAMP"
    return normalized


def _constraint_metadata(connection) -> list[dict[str, object]]:
    delete_actions = {
        "a": "NO ACTION",
        "r": "RESTRICT",
        "c": "CASCADE",
        "n": "SET NULL",
        "d": "SET DEFAULT",
    }
    rows = connection.execute(
        """
        SELECT
            source.relname,
            constraint_row.conname,
            constraint_row.contype,
            ARRAY(
                SELECT attribute.attname
                FROM unnest(constraint_row.conkey) WITH ORDINALITY
                     AS key(attnum, position)
                JOIN pg_attribute AS attribute
                  ON attribute.attrelid = constraint_row.conrelid
                 AND attribute.attnum = key.attnum
                ORDER BY key.position
            ),
            target.relname,
            ARRAY(
                SELECT attribute.attname
                FROM unnest(constraint_row.confkey) WITH ORDINALITY
                     AS key(attnum, position)
                JOIN pg_attribute AS attribute
                  ON attribute.attrelid = constraint_row.confrelid
                 AND attribute.attnum = key.attnum
                ORDER BY key.position
            ),
            constraint_row.confdeltype
        FROM pg_constraint AS constraint_row
        JOIN pg_class AS source ON source.oid = constraint_row.conrelid
        JOIN pg_namespace AS namespace ON namespace.oid = source.relnamespace
        LEFT JOIN pg_class AS target ON target.oid = constraint_row.confrelid
        WHERE namespace.nspname = 'public'
          AND constraint_row.contype IN ('p', 'u', 'f', 'c')
        ORDER BY source.relname, constraint_row.conname
        """
    ).fetchall()
    return [
        {
            "table": row[0],
            "name": row[1],
            "kind": row[2],
            "columns": tuple(row[3] or ()),
            "target_table": row[4],
            "target_columns": tuple(row[5] or ()),
            "on_delete": delete_actions.get(row[6], "UNKNOWN"),
        }
        for row in rows
    ]


def _index_metadata(connection) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT
            source.relname,
            index_relation.relname,
            index_row.indisunique,
            ARRAY(
                SELECT attribute.attname
                FROM unnest(index_row.indkey) WITH ORDINALITY
                     AS key(attnum, position)
                LEFT JOIN pg_attribute AS attribute
                  ON attribute.attrelid = index_row.indrelid
                 AND attribute.attnum = key.attnum
                ORDER BY key.position
            ),
            pg_get_expr(index_row.indpred, index_row.indrelid)
        FROM pg_index AS index_row
        JOIN pg_class AS source ON source.oid = index_row.indrelid
        JOIN pg_namespace AS namespace ON namespace.oid = source.relnamespace
        JOIN pg_class AS index_relation
          ON index_relation.oid = index_row.indexrelid
        WHERE namespace.nspname = 'public'
          AND NOT EXISTS (
              SELECT 1
              FROM pg_constraint AS constraint_row
              WHERE constraint_row.conindid = index_row.indexrelid
          )
        ORDER BY source.relname, index_relation.relname
        """
    ).fetchall()
    return [
        {
            "table": row[0],
            "name": row[1],
            "unique": row[2],
            "columns": tuple(row[3] or ()),
            "predicate": row[4],
        }
        for row in rows
    ]


def _enum_metadata(connection) -> dict[str, tuple[str, ...]]:
    rows = connection.execute(
        """
        SELECT type_row.typname, enum_row.enumlabel
        FROM pg_type AS type_row
        JOIN pg_enum AS enum_row ON enum_row.enumtypid = type_row.oid
        JOIN pg_namespace AS namespace ON namespace.oid = type_row.typnamespace
        WHERE namespace.nspname = 'public'
        ORDER BY type_row.typname, enum_row.enumsortorder
        """
    ).fetchall()
    result: dict[str, list[str]] = {}
    for enum_name, label in rows:
        result.setdefault(enum_name, []).append(label)
    return {name: tuple(labels) for name, labels in result.items()}


def _print_baseline_schema_comparison(connection, tables, columns) -> None:
    structural: list[str] = []
    naming_only: list[str] = []
    upgrade_name_blockers: list[str] = []

    actual_tables = tables - {"alembic_version"}
    expected_tables = set(BASELINE_COLUMNS)
    for table_name in sorted(expected_tables - actual_tables):
        structural.append(f"missing table {table_name}")
    for table_name in sorted(actual_tables - expected_tables):
        structural.append(f"extra table {table_name}")

    for table_name in sorted(expected_tables & actual_tables):
        expected_columns = BASELINE_COLUMNS[table_name]
        actual_columns = columns[table_name]
        for column_name in sorted(set(expected_columns) - set(actual_columns)):
            structural.append(f"missing column {table_name}.{column_name}")
        for column_name in sorted(set(actual_columns) - set(expected_columns)):
            structural.append(f"extra column {table_name}.{column_name}")
        for column_name in sorted(set(expected_columns) & set(actual_columns)):
            expected_type, expected_nullable, expected_default = expected_columns[
                column_name
            ]
            metadata = actual_columns[column_name]
            actual_type = _normalized_column_type(metadata)
            actual_nullable = bool(metadata["nullable"])
            actual_default = _normalized_column_default(metadata)
            if actual_type != expected_type:
                structural.append(
                    f"type {table_name}.{column_name}:"
                    f"expected={expected_type},actual={actual_type}"
                )
            if actual_nullable != expected_nullable:
                structural.append(
                    f"nullability {table_name}.{column_name}:"
                    f"expected={expected_nullable},actual={actual_nullable}"
                )
            if actual_default != expected_default:
                structural.append(
                    f"default {table_name}.{column_name}:"
                    f"expected={expected_default},actual={actual_default}"
                )

    constraints = _constraint_metadata(connection)
    primary_keys = [row for row in constraints if row["kind"] == "p"]
    unique_constraints = [row for row in constraints if row["kind"] == "u"]
    foreign_keys = [row for row in constraints if row["kind"] == "f"]
    check_constraints = [row for row in constraints if row["kind"] == "c"]

    for table_name, (expected_columns, expected_name) in BASELINE_PRIMARY_KEYS.items():
        matches = [
            row
            for row in primary_keys
            if row["table"] == table_name and row["columns"] == expected_columns
        ]
        if not matches:
            structural.append(f"missing primary key {table_name}{expected_columns}")
        elif matches[0]["name"] != expected_name:
            naming_only.append(
                f"primary key {table_name}{expected_columns}:"
                f"expected={expected_name},actual={matches[0]['name']}"
            )
    expected_pk_structures = {
        (table_name, expected_columns)
        for table_name, (expected_columns, _name) in BASELINE_PRIMARY_KEYS.items()
    }
    for row in primary_keys:
        if (row["table"], row["columns"]) not in expected_pk_structures:
            structural.append(f"extra primary key {row['table']}{row['columns']}")

    expected_unique_structures = {
        (table_name, expected_columns)
        for table_name, entries in BASELINE_UNIQUE_CONSTRAINTS.items()
        for expected_columns, _name in entries
    }
    for table_name, entries in BASELINE_UNIQUE_CONSTRAINTS.items():
        for expected_columns, expected_name in entries:
            matches = [
                row
                for row in unique_constraints
                if row["table"] == table_name
                and row["columns"] == expected_columns
            ]
            if not matches:
                structural.append(
                    f"missing unique constraint {table_name}{expected_columns}"
                )
            elif matches[0]["name"] != expected_name:
                naming_only.append(
                    f"unique constraint {table_name}{expected_columns}:"
                    f"expected={expected_name},actual={matches[0]['name']}"
                )
    for row in unique_constraints:
        if (row["table"], row["columns"]) not in expected_unique_structures:
            structural.append(
                f"extra unique constraint {row['table']}{row['columns']}"
            )

    expected_fk_structures = set(BASELINE_FOREIGN_KEYS)
    actual_fk_structures = {
        (
            row["table"],
            row["columns"],
            row["target_table"],
            row["target_columns"],
            row["on_delete"],
        )
        for row in foreign_keys
    }
    for expected in sorted(expected_fk_structures - actual_fk_structures):
        structural.append(f"missing foreign key {expected}")
    for actual in sorted(actual_fk_structures - expected_fk_structures):
        structural.append(f"extra foreign key {actual}")

    for row in foreign_keys:
        structure = (
            row["table"],
            row["columns"],
            row["target_table"],
            row["target_columns"],
            row["on_delete"],
        )
        if structure not in expected_fk_structures:
            continue
        expected_name = f"{row['table']}_{'_'.join(row['columns'])}_fkey"
        if row["name"] != expected_name:
            difference = (
                f"foreign key {row['table']}{row['columns']}:"
                f"expected={expected_name},actual={row['name']}"
            )
            naming_only.append(difference)
            required_name = BASELINE_REQUIRED_FK_NAMES.get(
                (row["table"], row["columns"])
            )
            if required_name and row["name"] != required_name:
                upgrade_name_blockers.append(difference)

    for row in check_constraints:
        structural.append(f"extra check constraint {row['table']}.{row['name']}")

    actual_indexes = _index_metadata(connection)
    expected_index_structures = {
        (table_name, columns, unique, None)
        for table_name, (_name, columns, unique) in BASELINE_INDEXES.items()
    }
    actual_index_structures = {
        (row["table"], row["columns"], row["unique"], row["predicate"])
        for row in actual_indexes
    }
    for structure in sorted(
        expected_index_structures - actual_index_structures,
        key=repr,
    ):
        structural.append(f"missing index {structure}")
    for structure in sorted(
        actual_index_structures - expected_index_structures,
        key=repr,
    ):
        structural.append(f"extra index {structure}")
    for table_name, (expected_name, expected_columns, expected_unique) in (
        BASELINE_INDEXES.items()
    ):
        matches = [
            row
            for row in actual_indexes
            if row["table"] == table_name
            and row["columns"] == expected_columns
            and row["unique"] == expected_unique
            and row["predicate"] is None
        ]
        if matches and matches[0]["name"] != expected_name:
            naming_only.append(
                f"index {table_name}{expected_columns}:"
                f"expected={expected_name},actual={matches[0]['name']}"
            )

    actual_enums = _enum_metadata(connection)
    for enum_name, labels in BASELINE_ENUMS.items():
        if actual_enums.get(enum_name) != labels:
            structural.append(
                f"enum {enum_name}:expected={labels},"
                f"actual={actual_enums.get(enum_name)}"
            )
    for enum_name in sorted(set(actual_enums) - set(BASELINE_ENUMS)):
        structural.append(f"extra enum {enum_name}")

    for index, difference in enumerate(structural, start=1):
        print(f"BASELINE_STRUCTURAL_DIFFERENCE[{index}]={difference}")
    for index, difference in enumerate(naming_only, start=1):
        print(f"BASELINE_NAMING_ONLY_DIFFERENCE[{index}]={difference}")
    for index, difference in enumerate(upgrade_name_blockers, start=1):
        print(f"BASELINE_UPGRADE_NAME_BLOCKER[{index}]={difference}")
    print(f"BASELINE_STRUCTURAL_DIFFERENCE_COUNT={len(structural)}")
    print(f"BASELINE_NAMING_ONLY_DIFFERENCE_COUNT={len(naming_only)}")
    print(f"BASELINE_UPGRADE_NAME_BLOCKER_COUNT={len(upgrade_name_blockers)}")
    safe_to_stamp = not structural and not naming_only and not upgrade_name_blockers
    print(f"BASELINE_SAFE_TO_STAMP_0001={'YES' if safe_to_stamp else 'NO'}")


def _print_head_schema_comparison(
    tables: set[str],
    columns: dict[str, dict[str, object]],
) -> None:
    expected_tables = set(Base.metadata.tables)
    actual_application_tables = tables - {"alembic_version"}

    print(
        "HEAD_MISSING_TABLES="
        + ",".join(sorted(expected_tables - actual_application_tables))
    )
    print(
        "HEAD_EXTRA_TABLES="
        + ",".join(sorted(actual_application_tables - expected_tables))
    )

    drift_found = False
    for table_name in sorted(expected_tables & actual_application_tables):
        expected_columns = {
            column.name for column in Base.metadata.tables[table_name].columns
        }
        actual_columns = set(columns[table_name])
        missing = expected_columns - actual_columns
        extra = actual_columns - expected_columns
        if missing or extra:
            drift_found = True
            print(
                f"COLUMN_DRIFT[{table_name}]="
                f"missing:{','.join(sorted(missing))};"
                f"extra:{','.join(sorted(extra))}"
            )
    if not drift_found:
        print("COLUMN_DRIFT=<none>")


def _print_reconciliation_counts(connection, tables, columns) -> None:
    def applicable(table: str, required_columns: tuple[str, ...] = ()) -> bool:
        return table in tables and set(required_columns) <= set(columns[table])

    def count(name: str, statement: str) -> None:
        row = connection.execute(statement).fetchone()
        if row is None:
            raise RuntimeError("count query returned no row")
        value = row[0]
        print(f"{name}={value}")

    if applicable("user_attempts"):
        count("LEGACY_USER_ATTEMPTS_COUNT", "SELECT COUNT(*) FROM user_attempts")
    else:
        print("LEGACY_USER_ATTEMPTS_COUNT=<table-missing>")
    if applicable("revision_sessions"):
        count(
            "LEGACY_REVISION_SESSIONS_COUNT",
            "SELECT COUNT(*) FROM revision_sessions",
        )
        if applicable("revision_sessions", ("ended_at",)):
            count(
                "LEGACY_REVISION_SESSIONS_ENDED_COUNT",
                "SELECT COUNT(*) FROM revision_sessions WHERE ended_at IS NOT NULL",
            )
    else:
        print("LEGACY_REVISION_SESSIONS_COUNT=<table-missing>")

    phase1_pending = (
        applicable("revision_sessions", ("id", "quiz_type"))
        and applicable(
            "revision_session_questions",
            ("id", "session_id", "question_id", "question_order"),
        )
        and "requested_strategy" not in columns["revision_sessions"]
    )
    if phase1_pending:
        count(
            "G0002_INVALID_SESSION_BACKFILL",
            """
            SELECT COUNT(*)
            FROM (
                SELECT
                    session.id,
                    UPPER(session.quiz_type) AS strategy,
                    COUNT(selected.id) AS question_count
                FROM revision_sessions AS session
                LEFT JOIN revision_session_questions AS selected
                  ON selected.session_id = session.id
                GROUP BY session.id, session.quiz_type
            ) AS candidate
            WHERE strategy IS NULL
               OR strategy NOT IN ('RANDOM', 'LABEL')
               OR question_count NOT BETWEEN 1 AND 50
            """,
        )
        count(
            "G0002_DUPLICATE_ORDER_GROUPS",
            """
            SELECT COUNT(*)
            FROM (
                SELECT session_id, question_order
                FROM revision_session_questions
                GROUP BY session_id, question_order
                HAVING COUNT(*) > 1
            ) AS duplicates
            """,
        )

        source_tables_available = applicable(
            "questions",
            (
                "id",
                "learning_item_id",
                "question_text",
                "option_a",
                "option_b",
                "option_c",
                "option_d",
                "correct_option",
                "difficulty",
                "expected_time_seconds",
            ),
        ) and applicable("learning_item", ("id", "title"))
        if source_tables_available:
            count(
                "G0002_INCOMPLETE_SNAPSHOT_SOURCES",
                """
                SELECT COUNT(*)
                FROM revision_session_questions AS selected
                LEFT JOIN questions AS question
                  ON question.id = selected.question_id
                LEFT JOIN learning_item AS item
                  ON item.id = question.learning_item_id
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
        else:
            print("G0002_INCOMPLETE_SNAPSHOT_SOURCES=<schema-unavailable>")
    else:
        print("G0002=<not-applicable-or-already-applied>")

    phase3_pending = (
        applicable(
            "revision_sessions",
            ("id", "status", "ended_at", "requested_question_count"),
        )
        and applicable(
            "revision_session_questions",
            ("session_id", "correct_option_snapshot"),
        )
        and applicable("user_attempts")
        and "session_question_id" not in columns["user_attempts"]
    )
    if phase3_pending:
        count("G0004_LEGACY_ATTEMPTS", "SELECT COUNT(*) FROM user_attempts")
        count(
            "G0004_COMPLETED_SESSIONS",
            """
            SELECT COUNT(*)
            FROM revision_sessions
            WHERE status = 'COMPLETED'
            """,
        )
        count(
            "G0004_INVALID_SESSION_LIFECYCLE_OR_COUNT",
            """
            SELECT COUNT(*)
            FROM revision_sessions AS session
            WHERE session.status <> 'IN_PROGRESS'
               OR session.ended_at IS NOT NULL
               OR session.requested_question_count NOT BETWEEN 1 AND 50
               OR session.requested_question_count <> (
                   SELECT COUNT(*)
                   FROM revision_session_questions AS selected
                   WHERE selected.session_id = session.id
               )
            """,
        )
        count(
            "G0004_UNNORMALIZABLE_SNAPSHOT_ANSWERS",
            """
            SELECT COUNT(*)
            FROM revision_session_questions
            WHERE UPPER(BTRIM(correct_option_snapshot))
                  NOT IN ('0', '1', '2', '3', 'A', 'B', 'C', 'D')
            """,
        )

        for table_name in (
            "user_label_mastery",
            "user_learning_item_mastery",
        ):
            if applicable(
                table_name,
                ("mastery_score", "total_attempts", "correct_attempts"),
            ):
                count(
                    f"G0004_INVALID_MASTERY[{table_name}]",
                    f"""
                    SELECT COUNT(*)
                    FROM {table_name}
                    WHERE (
                        mastery_score IS NOT NULL
                        AND mastery_score NOT BETWEEN 0 AND 100
                    )
                    OR (
                        total_attempts IS NOT NULL
                        AND total_attempts < 0
                    )
                    OR (
                        correct_attempts IS NOT NULL
                        AND correct_attempts < 0
                    )
                    OR COALESCE(correct_attempts, 0)
                       > COALESCE(total_attempts, 0)
                    """,
                )
            else:
                print(f"G0004_INVALID_MASTERY[{table_name}]=<schema-unavailable>")
    else:
        print("G0004=<not-applicable-or-already-applied>")

    if applicable(
        "revision_sessions",
        ("requested_strategy", "strategy_used"),
    ):
        count(
            "G0005_INVALID_STRATEGY_VALUES",
            """
            SELECT COUNT(*)
            FROM revision_sessions
            WHERE requested_strategy IS NULL
               OR requested_strategy NOT IN ('RANDOM', 'LABEL', 'SMART')
               OR strategy_used IS NULL
               OR strategy_used NOT IN ('RANDOM', 'LABEL', 'SMART')
            """,
        )
    else:
        print("G0005=<not-applicable-before-0002>")


def _exception_chain(exc: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and current not in chain:
        chain.append(current)
        nested = getattr(current, "orig", None)
        if not isinstance(nested, BaseException):
            nested = current.__cause__ or current.__context__
        current = nested if isinstance(nested, BaseException) else None
    return chain


def _sqlstate(exc: BaseException) -> str | None:
    for candidate in _exception_chain(exc):
        value = getattr(candidate, "sqlstate", None)
        if value is None:
            diagnostic = getattr(candidate, "diag", None)
            value = getattr(diagnostic, "sqlstate", None)
        if value:
            normalized = str(value).upper()
            if len(normalized) == 5 and normalized.isalnum():
                return normalized
    return None


def _classify_failure(stage: str, exc: BaseException) -> str:
    chain = _exception_chain(exc)
    sqlstate = _sqlstate(exc)
    message = " ".join(str(candidate).casefold() for candidate in chain)

    if stage == DNS or any(isinstance(item, socket.gaierror) for item in chain):
        return "DNS"
    if sqlstate in {"28000", "28P01"}:
        return "AUTHENTICATION"
    if sqlstate == "3D000":
        return "MISSING_DATABASE"
    if (
        "unsupported startup parameter" in message
        or "unsupported connection option" in message
        or "invalid connection option" in message
        or "unrecognized configuration parameter" in message
    ):
        return "UNSUPPORTED_CONNECTION_OPTION"
    if (
        "password authentication failed" in message
        or "authentication failed" in message
        or "no password supplied" in message
        or "no pg_hba.conf entry" in message
    ):
        return "AUTHENTICATION"
    if "database" in message and "does not exist" in message:
        return "MISSING_DATABASE"
    if any(
        marker in message
        for marker in (
            "ssl",
            "tls",
            "certificate",
            "channel binding",
            "connection is insecure",
        )
    ):
        return "SSL"
    if any(isinstance(item, (TimeoutError, socket.timeout)) for item in chain) or any(
        marker in message
        for marker in (
            "timeout",
            "timed out",
            "query_wait_timeout",
        )
    ):
        return "TIMEOUT"
    if any(
        marker in message
        for marker in (
            "could not translate host name",
            "getaddrinfo",
            "name or service not known",
            "name resolution",
            "nodename nor servname",
        )
    ):
        return "DNS"
    return "UNKNOWN"


def _print_failure(stage: str, exc: BaseException) -> None:
    exception_class = "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in type(exc).__name__
    )
    print("INSPECTION_ERROR=FAILED")
    print(f"FAILURE_STAGE={stage}")
    print(f"EXCEPTION_CLASS={exception_class or 'UNKNOWN'}")
    print(f"SQLSTATE={_sqlstate(exc) or '<unavailable>'}")
    print(f"CLASSIFIED_CAUSE={_classify_failure(stage, exc)}")


def main() -> int:
    database_url = _configured_database_url()
    if not database_url:
        _print_failure(
            URL_PARSING,
            ValueError("DATABASE_URL is not configured"),
        )
        return 2

    try:
        _run_inspection(database_url)
    except KeyboardInterrupt:
        print("INSPECTION_ERROR=INTERRUPTED")
        return 130
    except InspectionFailure as exc:
        _print_failure(exc.stage, exc.cause)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
