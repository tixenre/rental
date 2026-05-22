"""grupo_visual en categorias

Agregar `grupo_visual VARCHAR(64)` a `categorias` para soportar el
agrupamiento visual del catálogo (Lentes + Adaptadores + Filtros → bloque
"Óptica") sin nidos en el modelo de datos. Hidratación inicial desde
`backend/specs/registry.py` vía registry_seeder en el próximo boot.

Revision ID: f2a8c9e1b3d4
Revises: e5a7b9d2c4f1
Create Date: 2026-05-20
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f2a8c9e1b3d4"
down_revision: Union[str, Sequence[str], None] = "e5a7b9d2c4f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE categorias ADD COLUMN IF NOT EXISTS grupo_visual VARCHAR(64)")


def downgrade() -> None:
    op.execute("ALTER TABLE categorias DROP COLUMN IF EXISTS grupo_visual")
