"""agregar visible a categorias

Permite ocultar una categoría del catálogo público sin borrarla. Útil
cuando hay equipos en stock pero no se quieren mostrar (ej. equipos de
uso interno, equipos en mantenimiento prolongado, etc.).

Default TRUE para que las categorías existentes sigan apareciendo. El
admin las oculta una por una desde la nueva vista `/admin/diseno`.

Revision ID: 9b27c84e5a01
Revises: 6ca756867afb
Create Date: 2026-05-14
"""
from typing import Sequence, Union

from alembic import op

revision: str = "9b27c84e5a01"
down_revision: Union[str, Sequence[str], None] = "6ca756867afb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE categorias "
        "ADD COLUMN IF NOT EXISTS visible BOOLEAN NOT NULL DEFAULT TRUE"
    )


def downgrade() -> None:
    pass
