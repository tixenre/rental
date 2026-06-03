"""equipos.estado: alinear el default 'ok' (inexistente) al enum de la app

El default histórico del schema era 'ok', un valor que no pertenece al enum de
estado de la app (operativo / en_mantenimiento / fuera_servicio). Un equipo
insertado sin estado explícito quedaba en 'ok' y el dropdown del admin no
matcheaba ninguna opción (#637). Se alinea el default a 'operativo' y se
normalizan las filas viejas que hayan quedado en 'ok'. Idempotente.

Revision ID: o1p2q3r4s5t6
Revises: n1o2p3q4r5s6
Create Date: 2026-06-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "o1p2q3r4s5t6"
down_revision: Union[str, Sequence[str], None] = "n1o2p3q4r5s6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alinear el default de columna al enum real.
    op.execute(sa.text("ALTER TABLE equipos ALTER COLUMN estado SET DEFAULT 'operativo'"))
    # Normalizar filas que hayan quedado con el default viejo.
    op.execute(sa.text("UPDATE equipos SET estado = 'operativo' WHERE estado = 'ok'"))


def downgrade() -> None:
    # El default 'ok' era un bug; no se revierte el dato. Solo el default de columna.
    op.execute(sa.text("ALTER TABLE equipos ALTER COLUMN estado SET DEFAULT 'ok'"))
