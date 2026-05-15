"""spec_definitions.validado — flag que el dueño marca cuando confirmó que la spec está bien

Permite ordenar el catálogo: validadas arriba, "sin revisar" abajo.

Revision ID: e7b3d5f9a1c2
Revises: c3e5f7a9d2b4
Create Date: 2026-05-15
"""
from typing import Sequence, Union

from alembic import op

revision: str = "e7b3d5f9a1c2"
down_revision: Union[str, Sequence[str], None] = "c3e5f7a9d2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE spec_definitions "
        "ADD COLUMN IF NOT EXISTS validado BOOLEAN NOT NULL DEFAULT FALSE"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE spec_definitions DROP COLUMN IF EXISTS validado")
