"""auth_sessions — revocación de sesión server-side (logout real + "cerrar mis otras sesiones").

Allowlist de sesiones: la cookie firmada lleva un `jti` opaco y esta tabla decide
si sigue viva (`revoked_at IS NULL AND expires_at > now`). Toda sesión válida lleva
`jti` y vive acá; una cookie sin jti (viejas pre-deploy) se rechaza → re-login.
Espejo idempotente en `database/schema.py::init_db` (decisión 2026-06-03).
Discriminada por `owner_type` como `passkey_credentials`.

Revision ID: b2c4d6e8f0a1
Revises: a1f2b3c4d5e6
Create Date: 2026-06-29
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b2c4d6e8f0a1"
down_revision: Union[str, Sequence[str], None] = "a1f2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_sessions (
            jti           TEXT PRIMARY KEY,
            owner_type    TEXT NOT NULL CHECK (owner_type IN ('admin', 'cliente')),
            owner_email   TEXT NOT NULL,
            cliente_id    INTEGER REFERENCES clientes(id) ON DELETE CASCADE,
            user_agent    TEXT,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at    TIMESTAMP NOT NULL,
            revoked_at    TIMESTAMP,
            CHECK ((owner_type = 'cliente' AND cliente_id IS NOT NULL)
                OR (owner_type = 'admin'   AND cliente_id IS NULL))
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_auth_sessions_cliente "
        "ON auth_sessions(cliente_id) WHERE owner_type = 'cliente'"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_auth_sessions_admin "
        "ON auth_sessions(LOWER(owner_email)) WHERE owner_type = 'admin'"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires "
        "ON auth_sessions(expires_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS auth_sessions")
