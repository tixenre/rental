"""login_identities + auth_challenges — fundación passwordless (Fase 1 identidad).

- `login_identities`: las N llaves de login (Google `sub` / mail) que apuntan a UNA
  cuenta (`clientes.id`). Generaliza "método de login → cuenta"; `UNIQUE(method,
  identifier)` = una llave apunta a una sola cuenta. Passkey sigue en su propia tabla.
- `auth_challenges`: backing store del magic-link por mail (link de un solo uso).

Backfill: cada cliente existente recibe su identidad 'email' (su mail actual, verificada)
→ el lookup por mail y el magic-link andan desde el día uno; el `sub` de Google se
backfillea perezosamente en el próximo login (fallback por mail en `identities_store`).

Espejo idempotente en `database/schema.py::init_db` (decisión 2026-06-03).

Revision ID: f3b8d1a6c9e2
Revises: e5a7c9b1d3f4
Create Date: 2026-06-29
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f3b8d1a6c9e2"
down_revision: Union[str, Sequence[str], None] = "e5a7c9b1d3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS login_identities (
            id           SERIAL PRIMARY KEY,
            cliente_id   INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
            method       TEXT NOT NULL CHECK (method IN ('google', 'passkey', 'email')),
            identifier   TEXT NOT NULL,
            verified_at  TIMESTAMP,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (method, identifier)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_login_identities_cliente "
        "ON login_identities(cliente_id)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_challenges (
            id           SERIAL PRIMARY KEY,
            kind         TEXT NOT NULL CHECK (kind IN ('magic_link')),
            email        TEXT NOT NULL,
            token_hash   TEXT NOT NULL UNIQUE,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at   TIMESTAMP NOT NULL,
            used_at      TIMESTAMP,
            attempts     INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_auth_challenges_email "
        "ON auth_challenges(LOWER(email))"
    )
    # Backfill: identidad 'email' (verificada) por cada cliente con mail. ON CONFLICT
    # DO NOTHING por si el índice case-insensitive ya tuviera colisiones raras.
    op.execute(
        """
        INSERT INTO login_identities (cliente_id, method, identifier, verified_at)
        SELECT id, 'email', LOWER(email), CURRENT_TIMESTAMP
        FROM clientes
        WHERE email IS NOT NULL AND email <> ''
        ON CONFLICT (method, identifier) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS auth_challenges")
    op.execute("DROP TABLE IF EXISTS login_identities")
