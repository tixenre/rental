"""B1 #635: contenido_incluido_json en equipo_fichas.

Dimension 3 del modelo de productos: qué trae la caja de cada equipo
(reflector, fuente, cables, estuche). Lista estructurada con nombre,
cantidad y foto opcional. Editada manualmente, nunca por IA.

Revision ID: b1e3f5a7c9d2
Revises: a1b3c5e7f9d2
Create Date: 2026-05-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b1e3f5a7c9d2"
down_revision: Union[str, Sequence[str], None] = "a1b3c5e7f9d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE equipo_fichas "
        "ADD COLUMN IF NOT EXISTS contenido_incluido_json TEXT"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE equipo_fichas "
        "DROP COLUMN IF EXISTS contenido_incluido_json"
    ))
