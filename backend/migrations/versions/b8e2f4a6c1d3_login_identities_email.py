"""login_identities.email — mail asociado a la identidad (display del Google linkeado).

Guarda el mail con que se vinculó una identidad (el del Google, o el del método 'email')
para mostrarlo en "Métodos de acceso". Es **solo display**: el ancla sigue siendo
`identifier` (el `sub` estable para Google). Nullable. Espejo idempotente en
`database/schema.py::init_db`.

Revision ID: b8e2f4a6c1d3
Revises: a7f3e1c9d2b4
Create Date: 2026-06-29
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b8e2f4a6c1d3"
down_revision: Union[str, Sequence[str], None] = "a7f3e1c9d2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE login_identities ADD COLUMN IF NOT EXISTS email TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE login_identities DROP COLUMN IF EXISTS email")
