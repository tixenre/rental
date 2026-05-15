"""descuentos por jornadas (interpolación lineal entre puntos ancla)

Revision ID: a3e7f1d2b8c4
Revises: f17e3a8b4c92
Create Date: 2026-05-15
"""
from typing import Sequence, Union
from alembic import op

revision: str = "a3e7f1d2b8c4"
down_revision: Union[str, Sequence[str], None] = "f17e3a8b4c92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS descuentos_jornada (
            id         SERIAL PRIMARY KEY,
            jornadas   INTEGER NOT NULL UNIQUE,
            pct        FLOAT   NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute(
        "ALTER TABLE alquileres "
        "ADD COLUMN IF NOT EXISTS descuento_jornadas_pct FLOAT DEFAULT 0"
    )


def downgrade() -> None:
    pass
