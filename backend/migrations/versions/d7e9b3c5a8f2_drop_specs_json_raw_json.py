"""drop equipo_fichas.specs_json y raw_json (Fase E del refactor de specs)

Las specs estructuradas viven en `equipo_specs` desde el PR #456 (admin)
y la Fase D (catálogo público). `specs_json` y `raw_json` quedaron sin
lectores activos tras el refactor — esta migration las dropea.

`raw_json` era write-only (cache del scrape B&H, nadie leía).
`specs_json` era el campo legacy que tanto admin como catálogo público
consumían; ya migrados a `equipo.specs` (estructurada desde equipo_specs).

Las otras columnas legacy de equipo_fichas (`montura`, `formato`,
`resolucion`, `peso`, `dimensiones`, `alimentacion`, `incluye_json`,
`conectividad_json`, `compatible_con_json`) SIGUEN presentes — son
escritas por el enriquecimiento IA del autocompletar y leídas como
fallback por el catálogo. Su migración a equipo_specs queda para Fase F.

Revision ID: d7e9b3c5a8f2
Revises: c7e1a9f4d2b6
Create Date: 2026-05-24
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d7e9b3c5a8f2"
down_revision: Union[str, Sequence[str], None] = "c7e1a9f4d2b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE equipo_fichas DROP COLUMN IF EXISTS specs_json")
    op.execute("ALTER TABLE equipo_fichas DROP COLUMN IF EXISTS raw_json")


def downgrade() -> None:
    # Re-crea las columnas vacías. Los datos previos NO se restauran
    # (los specs estructurados ya están en equipo_specs).
    op.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS specs_json TEXT")
    op.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS raw_json TEXT")
