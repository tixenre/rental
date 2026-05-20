"""factura_a_fields: campos para emisión de Factura A en clientes RI

Agrega:
- razon_social: nombre legal en factura (≠ apellido/nombre persona).
- domicilio_fiscal: dirección fiscal (puede diferir de la dirección de entrega).
- email_facturacion: email a donde enviar la factura (puede diferir del email login).

Sólo aplican cuando `perfil_impuestos = 'responsable_inscripto'`. Para el
resto de los perfiles quedan NULL y no se piden.

Revision ID: d3e4f5a6b7c8
Revises: c1d2e3f4a5b6
Create Date: 2026-05-19
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS razon_social TEXT")
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS domicilio_fiscal TEXT")
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS email_facturacion TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS email_facturacion")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS domicilio_fiscal")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS razon_social")
