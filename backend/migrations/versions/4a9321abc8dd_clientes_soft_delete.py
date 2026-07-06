"""clientes: soft delete (eliminado_at) — #1251 Fase 2

Revision ID: 4a9321abc8dd
Revises: q7r8s9t0u1v2
Create Date: 2026-07-05
"""
from typing import Sequence, Union
from alembic import op

revision: str = "4a9321abc8dd"
down_revision: Union[str, Sequence[str], None] = "q7r8s9t0u1v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS eliminado_at TIMESTAMP")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_clientes_eliminado_at ON clientes(eliminado_at) "
        "WHERE eliminado_at IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_clientes_eliminado_at")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS eliminado_at")
