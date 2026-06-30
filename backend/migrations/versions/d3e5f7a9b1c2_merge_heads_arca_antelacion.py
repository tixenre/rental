"""Merge: facturacion ARCA heads + antelacion_minima_horas de dev.

Unifica c2d3e4f5a6b7 (merge emisores_arca + facturas) y c2d4e6f8a0b2
(antelacion_minima_horas) en un único head.

Revision ID: d3e5f7a9b1c2
Revises: c2d3e4f5a6b7, c2d4e6f8a0b2
Create Date: 2026-06-30
"""

from typing import Sequence, Union

revision: str = "d3e5f7a9b1c2"
down_revision: Union[str, Sequence[str], None] = ("c2d3e4f5a6b7", "c2d4e6f8a0b2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
