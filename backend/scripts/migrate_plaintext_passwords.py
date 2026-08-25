"""Explicit, idempotent migration for legacy plaintext password rows."""
import argparse
import os
import sys
from dataclasses import dataclass

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from src.core.security import (
    hash_password,
    is_approved_password_hash,
    looks_like_unsupported_hash,
)
from src.modules.auth.models import User


@dataclass
class MigrationCounts:
    examined: int = 0
    already_hashed: int = 0
    plaintext_candidates: int = 0
    migrated: int = 0
    ambiguous: int = 0
    failed: int = 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url-env", required=True)
    parser.add_argument(
        "--environment",
        required=True,
        choices=("development", "staging", "production"),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-database-name")
    parser.add_argument("--confirm-production", action="store_true")
    parser.add_argument("--batch-size", type=int, default=100)
    return parser


def classify_password(value: str) -> str:
    if is_approved_password_hash(value):
        return "approved"
    if looks_like_unsupported_hash(value):
        return "ambiguous"
    return "plaintext"


def run_migration(
    database_url: str,
    *,
    apply_changes: bool,
    batch_size: int,
) -> MigrationCounts:
    engine = create_engine(database_url, pool_pre_ping=True)
    counts = MigrationCounts()

    with Session(engine) as db:
        users = db.scalars(select(User).order_by(User.id)).yield_per(batch_size)
        pending = 0
        try:
            for user in users:
                counts.examined += 1
                classification = classify_password(user.password_hash)
                if classification == "approved":
                    counts.already_hashed += 1
                    continue
                if classification == "ambiguous":
                    counts.ambiguous += 1
                    continue

                counts.plaintext_candidates += 1
                if apply_changes:
                    user.password_hash = hash_password(user.password_hash)
                    counts.migrated += 1
                    pending += 1
                    if pending >= batch_size:
                        db.commit()
                        pending = 0

            if apply_changes:
                db.commit()
            else:
                db.rollback()
        except Exception:
            counts.failed += 1
            db.rollback()
            raise
        finally:
            engine.dispose()
    return counts


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    variable_name = args.database_url_env
    database_url = os.environ.get(variable_name)
    if not database_url:
        print("Target database environment variable is missing", file=sys.stderr)
        return 2
    if args.batch_size <= 0:
        print("Batch size must be positive", file=sys.stderr)
        return 2

    database_name = make_url(database_url).database or ""
    if args.apply and args.confirm_database_name != database_name:
        print("Exact database-name confirmation is required for apply mode", file=sys.stderr)
        return 2
    if args.environment == "production" and not args.confirm_production:
        print("Production mode requires --confirm-production", file=sys.stderr)
        return 2

    counts = run_migration(
        database_url,
        apply_changes=args.apply,
        batch_size=args.batch_size,
    )
    mode = "apply" if args.apply else "dry-run"
    print(
        f"mode={mode} examined={counts.examined} "
        f"already_hashed={counts.already_hashed} "
        f"plaintext_candidates={counts.plaintext_candidates} "
        f"migrated={counts.migrated} "
        f"ambiguous={counts.ambiguous} failed={counts.failed}"
    )
    return 0 if counts.ambiguous == 0 and counts.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
