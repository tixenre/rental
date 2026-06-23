"""server_errors: tabla de registro de errores del servidor.

Revision ID: s3rv3r3rr0rs
Revises: cart0sact1vos
Create Date: 2026-06-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "s3rv3r3rr0rs"
down_revision: Union[str, Sequence[str], None] = "cart0sact1vos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS server_errors (
            id          SERIAL PRIMARY KEY,
            route       TEXT NOT NULL,
            error_type  TEXT NOT NULL,
            message     TEXT NOT NULL DEFAULT '',
            traceback   TEXT NOT NULL DEFAULT '',
            request_id  TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_server_errors_created "
        "ON server_errors(created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS server_errors")
