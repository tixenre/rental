"""merge heads: une las dos cabezas divergentes que cuelgan de cart0sact1vos.

Dos migraciones tomaron el mismo padre (`cart0sact1vos`) y quedaron como
cabezas paralelas:
  - s1r2c3s4e5t6 (equipos_foto_url_sm)
  - s3rv3r3rr0rs (server_errors)

Esta revisión de merge las unifica para que `alembic upgrade head` resuelva
a una sola cabeza. No tiene operaciones de esquema (un merge solo reconcilia
el historial de revisiones).

Revision ID: m3rg3h34ds01
Revises: s1r2c3s4e5t6, s3rv3r3rr0rs
Create Date: 2026-06-23
"""

from typing import Sequence, Union

revision: str = "m3rg3h34ds01"
down_revision: Union[str, Sequence[str], None] = ("s1r2c3s4e5t6", "s3rv3r3rr0rs")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
