"""spec_definitions.output_config — config declarativa de render de placeholder

Permite que el spec_definition declare cómo se rinde como placeholder
({spec:Label}) en el nombre público. Inicialmente soporta:
  - row_strategy: "all" | "first" | "last"  (solo para tipo='tabla')

NULL significa "default" (row_strategy=all). Sin backfill — los specs
existentes mantienen comportamiento actual.

Revision ID: a8c1b3d5e9f2
Revises: d7c9e1f3a8b2
Create Date: 2026-05-15
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a8c1b3d5e9f2"
down_revision: Union[str, Sequence[str], None] = "d7c9e1f3a8b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE spec_definitions "
        "ADD COLUMN IF NOT EXISTS output_config JSONB NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE spec_definitions DROP COLUMN IF EXISTS output_config")
