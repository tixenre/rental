"""emisores_arca.habilitado_exportacion — flag de habilitación WSFEXv1

Espeja init_db(). Un emisor necesita una relación de servicio AFIP SEPARADA de "wsfe" para
facturar exportación (mismo mecanismo que ya exige el padrón) — sin este flag explícito, un intento
de facturar exportación con un emisor sin esa relación delegada falla recién al pegarle a AFIP.

Revision ID: s2t3u4v5w6x7
Revises: r1s2t3u4v5w6
Create Date: 2026-07-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "s2t3u4v5w6x7"
down_revision: Union[str, Sequence[str], None] = "r1s2t3u4v5w6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE emisores_arca
            ADD COLUMN IF NOT EXISTS habilitado_exportacion BOOLEAN NOT NULL DEFAULT false
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE emisores_arca DROP COLUMN IF EXISTS habilitado_exportacion")
