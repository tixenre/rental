"""merge heads: talleres notif_email + didit estado verificación.

Migración de merge (sin schema). Une las dos cabezas divergentes que quedaron
al ramificar desde `z0a1b2c3d4e5`:

- `t2n3o4t5i6f7` (talleres: columna notif_email + templates dinámicos)
- `d1e2f3a4b5c6` (didit: estado_verificacion)

Ambas parten del mismo ancestro común; este merge las reconcilia en una sola
head para que `alembic upgrade head` no falle por branches divergentes.

Revision ID: m1e2r3g4e5h6
Revises: d1e2f3a4b5c6, t2n3o4t5i6f7
Create Date: 2026-06-20
"""

from typing import Sequence, Union

revision: str = "m1e2r3g4e5h6"
down_revision: Union[str, Sequence[str], None] = ("d1e2f3a4b5c6", "t2n3o4t5i6f7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
