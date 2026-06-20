"""Crea el índice faltante idx_spec_def_es_compat (#921).

En init_db() dos índices se llamaban `idx_spec_def_compat` con definiciones
distintas (uno sobre `spec_key`, otro sobre `es_compatibilidad`); con
`IF NOT EXISTS` el segundo nunca se creaba. Se renombró a `idx_spec_def_es_compat`
en init_db; esta migración lo crea en las bases existentes, donde init_db ya corrió
con el nombre en colisión y el índice sobre `es_compatibilidad` nunca llegó a existir.

Espeja init_db() (esquema en dos capas, MEMORIA 2026-06-03).

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-06-20
"""

from typing import Sequence, Union

from alembic import op

revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, Sequence[str], None] = "h8i9j0k1l2m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_spec_def_es_compat "
        "ON spec_definitions(es_compatibilidad) WHERE es_compatibilidad"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_spec_def_es_compat")
