"""productoras: nombre + redes_sociales — #1251 Fase 2

Revision ID: 7b3f0e19d2ac
Revises: 4a9321abc8dd
Create Date: 2026-07-05
"""
from typing import Sequence, Union
from alembic import op

revision: str = "7b3f0e19d2ac"
down_revision: Union[str, Sequence[str], None] = "4a9321abc8dd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE productoras ADD COLUMN IF NOT EXISTS nombre TEXT")
    op.execute("ALTER TABLE productoras ADD COLUMN IF NOT EXISTS redes_sociales TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE productoras DROP COLUMN IF EXISTS redes_sociales")
    op.execute("ALTER TABLE productoras DROP COLUMN IF EXISTS nombre")
