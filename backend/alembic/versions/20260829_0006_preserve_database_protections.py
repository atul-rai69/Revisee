"""Preserve database-enforced ownership protections.

Revision ID: 20260829_0006
Revises: 20260827_0005
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260829_0006"
down_revision: str | None = "20260827_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


KEY_POINT_FK = "learning_item_key_points_learning_item_id_fkey"
USER_SESSION_FK = "user_sessions_user_id_fkey"


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM learning_item_key_points
                WHERE learning_item_id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'upgrade refused: null key-point references require reconciliation';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM learning_item_key_points AS key_point
                LEFT JOIN learning_item AS item
                    ON item.id = key_point.learning_item_id
                WHERE item.id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'upgrade refused: orphan key-point references require reconciliation';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM user_sessions AS user_session
                LEFT JOIN users AS app_user
                    ON app_user.id = user_session.user_id
                WHERE app_user.id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'upgrade refused: orphan user-session references require reconciliation';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint AS constraint_record
                WHERE constraint_record.conname =
                    'learning_item_key_points_learning_item_id_fkey'
                  AND constraint_record.contype = 'f'
                  AND constraint_record.conrelid =
                    'public.learning_item_key_points'::regclass
                  AND constraint_record.confrelid =
                    'public.learning_item'::regclass
                  AND constraint_record.conkey = ARRAY[
                        (
                            SELECT attribute.attnum
                            FROM pg_attribute AS attribute
                            WHERE attribute.attrelid =
                                'public.learning_item_key_points'::regclass
                              AND attribute.attname = 'learning_item_id'
                        )
                    ]::smallint[]
                  AND constraint_record.confkey = ARRAY[
                        (
                            SELECT attribute.attnum
                            FROM pg_attribute AS attribute
                            WHERE attribute.attrelid =
                                'public.learning_item'::regclass
                              AND attribute.attname = 'id'
                        )
                    ]::smallint[]
                  AND constraint_record.confdeltype = 'a'
                  AND constraint_record.convalidated
            ) OR NOT EXISTS (
                SELECT 1
                FROM pg_constraint AS constraint_record
                WHERE constraint_record.conname = 'user_sessions_user_id_fkey'
                  AND constraint_record.contype = 'f'
                  AND constraint_record.conrelid =
                    'public.user_sessions'::regclass
                  AND constraint_record.confrelid = 'public.users'::regclass
                  AND constraint_record.conkey = ARRAY[
                        (
                            SELECT attribute.attnum
                            FROM pg_attribute AS attribute
                            WHERE attribute.attrelid =
                                'public.user_sessions'::regclass
                              AND attribute.attname = 'user_id'
                        )
                    ]::smallint[]
                  AND constraint_record.confkey = ARRAY[
                        (
                            SELECT attribute.attnum
                            FROM pg_attribute AS attribute
                            WHERE attribute.attrelid = 'public.users'::regclass
                              AND attribute.attname = 'id'
                        )
                    ]::smallint[]
                  AND constraint_record.confdeltype = 'a'
                  AND constraint_record.convalidated
            ) THEN
                RAISE EXCEPTION
                    'upgrade refused: expected 0005 foreign-key definitions are missing or incompatible';
            END IF;
        END $$
        """
    )

    op.alter_column(
        "learning_item_key_points",
        "learning_item_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_constraint(
        KEY_POINT_FK,
        "learning_item_key_points",
        type_="foreignkey",
    )
    op.create_foreign_key(
        KEY_POINT_FK,
        "learning_item_key_points",
        "learning_item",
        ["learning_item_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        USER_SESSION_FK,
        "user_sessions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        USER_SESSION_FK,
        "user_sessions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column(
        "user_sessions",
        "is_active",
        existing_type=sa.Boolean(),
        existing_nullable=True,
        server_default=sa.true(),
    )


def downgrade() -> None:
    op.alter_column(
        "user_sessions",
        "is_active",
        existing_type=sa.Boolean(),
        existing_nullable=True,
        server_default=None,
    )

    op.drop_constraint(
        USER_SESSION_FK,
        "user_sessions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        USER_SESSION_FK,
        "user_sessions",
        "users",
        ["user_id"],
        ["id"],
    )

    op.drop_constraint(
        KEY_POINT_FK,
        "learning_item_key_points",
        type_="foreignkey",
    )
    op.create_foreign_key(
        KEY_POINT_FK,
        "learning_item_key_points",
        "learning_item",
        ["learning_item_id"],
        ["id"],
    )
    op.alter_column(
        "learning_item_key_points",
        "learning_item_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
