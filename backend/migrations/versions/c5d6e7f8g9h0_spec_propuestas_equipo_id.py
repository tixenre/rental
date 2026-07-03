"""spec_propuestas_pendientes: equipo_id para atribución del panel no-reconocidos (#1203)

El primer productor de `spec_propuestas_pendientes` (specs_ingesta F7, umbral
≥3 HTMLs) escribe agregado, sin equipo_id — sirve para el CLI offline sobre
muchos HTMLs a la vez. El upload en vivo necesita un segundo modo: encolar
CADA par sin match, sin esperar repetición (con pocos equipos el umbral de 3
casi nunca dispara), atribuido al equipo que lo encontró — para que el panel
admin pueda agrupar por label y mostrar qué equipos la tienen.

Nullable: las propuestas viejas (agregadas, sin equipo) siguen válidas.

Espejado en init_db() (esquema en dos capas, decisión 2026-06-03). Idempotente.

Revision ID: c5d6e7f8g9h0
Revises: b4c5d6e7f8g9
Create Date: 2026-07-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c5d6e7f8g9h0"
down_revision: Union[str, Sequence[str], None] = "b4c5d6e7f8g9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text(
        "ALTER TABLE spec_propuestas_pendientes ADD COLUMN IF NOT EXISTS "
        "equipo_id INT REFERENCES equipos(id) ON DELETE CASCADE"
    ))
    bind.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_propuestas_pendientes_equipo "
        "ON spec_propuestas_pendientes(equipo_id) WHERE equipo_id IS NOT NULL"
    ))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP INDEX IF EXISTS idx_propuestas_pendientes_equipo"))
    bind.execute(sa.text(
        "ALTER TABLE spec_propuestas_pendientes DROP COLUMN IF EXISTS equipo_id"
    ))
