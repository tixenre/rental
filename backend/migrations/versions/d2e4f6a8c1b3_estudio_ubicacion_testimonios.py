"""estudio: ubicación + cómo llegar + testimonios (prueba social).

Revision ID: d2e4f6a8c1b3
Revises: b9f4c2e7a1d3
Create Date: 2026-05-27

Agrega a `estudio` tres campos editables desde el back-office, para enriquecer
la ficha pública:
- `direccion` (TEXT): dirección del espacio (alimenta el mapa embebido).
- `como_llegar` (TEXT): notas de acceso / estacionamiento / entrada de autos.
- `testimonios_json` (TEXT): lista [{autor, texto}] de prueba social.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d2e4f6a8c1b3"
down_revision: Union[str, Sequence[str], None] = "b9f4c2e7a1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE estudio ADD COLUMN IF NOT EXISTS direccion TEXT NOT NULL DEFAULT ''"))
    conn.execute(sa.text("ALTER TABLE estudio ADD COLUMN IF NOT EXISTS como_llegar TEXT NOT NULL DEFAULT ''"))
    conn.execute(sa.text("ALTER TABLE estudio ADD COLUMN IF NOT EXISTS testimonios_json TEXT"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE estudio DROP COLUMN IF EXISTS direccion"))
    conn.execute(sa.text("ALTER TABLE estudio DROP COLUMN IF EXISTS como_llegar"))
    conn.execute(sa.text("ALTER TABLE estudio DROP COLUMN IF EXISTS testimonios_json"))
