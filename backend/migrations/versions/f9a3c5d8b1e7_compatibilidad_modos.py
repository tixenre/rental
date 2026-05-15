"""compatibilidad_modo en spec_definitions + rol_compatibilidad en asignaciones

Habilita el modelo de compatibilidad automática multi-modo:
- exacta: A.value == B.value ⇒ match (HDMI, montura, conexión).
- jerarquica: enum_options ordenado; position-based con rol contenedor/contenido.

Revision ID: f9a3c5d8b1e7
Revises: e8f4c2a1d7b9
Create Date: 2026-05-15
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f9a3c5d8b1e7"
down_revision: Union[str, Sequence[str], None] = "e8f4c2a1d7b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE spec_definitions "
        "ADD COLUMN IF NOT EXISTS compatibilidad_modo VARCHAR(16) NOT NULL DEFAULT 'exacta'"
    )
    op.execute(
        "ALTER TABLE spec_definitions "
        "DROP CONSTRAINT IF EXISTS spec_definitions_compat_modo_check"
    )
    op.execute(
        "ALTER TABLE spec_definitions "
        "ADD CONSTRAINT spec_definitions_compat_modo_check "
        "CHECK (compatibilidad_modo IN ('exacta', 'jerarquia'))"
    )

    op.execute(
        "ALTER TABLE categoria_spec_templates "
        "ADD COLUMN IF NOT EXISTS rol_compatibilidad VARCHAR(16)"
    )
    op.execute(
        "ALTER TABLE categoria_spec_templates "
        "DROP CONSTRAINT IF EXISTS categoria_spec_templates_rol_check"
    )
    op.execute(
        "ALTER TABLE categoria_spec_templates "
        "ADD CONSTRAINT categoria_spec_templates_rol_check "
        "CHECK (rol_compatibilidad IS NULL OR rol_compatibilidad IN ('contenedor', 'contenido'))"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE categoria_spec_templates "
        "DROP CONSTRAINT IF EXISTS categoria_spec_templates_rol_check"
    )
    op.execute(
        "ALTER TABLE categoria_spec_templates "
        "DROP COLUMN IF EXISTS rol_compatibilidad"
    )
    op.execute(
        "ALTER TABLE spec_definitions "
        "DROP CONSTRAINT IF EXISTS spec_definitions_compat_modo_check"
    )
    op.execute(
        "ALTER TABLE spec_definitions "
        "DROP COLUMN IF EXISTS compatibilidad_modo"
    )
