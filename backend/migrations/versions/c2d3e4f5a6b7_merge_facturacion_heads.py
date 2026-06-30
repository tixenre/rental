"""Merge heads: a2b3c4d5e6f7 (facturas_arca) + b1c2d3e4f5a6 (emisores_arca).

Unifica las dos ramas de migración del sistema de facturación ARCA (#1139).

Revision ID: c2d3e4f5a6b7
Revises: a2b3c4d5e6f7, b1c2d3e4f5a6
Create Date: 2026-06-30
"""

from alembic import op

revision = "c2d3e4f5a6b7"
down_revision = ("a2b3c4d5e6f7", "b1c2d3e4f5a6")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
