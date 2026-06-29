"""identity Fase 2 — verified_contacts + kyc_events + consentimiento/conflicto.

Base del motor `backend/identity/` (MEMORIA: motor único "quién sos"). Agrega:
  - verified_contacts: mail/teléfono verificados (Google/Didit/OTP) → comunicación + recuperación.
  - kyc_events: bitácora de auditoría del KYC, SOLO TEXTO (Ley 25.326).
  - clientes.kyc_consent_at: consentimiento explícito del KYC.
  - clientes.identidad_conflicto: marca de conflicto de dedup → estado derivado 'conflicto'.

El índice único parcial de CUIL va en una migración aparte, AL FINAL (tras limpiar
duplicados legacy). Espejo idempotente en database/schema.py::init_db.

Revision ID: 1d3nt1dadf2a
Revises: b8e2f4a6c1d3
Create Date: 2026-06-29
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1d3nt1dadf2a"
down_revision: Union[str, Sequence[str], None] = "b8e2f4a6c1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS kyc_consent_at TIMESTAMP")
    op.execute(
        "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS "
        "identidad_conflicto BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute("""
        CREATE TABLE IF NOT EXISTS verified_contacts (
            id            SERIAL PRIMARY KEY,
            cliente_id    INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
            kind          TEXT NOT NULL CHECK (kind IN ('email', 'phone')),
            value         TEXT NOT NULL,
            source        TEXT NOT NULL CHECK (source IN ('google', 'didit', 'otp', 'manual')),
            verified_at   TIMESTAMP,
            is_disposable BOOLEAN,
            is_virtual    BOOLEAN,
            is_breached   BOOLEAN,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (cliente_id, kind, value)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_verified_contacts_cliente ON verified_contacts(cliente_id)"
    )
    op.execute("""
        CREATE TABLE IF NOT EXISTS kyc_events (
            id          SERIAL PRIMARY KEY,
            cliente_id  INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
            evento      TEXT NOT NULL,
            detalle     TEXT,
            session_id  TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_kyc_events_cliente ON kyc_events(cliente_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS kyc_events")
    op.execute("DROP TABLE IF EXISTS verified_contacts")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS identidad_conflicto")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS kyc_consent_at")
