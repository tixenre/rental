"""contabilidad_cierres: congelar un mes contable (módulo contable, #809)

Cerrar un mes contable guarda una FOTO inmutable del mes (ganancia, rendición y
gastos con que se calculó) y, sobre todo, **traba la edición de movimientos**
fechados en ese mes — la red de fiabilidad del módulo. Reabrir = borrar la fila.
`mes` es 'YYYY-MM'. Es distinto del cierre de liquidación (#721, que congela el
reparto): este congela el estado de cajas/movimientos.

Espejada en init_db() (esquema en dos capas, decisión 2026-06-03). Idempotente.

Revision ID: b2c3d4e5f6a7
Revises: x8y9z0a1b2c3
Create Date: 2026-06-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "x8y9z0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.get_bind().execute(sa.text("""
        CREATE TABLE IF NOT EXISTS contabilidad_cierres (
            mes           VARCHAR(7) PRIMARY KEY,
            snapshot_json TEXT NOT NULL,
            cerrado_por   VARCHAR(255),
            cerrado_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))


def downgrade() -> None:
    op.get_bind().execute(sa.text("DROP TABLE IF EXISTS contabilidad_cierres"))
