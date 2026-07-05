"""perfiles fiscales múltiples por cliente + productoras (#1240)

Revision ID: q7r8s9t0u1v2
Revises: q4r5s6t7u8v9
Create Date: 2026-07-05
"""
from typing import Sequence, Union
from alembic import op

revision: str = "q7r8s9t0u1v2"
down_revision: Union[str, Sequence[str], None] = "q4r5s6t7u8v9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS cliente_perfiles_fiscales (
            id                SERIAL PRIMARY KEY,
            cliente_id        INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
            cuit              TEXT NOT NULL,
            perfil_impuestos  TEXT NOT NULL,
            razon_social      TEXT,
            domicilio_fiscal  TEXT,
            email_facturacion TEXT,
            etiqueta          TEXT,
            verificado_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            es_default        BOOLEAN NOT NULL DEFAULT FALSE,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cliente_perfiles_fiscales_cliente_id "
        "ON cliente_perfiles_fiscales(cliente_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_cliente_perfiles_fiscales_default "
        "ON cliente_perfiles_fiscales(cliente_id) WHERE es_default"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_cliente_perfiles_fiscales_cuit "
        "ON cliente_perfiles_fiscales(cliente_id, cuit)"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS productoras (
            id                SERIAL PRIMARY KEY,
            cuit              TEXT NOT NULL UNIQUE,
            perfil_impuestos  TEXT NOT NULL,
            razon_social      TEXT,
            domicilio_fiscal  TEXT,
            email_facturacion TEXT,
            notas             TEXT,
            verificado_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS productora_miembros (
            productora_id  INTEGER NOT NULL REFERENCES productoras(id) ON DELETE CASCADE,
            cliente_id     INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (productora_id, cliente_id)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_productora_miembros_cliente_id "
        "ON productora_miembros(cliente_id)"
    )

    op.execute(
        "ALTER TABLE alquileres ADD COLUMN IF NOT EXISTS perfil_fiscal_id "
        "INTEGER REFERENCES cliente_perfiles_fiscales(id)"
    )
    op.execute(
        "ALTER TABLE alquileres ADD COLUMN IF NOT EXISTS productora_id "
        "INTEGER REFERENCES productoras(id)"
    )
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'chk_alquileres_facturacion_target'
            ) THEN
                ALTER TABLE alquileres ADD CONSTRAINT chk_alquileres_facturacion_target
                    CHECK (perfil_fiscal_id IS NULL OR productora_id IS NULL);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """No-op: revertir borraría perfiles fiscales/productoras ya cargados a ciegas."""
    pass
