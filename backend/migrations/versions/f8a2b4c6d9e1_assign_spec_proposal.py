"""permitir tipo 'assign_spec' en spec_propuestas_pendientes

Nuevo tipo de propuesta IA: cuando el autocompletar detecta una spec que
existe en el catálogo global pero NO está asignada a la categoría del
equipo, propone asignarla (en lugar de crear duplicado).

Revision ID: f8a2b4c6d9e1
Revises: e7b3d5f9a1c2
Create Date: 2026-05-15
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f8a2b4c6d9e1"
down_revision: Union[str, Sequence[str], None] = "e7b3d5f9a1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE spec_propuestas_pendientes "
        "DROP CONSTRAINT IF EXISTS spec_propuestas_pendientes_tipo_check"
    )
    op.execute(
        "ALTER TABLE spec_propuestas_pendientes "
        "ADD CONSTRAINT spec_propuestas_pendientes_tipo_check "
        "CHECK (tipo IN ('enum_option', 'spec_nueva', 'merge_specs', 'assign_spec'))"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE spec_propuestas_pendientes "
        "DROP CONSTRAINT IF EXISTS spec_propuestas_pendientes_tipo_check"
    )
    op.execute(
        "ALTER TABLE spec_propuestas_pendientes "
        "ADD CONSTRAINT spec_propuestas_pendientes_tipo_check "
        "CHECK (tipo IN ('enum_option', 'spec_nueva', 'merge_specs'))"
    )
