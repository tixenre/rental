"""merge_heads: unir rama normalizar_enums + rama cliente_favoritos

Revision ID: e1f2a3b4c5d6
Revises: d9e3f1a5c2b7, f1a9c7e3b5d2
Create Date: 2026-06-01
"""

from typing import Sequence, Union

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = ("d9e3f1a5c2b7", "f1a9c7e3b5d2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
