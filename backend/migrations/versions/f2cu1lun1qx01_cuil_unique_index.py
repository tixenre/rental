"""identity Fase 2 — índice único parcial de CUIL (ancla "una persona = una cuenta").

ÚLTIMO paso de Fase 2: el candado a nivel DB que vuelve IMPOSIBLE dos cuentas
verificadas con el mismo CUIL. PARCIAL — solo aplica a verificados:
`WHERE cuil IS NOT NULL AND dni_validado_at IS NOT NULL`. Así no rompe a los
no-verificados ni a los extranjeros sin CUIL (cuil NULL nunca entra al índice).

⚠️ ORDEN: esta migración exige que NO haya duplicados legacy. Si los hay, falla con
UniqueViolation (correcto para una migración deliberada: es la señal de "deduplicá
primero"). Deduplicá con `identity.merge.candidatos_duplicados` → `merge_accounts`
ANTES de aplicarla. El espejo en `init_db` es resiliente (no rompe el boot); esta
migración es fail-loud a propósito.

Revision ID: f2cu1lun1qx01
Revises: 1d3nt1dadf2a
Create Date: 2026-06-29
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f2cu1lun1qx01"
down_revision: Union[str, Sequence[str], None] = "1d3nt1dadf2a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uniq_cliente_cuil_verificado "
        "ON clientes (cuil) WHERE cuil IS NOT NULL AND dni_validado_at IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uniq_cliente_cuil_verificado")
