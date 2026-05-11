"""normalizar valores de equipos.dueno a set canonico (Rambla|Pablo|Tincho)

Issue #90: el campo equipos.dueno era texto libre — generaba
inconsistencias por capitalización ("Pablo" vs "pablo" vs "PABLO"),
espacios, typos. Reportes por dueño quedaban fragmentados.

Esta migración normaliza los valores existentes via UPDATE case-insensitive:
- LOWER(TRIM(dueno)) = 'rambla' → 'Rambla'
- LOWER(TRIM(dueno)) = 'pablo'  → 'Pablo'
- LOWER(TRIM(dueno)) = 'tincho' → 'Tincho'
- Resto (NULL, vacío, valores raros): se quedan como están — el admin
  los corrige uno por uno desde el form (que ahora es dropdown).

NO agrega CHECK constraint todavía — preferimos tolerar valores legacy
para no romper si hay algún registro con dueño inesperado (ej: "Juan",
nombre de un dueño viejo).

Revision ID: c47b6b4e2851
Revises: 905bd97562e1
Create Date: 2026-05-11
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c47b6b4e2851"
down_revision: Union[str, Sequence[str], None] = "905bd97562e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mapeo: lowercase trimmed → canonical
NORMALIZACIONES = [
    ("rambla", "Rambla"),
    ("pablo", "Pablo"),
    ("tincho", "Tincho"),
]


def upgrade() -> None:
    """Normalizar capitalización y espacios de equipos.dueno."""
    for lowered, canonical in NORMALIZACIONES:
        op.execute(
            f"""
            UPDATE equipos
            SET dueno = '{canonical}'
            WHERE LOWER(TRIM(dueno)) = '{lowered}'
              AND dueno != '{canonical}'
            """
        )


def downgrade() -> None:
    """No-op: no tiene sentido revertir una normalización (perdemos
    información de capitalización original que ya estaba mezclada)."""
    pass
