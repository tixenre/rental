"""liquidacion_cierres: congelar la foto de un mes liquidado (#721)

Cerrar un mes guarda una FOTO inmutable del reporte de liquidación de ese mes
(los números Y el modelo de comisiones con que se calculó). Mientras está cerrado
el reporte se sirve desde la foto, inmune a cambios posteriores (modelo o pedidos);
reabrir = borrar la fila. `mes` es 'YYYY-MM'.

La tabla está espejada en init_db() (database.py) —esquema en dos capas, decisión
2026-06-03: toda tabla nueva va TAMBIÉN en init_db()— así existe aunque esta
migración no llegue a correr. Idempotente (IF NOT EXISTS) para convivir con el
bootstrap.

Revision ID: q1r2s3t4u5v6
Revises: p1q2r3s4t5u6
Create Date: 2026-06-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "q1r2s3t4u5v6"
down_revision: Union[str, Sequence[str], None] = "p1q2r3s4t5u6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.get_bind().execute(sa.text("""
        CREATE TABLE IF NOT EXISTS liquidacion_cierres (
            mes           VARCHAR(7) PRIMARY KEY,
            snapshot_json TEXT NOT NULL,
            modelo_json   TEXT NOT NULL,
            cerrado_por   VARCHAR(255),
            cerrado_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))


def downgrade() -> None:
    op.get_bind().execute(sa.text("DROP TABLE IF EXISTS liquidacion_cierres"))
