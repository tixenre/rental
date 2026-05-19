"""uniq_solicitud_pendiente: garantizar una sola solicitud pendiente por pedido

Sin este index, dos pestañas del mismo cliente pueden pasar el check
`_check_solicitud_pendiente` en paralelo y ambas insertar una solicitud
con estado='pendiente'. El partial unique index sobre `(pedido_id)
WHERE estado='pendiente'` lo previene atómicamente a nivel DB.

Revision ID: c1d2e3f4a5b6
Revises: b7a1d9e3f4c2
Create Date: 2026-05-19
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "b7a1d9e3f4c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uniq_solicitud_pendiente_por_pedido
        ON solicitudes_modificacion (pedido_id)
        WHERE estado = 'pendiente'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uniq_solicitud_pendiente_por_pedido")
