"""merge heads: afip_ta.servicio + facturas centavos numeric

Revision ID: 6e8e632e32da
Revises: f1a2b3c4d5e6, h3i4j5k6l7m8
Create Date: 2026-07-03 00:55:32.149291

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6e8e632e32da'
down_revision: Union[str, Sequence[str], None] = ('f1a2b3c4d5e6', 'h3i4j5k6l7m8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
