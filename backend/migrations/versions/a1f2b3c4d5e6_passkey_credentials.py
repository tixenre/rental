"""passkey_credentials — login con passkey (WebAuthn/FIDO2), aditivo a Google OAuth.

Una sola tabla para admin (owner_email, cliente_id NULL) y cliente (cliente_id
seteado), discriminada por `owner_type`. credential_id / public_key en base64url
TEXT. Espejo idempotente en `database/schema.py::init_db` (decisión 2026-06-03).

Revision ID: a1f2b3c4d5e6
Revises: f9a1c3e5b7d2
Create Date: 2026-06-28
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a1f2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "f9a1c3e5b7d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS passkey_credentials (
            id             SERIAL PRIMARY KEY,
            owner_type     TEXT NOT NULL CHECK (owner_type IN ('admin', 'cliente')),
            owner_email    TEXT NOT NULL,
            cliente_id     INTEGER REFERENCES clientes(id) ON DELETE CASCADE,
            credential_id  TEXT NOT NULL UNIQUE,
            public_key     TEXT NOT NULL,
            sign_count     BIGINT NOT NULL DEFAULT 0,
            transports     TEXT,
            aaguid         TEXT,
            device_name    TEXT,
            user_handle    TEXT NOT NULL,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used_at   TIMESTAMP,
            CHECK ((owner_type = 'cliente' AND cliente_id IS NOT NULL)
                OR (owner_type = 'admin'   AND cliente_id IS NULL))
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_passkey_cred_cliente "
        "ON passkey_credentials(cliente_id) WHERE owner_type = 'cliente'"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_passkey_cred_admin "
        "ON passkey_credentials(LOWER(owner_email)) WHERE owner_type = 'admin'"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS passkey_credentials")
