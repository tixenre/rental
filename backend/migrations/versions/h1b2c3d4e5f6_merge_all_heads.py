"""merge_all_heads: unir e1f2a3b4c5d6 + g1a2b3c4d5e6

Revision ID: h1b2c3d4e5f6
Revises: e1f2a3b4c5d6, g1a2b3c4d5e6
Create Date: 2026-06-01
"""

from typing import Sequence, Union

revision: str = "h1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = ("e1f2a3b4c5d6", "g1a2b3c4d5e6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
