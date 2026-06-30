"""Tabla `emisores_arca` — credenciales dinámicas de facturación ARCA.

Reemplaza el modelo ENV-por-emisor (AFIP_PABLO_CERT/KEY…) por una tabla
administrable desde el back-office. Cert+clave cifrados con ARCA_MASTER_KEY.

Espeja init_db() (esquema en dos capas, MEMORIA 2026-06-03). Todo `IF NOT
EXISTS` para idempotencia aunque el bootstrap ya haya creado la tabla.

Revision ID: b1c2d3e4f5a6
Revises: d3e4f5a6b7c8
Create Date: 2026-06-30
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS emisores_arca (
            id              SERIAL PRIMARY KEY,
            nombre          TEXT NOT NULL UNIQUE,
            cuit            TEXT NOT NULL,
            pto_vta         INTEGER NOT NULL,
            condicion_iva   TEXT NOT NULL,
            cert_enc        BYTEA,
            key_enc         BYTEA,
            activo          BOOLEAN NOT NULL DEFAULT true,
            notas           TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS emisores_arca")
