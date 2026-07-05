"""Factura de Exportación — WSFEXv1: tabla facturas_exportacion (separada de facturas)

Espeja init_db() (esquema en dos capas, MEMORIA 2026-06-03). Tabla SEPARADA de `facturas` — el
receptor de exportación no tiene doc_tipo/doc_nro/condicion_iva_receptor argentinos (NOT NULL en
`facturas`); forzar los dos modelos en una tabla arriesgaba romper invariantes ya probados. Flujo
nuevo sin `pedido_id` (confirmado con el dueño: venta al exterior, carga manual en el admin).

Revision ID: r1s2t3u4v5w6
Revises: q7r8s9t0u1v2
Create Date: 2026-07-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "r1s2t3u4v5w6"
down_revision: Union[str, Sequence[str], None] = "q7r8s9t0u1v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS facturas_exportacion (
            id                      SERIAL PRIMARY KEY,
            emisor                  TEXT NOT NULL,
            ambiente                TEXT NOT NULL,
            cbte_tipo               INTEGER NOT NULL,
            pto_vta                 INTEGER NOT NULL,
            cbte_nro                INTEGER,
            cae                     TEXT,
            cae_vto                 DATE,
            receptor_razon_social   TEXT NOT NULL,
            receptor_pais_destino   INTEGER NOT NULL,
            receptor_domicilio      TEXT,
            receptor_id_impositivo  TEXT,
            incoterm                TEXT NOT NULL,
            permiso_embarque        TEXT,
            moneda                  TEXT NOT NULL,
            cotizacion              NUMERIC(12,4) NOT NULL,
            imp_total               NUMERIC(12,2) NOT NULL,
            estado                  TEXT NOT NULL DEFAULT 'pendiente',
            nota_credito_de         INTEGER REFERENCES facturas_exportacion(id),
            raw_request             JSONB,
            raw_response            JSONB,
            errores                 JSONB,
            fecha_emision           TIMESTAMPTZ,
            created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by              TEXT
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_facturas_exportacion_estado
        ON facturas_exportacion (estado)
    """)


def downgrade() -> None:
    """No-op: revertir borraría Facturas de Exportación ya emitidas a ciegas."""
    pass
