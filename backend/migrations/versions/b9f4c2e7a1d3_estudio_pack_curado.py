"""estudio v2-C: pack curado (equipos elegidos a mano, no por categoría).

Revision ID: b9f4c2e7a1d3
Revises: a4c8e2f6b1d9
Create Date: 2026-05-27

Tabla `estudio_pack_equipos`: el admin cura qué equipos integran el pack del
estudio (reemplaza "todo lo de las categorías Grip/Iluminación/Modificadores").
La disponibilidad de la franja sigue saliendo del motor sagrado; solo cambia la
FUENTE de los ids candidatos.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b9f4c2e7a1d3"
down_revision: Union[str, Sequence[str], None] = "a4c8e2f6b1d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS estudio_pack_equipos (
            id          SERIAL PRIMARY KEY,
            estudio_id  INTEGER NOT NULL REFERENCES estudio(id) ON DELETE CASCADE,
            equipo_id   INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            orden       INTEGER NOT NULL DEFAULT 0,
            UNIQUE (estudio_id, equipo_id)
        )
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS estudio_pack_equipos"))
