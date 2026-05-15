"""unificar specs en spec_definitions globales

Refactor del modelo de specs: pasa de "por categoría" a un catálogo
global asignado a categorías + valores por equipo referenciados al
catálogo. Habilita la feature futura de compatibilidad automática.

WIPE STRATEGY: el dueño aprobó borrar la data existente de
categoria_spec_templates y equipo_specs. El back-office los recarga.

Revision ID: e8f4c2a1d7b9
Revises: a3e7f1d2b8c4
Create Date: 2026-05-15
"""
from typing import Sequence, Union

from alembic import op

revision: str = "e8f4c2a1d7b9"
down_revision: Union[str, Sequence[str], None] = "a3e7f1d2b8c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotente: si init_db ya creó las tablas nuevas (porque corre con
    # CREATE TABLE IF NOT EXISTS), la migración respeta y solo dropea las
    # viejas. El orden importa: catalog global → asignaciones → valores.
    #
    # En BDs viejas (con categoria_spec_templates(spec_key, ...)):
    # - DROP CASCADE elimina las viejas con sus datos.
    # - CREATE IF NOT EXISTS crea las nuevas si no existen.

    op.execute("DROP TABLE IF EXISTS equipo_specs CASCADE")
    op.execute("DROP TABLE IF EXISTS categoria_spec_templates CASCADE")

    op.execute("""
        CREATE TABLE IF NOT EXISTS spec_definitions (
            id                  SERIAL PRIMARY KEY,
            spec_key            VARCHAR(64) UNIQUE NOT NULL,
            label               VARCHAR(120) NOT NULL,
            tipo                VARCHAR(16) NOT NULL,
            unidad              VARCHAR(32),
            enum_options        JSONB,
            ayuda               TEXT,
            es_compatibilidad   BOOLEAN NOT NULL DEFAULT FALSE,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_spec_def_compat "
        "ON spec_definitions(es_compatibilidad) WHERE es_compatibilidad"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS categoria_spec_templates (
            id                  SERIAL PRIMARY KEY,
            categoria_id        INTEGER NOT NULL REFERENCES categorias(id) ON DELETE CASCADE,
            spec_def_id         INTEGER NOT NULL REFERENCES spec_definitions(id) ON DELETE RESTRICT,
            prioridad           INTEGER DEFAULT 100,
            destacado           BOOLEAN DEFAULT FALSE,
            obligatorio         BOOLEAN DEFAULT FALSE,
            visible_en_card     BOOLEAN DEFAULT FALSE,
            visible_en_filtros  BOOLEAN DEFAULT FALSE,
            visible_en_nombre   BOOLEAN DEFAULT FALSE,
            ayuda               TEXT,
            UNIQUE (categoria_id, spec_def_id)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cst_categoria "
        "ON categoria_spec_templates(categoria_id, prioridad)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cst_def "
        "ON categoria_spec_templates(spec_def_id)"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS equipo_specs (
            equipo_id    INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            spec_def_id  INTEGER NOT NULL REFERENCES spec_definitions(id) ON DELETE RESTRICT,
            value        TEXT NOT NULL,
            PRIMARY KEY (equipo_id, spec_def_id)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_equipo_specs_def_value "
        "ON equipo_specs(spec_def_id, value)"
    )


def downgrade() -> None:
    # No-op intencional. La estrategia de rollback es restaurar un snapshot
    # de la BD previa al deploy. Reversar el refactor automáticamente
    # requeriría preservar datos pre-wipe que ya no existen.
    raise NotImplementedError(
        "Refactor de specs irreversible vía downgrade. "
        "Rollback path: restaurar snapshot de DB pre-deploy."
    )
