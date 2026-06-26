"""merge: une las tres cabezas abiertas al 2026-06-26.

mrgestudmain (2026-06-25) + u2v3w4x5y6z7 (media content_hash, 2026-06-24)
+ t3ll4r1nst4x1 (talleres instructor_foto_url, 2026-06-23) quedaron como
tres heads independientes. Esta migración de merge (no-op) las une para que
`alembic upgrade head` sea inequívoco antes de agregar taller_sesiones.

Revision ID: m3rg3h34ds03
Revises: mrgestudmain, u2v3w4x5y6z7, t3ll4r1nst4x1
Create Date: 2026-06-26
"""

from typing import Sequence, Union

revision: str = "m3rg3h34ds03"
down_revision: Union[str, Sequence[str], None] = (
    "mrgestudmain",
    "u2v3w4x5y6z7",
    "t3ll4r1nst4x1",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
