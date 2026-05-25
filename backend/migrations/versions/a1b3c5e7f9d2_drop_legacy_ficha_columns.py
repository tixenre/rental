"""DROP columnas legacy de equipo_fichas — Fase F final cleanup.

Después del backfill (`e8f4d9c2b1a3`) los valores de estas columnas
están en `equipo_specs`. Las columnas en `equipo_fichas` ya no se
leen desde el frontend ni desde otros endpoints — esta migration las
dropea para cerrar la deuda.

Columnas eliminadas (todas con DROP COLUMN IF EXISTS, reversible):
- `montura` (string) → migrado a equipo_specs.lens_mount
- `formato` (string) → migrado a equipo_specs.formato
- `resolucion` (string) → migrado a equipo_specs.resolucion_max
- `peso` (string) → migrado a equipo_specs.peso_g
- `dimensiones` (string) → migrado a equipo_specs.dimensions_mm
- `alimentacion` (string) → migrado a equipo_specs.alimentacion

Quedan en equipo_fichas las que NO son specs estructuradas:
- `descripcion`, `notas`, `keywords_json`, `nombre_publico_template`
- Enriquecimiento IA: `incluye_json`, `conectividad_json`,
  `compatible_con_json`, `video_url`, `precio_bh_usd`, `fuente_url`,
  `fuente_titulo`, `enriquecido_at`, `enriquecido_fuente`

Revision ID: a1b3c5e7f9d2
Revises: e8f4d9c2b1a3
Create Date: 2026-05-25
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a1b3c5e7f9d2"
down_revision: Union[str, Sequence[str], None] = "e8f4d9c2b1a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COLS = ("montura", "formato", "resolucion", "peso", "dimensiones", "alimentacion")


def upgrade() -> None:
    for col in _COLS:
        op.execute(f"ALTER TABLE equipo_fichas DROP COLUMN IF EXISTS {col}")


def downgrade() -> None:
    # Re-crea las columnas vacías. Los valores migrados quedan en
    # equipo_specs (no se restauran a equipo_fichas).
    for col in _COLS:
        op.execute(f"ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS {col} TEXT")
