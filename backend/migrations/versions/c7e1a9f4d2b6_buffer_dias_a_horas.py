"""buffer de alquiler: días → horas

Renombra el setting `buffer_dias_alquiler` → `buffer_horas_alquiler` y
convierte el valor multiplicándolo por 24 (1 día = 24 horas), preservando el
gap configurado. El overlap de disponibilidad ahora respeta la hora de
retiro/devolución (ver `_rango_con_buffer`), no solo el día.

Solo afecta la fila existente en `app_settings` (si la hay). El guard
`value ~ '^[0-9]+$'` evita romper si el valor no es entero.

Revision ID: c7e1a9f4d2b6
Revises: f4b9d2a7c3e8
Create Date: 2026-05-24
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c7e1a9f4d2b6"
down_revision: Union[str, Sequence[str], None] = "f4b9d2a7c3e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE app_settings
           SET key = 'buffer_horas_alquiler',
               value = CAST(CAST(value AS INTEGER) * 24 AS TEXT)
         WHERE key = 'buffer_dias_alquiler'
           AND value ~ '^[0-9]+$'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE app_settings
           SET key = 'buffer_dias_alquiler',
               value = CAST(CAST(value AS INTEGER) / 24 AS TEXT)
         WHERE key = 'buffer_horas_alquiler'
           AND value ~ '^[0-9]+$'
        """
    )
