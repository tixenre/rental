"""clientes livianas — alta passwordless con passkey (Fase 4 identidad).

Relaja los NOT NULL de los campos base de `clientes` (nombre/apellido/telefono/email/
direccion/cuit) para permitir **cuentas livianas**: la cuenta nace solo con `id` + una
passkey, SIN datos. La identidad/contacto los completa Didit al primer pedido, y los
escribe en las columnas `*_renaper` (con COALESCE) — no en estos campos base. El `UNIQUE`
de `email` se mantiene (Postgres permite múltiples NULL). `cuenta_estado` ('liviana' /
'completa') marca la cuenta vacía; las existentes quedan 'completa'.

El gate `require_cliente_verificado` (mira `dni_validado_at`) deja las livianas inertes
hasta verificar — no pueden pedir. Espejo idempotente en `database/schema.py::init_db`.

Revision ID: a7f3e1c9d2b4
Revises: f3b8d1a6c9e2
Create Date: 2026-06-29
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a7f3e1c9d2b4"
down_revision: Union[str, Sequence[str], None] = "f3b8d1a6c9e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE clientes ALTER COLUMN nombre DROP NOT NULL")
    op.execute("ALTER TABLE clientes ALTER COLUMN apellido DROP NOT NULL")
    op.execute("ALTER TABLE clientes ALTER COLUMN telefono DROP NOT NULL")
    op.execute("ALTER TABLE clientes ALTER COLUMN email DROP NOT NULL")
    op.execute("ALTER TABLE clientes ALTER COLUMN direccion DROP NOT NULL")
    op.execute("ALTER TABLE clientes ALTER COLUMN cuit DROP NOT NULL")
    op.execute(
        "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS cuenta_estado TEXT NOT NULL DEFAULT 'completa'"
    )


def downgrade() -> None:
    # No se re-impone NOT NULL: podría haber cuentas livianas con NULL → fallaría.
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS cuenta_estado")
