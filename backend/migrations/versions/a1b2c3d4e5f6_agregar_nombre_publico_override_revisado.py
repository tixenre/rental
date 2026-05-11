"""agregar nombre_publico_override y nombre_publico_revisado a equipos

Columnas requeridas por calcular_nombres_para() en nombre_service.py.
Sin ellas, cualquier save de ficha que active el recálculo de nombres
(campos montura/formato/resolucion/nombre_publico_template) falla con
UndefinedColumn, envenena la transacción y devuelve 500.

Revision ID: a1b2c3d4e5f6
Revises: d4f8a2b1e6c3
Create Date: 2026-05-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "d4f8a2b1e6c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE equipos "
        "ADD COLUMN IF NOT EXISTS nombre_publico_override TEXT"
    )
    op.execute(
        "ALTER TABLE equipos "
        "ADD COLUMN IF NOT EXISTS nombre_publico_revisado BOOLEAN DEFAULT FALSE"
    )


def downgrade() -> None:
    pass
