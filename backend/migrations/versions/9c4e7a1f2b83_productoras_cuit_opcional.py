"""productoras: cuit/perfil_impuestos/verificado_at nullable (borrador sin CUIT) — #1251 Fase 3

Revision ID: 9c4e7a1f2b83
Revises: 7b3f0e19d2ac
Create Date: 2026-07-05
"""
from typing import Sequence, Union
from alembic import op

revision: str = "9c4e7a1f2b83"
down_revision: Union[str, Sequence[str], None] = "7b3f0e19d2ac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE productoras ALTER COLUMN cuit DROP NOT NULL")
    op.execute("ALTER TABLE productoras ALTER COLUMN perfil_impuestos DROP NOT NULL")
    op.execute("ALTER TABLE productoras ALTER COLUMN verificado_at DROP NOT NULL")


def downgrade() -> None:
    """No-op: revertir exigiría primero eliminar/completar las productoras
    borrador (sin cuit) que se hayan cargado — no se puede hacer a ciegas."""
    pass
