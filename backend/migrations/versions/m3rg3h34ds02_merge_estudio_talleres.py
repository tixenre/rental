"""Merge de cabezas Alembic divergentes: a1b2c3estudio + t4ll3r3d1c1x1.

La PR #1010 agrega a1b2c3estudio (url_sm en estudio_fotos) partiendo de
s1r2c3s4e5t6, pero en dev ya existe m3rg3h34ds01 que también parte de ese nodo,
y t4ll3r3d1c1x1 (talleres_ediciones) es otra cabeza independiente. Esta
migración de merge reconcilia ambas en una sola cabeza sin tocar esquema.

Revision ID: m3rg3h34ds02
Revises: a1b2c3estudio, t4ll3r3d1c1x1
Create Date: 2026-06-23
"""
from typing import Sequence, Union

from alembic import op

revision: str = "m3rg3h34ds02"
down_revision: Union[str, Sequence[str], None] = ("a1b2c3estudio", "t4ll3r3d1c1x1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
