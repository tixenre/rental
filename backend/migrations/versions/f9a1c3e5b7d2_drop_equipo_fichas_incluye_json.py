"""deprecación: drop equipo_fichas.incluye_json — enriquecimiento legacy (F5).

`incluye_json` era la lista descriptiva (JSON de strings) del enriquecimiento IA
viejo. Quedó muerta en la UI: el "qué incluye un kit/combo" se deriva de
`kit_componentes` (la receta real que el motor reserva) vía la puerta única
`services.contenido`. Se dropea para cerrar la redundancia.

NO toca:
- `contenido_incluido_json` (descriptivo manual editable — SE QUEDA).
- `conectividad_json` / `compatible_con_json` (se siguen mostrando en la ficha).
- `kit_componentes` (la receta real, en otra tabla).

Espejo en `database/schema.py::init_db` (decisión 2026-06-03): el ALTER ADD de
`incluye_json` ya se removió ahí, así que las BDs nuevas no la crean.

Revision ID: f9a1c3e5b7d2
Revises: e1d2c3i4o5n6
Create Date: 2026-06-28
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f9a1c3e5b7d2"
down_revision: Union[str, Sequence[str], None] = "e1d2c3i4o5n6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE equipo_fichas DROP COLUMN IF EXISTS incluye_json")


def downgrade() -> None:
    op.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS incluye_json TEXT")
