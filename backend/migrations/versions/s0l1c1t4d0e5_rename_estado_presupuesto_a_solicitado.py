"""Rename del estado `presupuesto` → `solicitado`.

El estado inicial de un pedido se llamaba `presupuesto` internamente pero se
mostraba "Solicitud" en la app — nombre interno inconsistente con lo visible
(deuda que confunde al leer el estado crudo en logs/exports/queries). Se
renombra el VALOR del estado a `solicitado` (el label visible sigue "Solicitud").
El documento PDF "Presupuesto"/cotización es INDEPENDIENTE del estado y NO cambia.

`solicitado` reserva stock igual que `presupuesto` (era, y sigue, parte de
`reservas.estados.ESTADOS_RESERVADO`) — este rename NO cambia la conducta del
motor de reservas, solo el nombre del estado.

Migra las filas existentes + el DEFAULT de la columna. En paridad con
`database/schema.py::init_db()` (el DEFAULT ya quedó en 'solicitado' ahí). NO
había ningún pedido con estado 'solicitado' antes de este rename (era solo un
estado de display del portal), así que el downgrade es seguro y reversible.

Revision ID: s0l1c1t4d0e5
Revises: t3l3f0n0bkfl
Create Date: 2026-07-14
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "s0l1c1t4d0e5"
down_revision: Union[str, Sequence[str], None] = "t3l3f0n0bkfl"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Filas existentes: presupuesto → solicitado.
    op.execute(text("UPDATE alquileres SET estado = 'solicitado' WHERE estado = 'presupuesto'"))
    # Default de la columna (en paridad con schema.py::init_db).
    op.execute(text("ALTER TABLE alquileres ALTER COLUMN estado SET DEFAULT 'solicitado'"))


def downgrade() -> None:
    op.execute(text("ALTER TABLE alquileres ALTER COLUMN estado SET DEFAULT 'presupuesto'"))
    op.execute(text("UPDATE alquileres SET estado = 'presupuesto' WHERE estado = 'solicitado'"))
