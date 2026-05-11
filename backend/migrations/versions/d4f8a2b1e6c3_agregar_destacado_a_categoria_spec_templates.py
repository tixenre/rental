"""agregar destacado a categoria_spec_templates

Issue #116: specs fundamentales destacados configurables.
Agrega columna `destacado` para marcar qué specs se muestran
como "quick facts" en la fila del catálogo (reemplaza el
conjunto hardcodeado montura/formato/resolucion/peso/alimentacion).

Revision ID: d4f8a2b1e6c3
Revises: 091de6e7b201
Create Date: 2026-05-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d4f8a2b1e6c3"
down_revision: Union[str, Sequence[str], None] = "091de6e7b201"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE categoria_spec_templates "
        "ADD COLUMN IF NOT EXISTS destacado BOOLEAN NOT NULL DEFAULT FALSE"
    )


def downgrade() -> None:
    pass
