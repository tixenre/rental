"""Tabla para propuestas IA del skill gear-compatibility

El skill genera propuestas de:
- enum_option nueva (agregar a una spec_definition existente)
- spec_nueva (crear una nueva spec_definition)
- merge_specs (consolidar specs duplicadas)

Las propuestas NO se aplican automáticamente — el dueño las aprueba o
descarta desde /admin/specs/propuestas.

Revision ID: c3e5f7a9d2b4
Revises: b2d4f6a8c1e3
Create Date: 2026-05-15
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c3e5f7a9d2b4"
down_revision: Union[str, Sequence[str], None] = "b2d4f6a8c1e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS spec_propuestas_pendientes (
            id            SERIAL PRIMARY KEY,
            tipo          VARCHAR(20) NOT NULL,
            payload       JSONB       NOT NULL,
            origen        VARCHAR(64),
            confianza     REAL,
            created_at    TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
            aplicado_at   TIMESTAMP,
            descartado_at TIMESTAMP,
            CHECK (tipo IN ('enum_option', 'spec_nueva', 'merge_specs'))
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_propuestas_pendientes "
        "ON spec_propuestas_pendientes(created_at DESC) "
        "WHERE aplicado_at IS NULL AND descartado_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_propuestas_pendientes")
    op.execute("DROP TABLE IF EXISTS spec_propuestas_pendientes")
