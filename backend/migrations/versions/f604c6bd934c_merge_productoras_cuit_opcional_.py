"""merge: productoras cuit opcional + movimientos cambio divisa

Revision ID: f604c6bd934c
Revises: 9c4e7a1f2b83, z9y8x7w6v5u4
Create Date: 2026-07-05 21:40:23.005621

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f604c6bd934c'
down_revision: Union[str, Sequence[str], None] = ('9c4e7a1f2b83', 'z9y8x7w6v5u4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
