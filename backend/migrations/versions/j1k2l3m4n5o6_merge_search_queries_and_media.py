"""merge: search_queries + media_assets_variants

Revision ID: j1k2l3m4n5o6
Revises: i1c2d3e4f5a6, i1j2k3l4m5n6
Create Date: 2026-06-03
"""

from typing import Sequence, Union

from alembic import op

revision: str = "j1k2l3m4n5o6"
down_revision: Union[str, Sequence[str], None] = ("i1c2d3e4f5a6", "i1j2k3l4m5n6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
