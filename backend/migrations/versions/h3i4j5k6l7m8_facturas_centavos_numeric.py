"""facturas: imp_neto/imp_iva/imp_total INTEGER → NUMERIC(12,2) (bug #1209)

El motor de facturación (`services/facturacion/engine.py`) calcula el neto/IVA/total
EXACTOS al centavo en Decimal (`arca_fe.calcular_importes`) y esos son los valores
que se le mandan a ARCA (`armar_fecae`) y se codifican en el QR fiscal (`armar_qr`)
para obtener el CAE. Pero al persistir la fila en `facturas` esos valores se
truncaban a entero (`int(round(float(...)))`) porque la tabla seguía la convención
de "enteros ARS" de la plata interna (`backend/contabilidad/`, 2026-06-07).

Esa convención no aplica acá: `facturas` es un documento FISCAL, no plata interna.
Una factura cuyo neto no sea múltiplo de 100 (ej. neto=$1001, IVA=21% → $210,21)
quedaba con `imp_iva=210`/`imp_total=1211` en la tabla y en el PDF impreso, mientras
el CAE/QR ya autorizados ante ARCA decían $210,21/$1211,21 — el comprobante legal
impreso quedaba por debajo de lo que ARCA realmente autorizó.

Fix: la columna pasa a NUMERIC(12,2) y `engine.py` deja de truncar — persiste el
mismo Decimal que ya se le mandó a ARCA. `pdf.py` no necesita cambios: `_money`/
`_plain` ya formatean con `.2f`, solo mostraban "00" de centavos porque el valor
guardado ya venía sin ellos.

Espeja init_db() (esquema en dos capas, MEMORIA 2026-06-03). USING cast simple
(sin ROUND: los valores existentes son enteros, no hay parte fraccionaria que
perder al pasar de INTEGER a NUMERIC — a diferencia de la migración inversa de
g1a2b3c4d5e6, acá no hay pérdida de precisión posible en ningún sentido).

Revision ID: h3i4j5k6l7m8
Revises: c5d6e7f8g9h0
Create Date: 2026-07-03
"""

from typing import Sequence, Union

from alembic import op

revision: str = "h3i4j5k6l7m8"
down_revision: Union[str, Sequence[str], None] = "c5d6e7f8g9h0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE facturas ALTER COLUMN imp_neto TYPE NUMERIC(12,2) "
        "USING imp_neto::NUMERIC(12,2)"
    )
    op.execute(
        "ALTER TABLE facturas ALTER COLUMN imp_iva TYPE NUMERIC(12,2) "
        "USING imp_iva::NUMERIC(12,2)"
    )
    op.execute(
        "ALTER TABLE facturas ALTER COLUMN imp_total TYPE NUMERIC(12,2) "
        "USING imp_total::NUMERIC(12,2)"
    )


def downgrade() -> None:
    # ROUND antes de volver a INTEGER: si para entonces hay filas con centavos
    # reales (post-fix), un cast directo a INTEGER trunca en vez de redondear.
    op.execute(
        "ALTER TABLE facturas ALTER COLUMN imp_neto TYPE INTEGER "
        "USING ROUND(imp_neto)::INTEGER"
    )
    op.execute(
        "ALTER TABLE facturas ALTER COLUMN imp_iva TYPE INTEGER "
        "USING ROUND(imp_iva)::INTEGER"
    )
    op.execute(
        "ALTER TABLE facturas ALTER COLUMN imp_total TYPE INTEGER "
        "USING ROUND(imp_total)::INTEGER"
    )
