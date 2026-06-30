"""Motor de facturación electrónica ARCA (#1139): tablas facturas + afip_ta.

Espeja init_db() (esquema en dos capas, MEMORIA 2026-06-03). Todo `IF NOT EXISTS`
para que sea idempotente aunque el bootstrap ya las haya creado.

Revision ID: a2b3c4d5e6f7
Revises: f6a7b8c9d0e1
Create Date: 2026-06-30
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS facturas (
            id                      SERIAL PRIMARY KEY,
            pedido_id               INTEGER NOT NULL REFERENCES alquileres(id) ON DELETE CASCADE,
            emisor                  TEXT NOT NULL,
            ambiente                TEXT NOT NULL,
            cbte_tipo               INTEGER NOT NULL,
            pto_vta                 INTEGER NOT NULL,
            cbte_nro                INTEGER,
            cae                     TEXT,
            cae_vto                 DATE,
            doc_tipo                INTEGER NOT NULL,
            doc_nro                 TEXT NOT NULL,
            condicion_iva_receptor  INTEGER NOT NULL,
            concepto                INTEGER NOT NULL,
            imp_neto                INTEGER NOT NULL,
            imp_iva                 INTEGER NOT NULL DEFAULT 0,
            imp_total               INTEGER NOT NULL,
            moneda                  TEXT NOT NULL DEFAULT 'PES',
            cliente_cuit            TEXT,
            razon_social            TEXT,
            qr_payload              TEXT,
            pdf_key                 TEXT,
            estado                  TEXT NOT NULL DEFAULT 'pendiente',
            nota_credito_de         INTEGER REFERENCES facturas(id),
            raw_request             JSONB,
            raw_response            JSONB,
            errores                 JSONB,
            fecha_emision           TIMESTAMPTZ,
            created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by              TEXT
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_factura_vigente_por_pedido
        ON facturas (pedido_id) WHERE estado IN ('pendiente','emitida')
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_facturas_pedido ON facturas (pedido_id)
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS afip_ta (
            ambiente   TEXT NOT NULL,
            emisor     TEXT NOT NULL,
            token      TEXT NOT NULL,
            sign       TEXT NOT NULL,
            expira_at  TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (ambiente, emisor)
        )
    """)
    # Seeds de claves no-secretas en app_settings
    for key in ("afip_pablo_cuit", "afip_pablo_ptovta",
                "afip_santini_cuit", "afip_santini_ptovta"):
        op.execute(
            f"INSERT INTO app_settings (key, value, updated_by)"
            f" VALUES ('{key}', '', 'migration-seed')"
            f" ON CONFLICT (key) DO NOTHING"
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS afip_ta")
    op.execute("DROP TABLE IF EXISTS facturas")
    for key in ("afip_pablo_cuit", "afip_pablo_ptovta",
                "afip_santini_cuit", "afip_santini_ptovta"):
        op.execute(f"DELETE FROM app_settings WHERE key = '{key}'")
