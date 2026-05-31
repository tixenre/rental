"""descuentos FLOAT → NUMERIC(5,2) para evitar error de redondeo flotante

Los porcentajes de descuento se guardaban como FLOAT (double precision).
Un 10% almacenado como 0.09999999... aplicado a $5000 puede dar $499.99
que redondea a $499 en vez de $500 — error de ±1 ARS por operación.
Bloqueante antes de facturación electrónica (AFIP no tolera diferencias
de redondeo).

Columnas migradas:
- alquileres.descuento_pct         (% de descuento del cliente para este pedido)
- alquileres.descuento_jornadas_pct (% de descuento por cantidad de jornadas)
- clientes.descuento                (% de descuento permanente del cliente)
- descuentos_jornada.pct           (tabla de escala de descuentos por jornadas)

Revision ID: g1a2b3c4d5e6
Revises: f9a3c5d8b1e7
Create Date: 2026-05-31
"""
from typing import Sequence, Union

from alembic import op

revision: str = "g1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "f1a9c7e3b5d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Usar USING para la conversión explícita — PostgreSQL requiere USING
    # cuando el tipo cambia (incluso de FLOAT a NUMERIC son tipos distintos).
    op.execute(
        "ALTER TABLE alquileres "
        "ALTER COLUMN descuento_pct TYPE NUMERIC(5,2) "
        "USING ROUND(descuento_pct::NUMERIC, 2)"
    )
    op.execute(
        "ALTER TABLE alquileres "
        "ALTER COLUMN descuento_jornadas_pct TYPE NUMERIC(5,2) "
        "USING ROUND(descuento_jornadas_pct::NUMERIC, 2)"
    )
    op.execute(
        "ALTER TABLE clientes "
        "ALTER COLUMN descuento TYPE NUMERIC(5,2) "
        "USING ROUND(descuento::NUMERIC, 2)"
    )
    op.execute(
        "ALTER TABLE descuentos_jornada "
        "ALTER COLUMN pct TYPE NUMERIC(5,2) "
        "USING ROUND(pct::NUMERIC, 2)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE alquileres "
        "ALTER COLUMN descuento_pct TYPE FLOAT "
        "USING descuento_pct::FLOAT"
    )
    op.execute(
        "ALTER TABLE alquileres "
        "ALTER COLUMN descuento_jornadas_pct TYPE FLOAT "
        "USING descuento_jornadas_pct::FLOAT"
    )
    op.execute(
        "ALTER TABLE clientes "
        "ALTER COLUMN descuento TYPE FLOAT "
        "USING descuento::FLOAT"
    )
    op.execute(
        "ALTER TABLE descuentos_jornada "
        "ALTER COLUMN pct TYPE FLOAT "
        "USING pct::FLOAT"
    )
