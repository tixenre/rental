"""drop tabla usuarios legacy (#76)

La tabla `usuarios` (id, email, password_hash, nombre, creado_en) era
del sistema de auth viejo con email + password. Ya no se usa en
ningún archivo del backend (verificado con grep en sesión anterior).
Auth ahora es 100% Google OAuth (admin) + Supabase (cliente).

Revision ID: 322b995843ad
Revises: 091de6e7b201
Create Date: 2026-05-11
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "322b995843ad"
down_revision: Union[str, Sequence[str], None] = "091de6e7b201"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS usuarios CASCADE")


def downgrade() -> None:
    """Recrea el schema mínimo. No restaura datos."""
    op.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id            SERIAL PRIMARY KEY,
            email         TEXT UNIQUE NOT NULL,
            nombre        TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            creado_en     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
