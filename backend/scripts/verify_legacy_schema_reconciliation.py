"""Read-only verification of a rehearsal schema reconciled to Alembic 0001."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import sys

import psycopg


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.inspect_development_database import (  # noqa: E402
    baseline_schema_comparison,
    schema_metadata,
)
from scripts.reconcile_legacy_schema_to_0001 import (  # noqa: E402
    ADVISORY_LOCK_KEYS,
    CONNECTION,
    POST_RECONCILIATION,
    ReconciliationFailure,
    TRANSACTION_SETUP,
    _adoption_url,
    _psycopg_connection_string,
    _snapshot_database,
    _target_identity_hash,
    load_snapshot,
    print_failure,
    run_in_transaction,
    validate_target,
)


def compare_preservation_snapshots(
    before: Mapping[str, object],
    after: Mapping[str, object],
) -> tuple[bool, bool]:
    """Compare retained rows/IDs separately from sequence ownership and state."""

    tables_match = before.get("tables") == after.get("tables")
    sequences_match = before.get("sequences") == after.get("sequences")
    return tables_match, sequences_match


def _verify_transaction(
    connection,
    *,
    target_hash: str,
    expected_snapshot: Mapping[str, object],
) -> None:
    try:
        connection.execute(
            "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
        )
        connection.execute("SET LOCAL statement_timeout = '60s'")
        connection.execute("SET LOCAL lock_timeout = '5s'")
        connection.execute(
            "SELECT pg_advisory_xact_lock(%s, %s)",
            ADVISORY_LOCK_KEYS,
        )
    except Exception as exc:
        raise ReconciliationFailure(
            TRANSACTION_SETUP,
            "READ_ONLY_TRANSACTION_SETUP_FAILED",
            exc,
        ) from None

    try:
        tables, columns = schema_metadata(connection)
        alembic_absent = "alembic_version" not in tables
        structural, naming, blockers = baseline_schema_comparison(
            connection,
            tables,
            columns,
        )
        current_snapshot = _snapshot_database(connection, target_hash)
        rows_and_ids_match, sequences_match = compare_preservation_snapshots(
            expected_snapshot,
            current_snapshot,
        )
    except ReconciliationFailure:
        raise
    except Exception as exc:
        raise ReconciliationFailure(
            POST_RECONCILIATION,
            "POST_RECONCILIATION_QUERY_FAILED",
            exc,
        ) from None

    print(f"BASELINE_STRUCTURAL_DIFFERENCE_COUNT={len(structural)}")
    print(f"BASELINE_NAMING_ONLY_DIFFERENCE_COUNT={len(naming)}")
    print(f"BASELINE_UPGRADE_NAME_BLOCKER_COUNT={len(blockers)}")
    print(
        "BASELINE_SAFE_TO_STAMP_0001="
        f"{'YES' if not structural and not naming and not blockers else 'NO'}"
    )
    print(f"ALEMBIC_VERSION_ABSENT={'YES' if alembic_absent else 'NO'}")
    print(
        "RETAINED_ROW_COUNTS_AND_ID_SIGNATURES_MATCH="
        f"{'YES' if rows_and_ids_match else 'NO'}"
    )
    print(f"SEQUENCES_AND_OWNERSHIP_MATCH={'YES' if sequences_match else 'NO'}")

    if not alembic_absent:
        raise ReconciliationFailure(
            POST_RECONCILIATION,
            "ALEMBIC_VERSION_CREATED_UNEXPECTEDLY",
        )
    if structural or naming or blockers:
        raise ReconciliationFailure(
            POST_RECONCILIATION,
            "BASELINE_RECONCILIATION_INCOMPLETE",
        )
    if not rows_and_ids_match or not sequences_match:
        raise ReconciliationFailure(
            POST_RECONCILIATION,
            "RETAINED_DATA_OR_SEQUENCE_CHANGED",
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify the rehearsal schema matches Alembic 0001",
    )
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
        adoption_url = _adoption_url(active_environ)
        parsed_url = validate_target(adoption_url, environ=active_environ)
        target_hash = _target_identity_hash(parsed_url)
        expected_snapshot = load_snapshot(args.snapshot_file, target_hash)
    except ReconciliationFailure as failure:
        print_failure(failure)
        return 2

    try:
        with psycopg.connect(
            _psycopg_connection_string(parsed_url),
            connect_timeout=15,
            autocommit=False,
        ) as connection:
            run_in_transaction(
                connection,
                lambda active_connection: _verify_transaction(
                    active_connection,
                    target_hash=target_hash,
                    expected_snapshot=expected_snapshot,
                ),
            )
    except KeyboardInterrupt:
        print("RECONCILIATION_VERIFICATION_ERROR=INTERRUPTED")
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
