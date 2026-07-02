"""afip_ta: columna servicio — un TA es por (ambiente, emisor, SERVICIO), no
solo (ambiente, emisor).

Hasta ahora `afip_ta` asumía implícitamente un único servicio ("wsfe"): la PK
era (ambiente, emisor). El padrón de AFIP (ws_sr_padron_a13, para autocompletar
razón social/domicilio/condición IVA a partir de un CUIT — MEMORIA 2026-07-02)
necesita su PROPIO TA por emisor (WSAA autentica una relación CUIT↔servicio; el
TA de "wsfe" no sirve para consultar el padrón). Se agrega `servicio` a la PK
para poder cachear ambos TAs en paralelo sin pisarse.

Espeja init_db() (esquema en dos capas, MEMORIA 2026-06-03).

Revision ID: f1a2b3c4d5e6
Revises: e4f6a8b0c2d4
Create Date: 2026-07-02
"""

from typing import Sequence, Union

from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e4f6a8b0c2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE afip_ta ADD COLUMN IF NOT EXISTS servicio TEXT NOT NULL DEFAULT 'wsfe'"
    )
    op.execute("ALTER TABLE afip_ta DROP CONSTRAINT IF EXISTS afip_ta_pkey")
    op.execute(
        "ALTER TABLE afip_ta ADD CONSTRAINT afip_ta_pkey PRIMARY KEY (ambiente, emisor, servicio)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE afip_ta DROP CONSTRAINT IF EXISTS afip_ta_pkey")
    op.execute("DELETE FROM afip_ta WHERE servicio <> 'wsfe'")
    op.execute(
        "ALTER TABLE afip_ta ADD CONSTRAINT afip_ta_pkey PRIMARY KEY (ambiente, emisor)"
    )
    op.execute("ALTER TABLE afip_ta DROP COLUMN IF EXISTS servicio")
