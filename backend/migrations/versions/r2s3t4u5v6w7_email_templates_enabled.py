"""email_templates_enabled: on/off por plantilla de mail.

Agrega `email_templates.enabled BOOLEAN NOT NULL DEFAULT TRUE` para poder apagar
un mail automático desde la UI (/admin/settings → Emails) sin tocar código.
`services/email/service.send_email` respeta el flag (skip si está apagado); el
envío de prueba del admin lo ignora (para poder testear un template apagado).

Espeja `init_db()` (esquema en dos capas, `docs/MEMORIA.md` 2026-06-03): la
columna se crea TAMBIÉN ahí con un ADD COLUMN idempotente. `ADD COLUMN IF NOT
EXISTS` hace esta migración segura aunque el bootstrap ya la haya agregado.

Revision ID: r2s3t4u5v6w7
Revises: a7d4f1c9e2b5
Create Date: 2026-06-06
"""
from typing import Sequence, Union

from alembic import op

revision: str = "r2s3t4u5v6w7"
down_revision: Union[str, Sequence[str], None] = "a7d4f1c9e2b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE email_templates "
        "ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE email_templates DROP COLUMN IF EXISTS enabled")
