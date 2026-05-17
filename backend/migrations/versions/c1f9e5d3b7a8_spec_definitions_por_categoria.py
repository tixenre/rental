"""spec_definitions por categoría (composite key + registry-driven)

Refactor: pasa `spec_definitions` de UNIQUE(spec_key) global a
UNIQUE(categoria_raiz_id, spec_key). Cada categoría raíz es dueña de su
propia fila de cada spec, lo que permite que dos cats tengan
"camera_subtipo"/"filtro_subtipo" sin colisión, y elimina los UNION
silenciosos de enum_options entre categorías heterogéneas.

WIPE STRATEGY: el dueño aprobó borrar la data de spec_definitions,
categoria_spec_templates y equipo_specs. Los seeds (que ahora consumen
`backend/specs/registry.py` como single source of truth) la recargan en
una sola pasada al re-correr.

Rollback no soportado — el esquema viejo permitía colisión por diseño.
Si hay que volver, restaurar desde backup.

Revision ID: c1f9e5d3b7a8
Revises: a5c2e4f8b1d6
Create Date: 2026-05-17
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c1f9e5d3b7a8"
down_revision: Union[str, Sequence[str], None] = "a5c2e4f8b1d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Orden: drop hijos primero (FK), después la tabla padre.
    op.execute("DROP TABLE IF EXISTS equipo_specs CASCADE")
    op.execute("DROP TABLE IF EXISTS categoria_spec_templates CASCADE")
    op.execute("DROP TABLE IF EXISTS spec_definitions CASCADE")

    # spec_definitions con composite key (categoria_raiz_id, spec_key).
    # categoria_raiz_id es NOT NULL: toda spec pertenece a una cat raíz.
    # Shared keys (lens_mount, formato, diametro_filtro, peso_g) tienen una
    # fila por cat que las usa — el motor de compat matchea por string
    # equality del spec_key + value, no por spec_def_id compartido.
    op.execute("""
        CREATE TABLE spec_definitions (
            id                  SERIAL PRIMARY KEY,
            -- nullable: el admin endpoint puede crear specs free-floating;
            -- el registry-driven flow siempre setea categoria_raiz_id
            categoria_raiz_id   INTEGER REFERENCES categorias(id) ON DELETE CASCADE,
            spec_key            VARCHAR(64) NOT NULL,
            label               VARCHAR(120) NOT NULL,
            tipo                VARCHAR(16) NOT NULL,
            unidad              VARCHAR(32),
            enum_options        JSONB,
            ayuda               TEXT,
            es_compatibilidad   BOOLEAN NOT NULL DEFAULT FALSE,
            compatibilidad_modo VARCHAR(16) NOT NULL DEFAULT 'exacta',
            rol_compatibilidad  VARCHAR(16),
            validado            BOOLEAN NOT NULL DEFAULT FALSE,
            tabla_columnas      JSONB,
            output_config       JSONB,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (categoria_raiz_id, spec_key)
        )
    """)
    op.execute(
        "CREATE INDEX idx_spec_def_categoria "
        "ON spec_definitions(categoria_raiz_id, spec_key)"
    )
    op.execute(
        "CREATE INDEX idx_spec_def_compat "
        "ON spec_definitions(spec_key) WHERE es_compatibilidad"
    )
    # Specs free-floating (admin endpoint sin categoría): el composite
    # UNIQUE (categoria_raiz_id, spec_key) trata NULLs como distintos, por lo
    # que sin esto se podrían crear duplicados. Partial index garantiza
    # unicidad global del spec_key dentro de las free-floating.
    op.execute(
        "CREATE UNIQUE INDEX idx_spec_def_global_unique "
        "ON spec_definitions(spec_key) WHERE categoria_raiz_id IS NULL"
    )

    # categoria_spec_templates: asigna una spec_def a una sub-categoría
    # (heredada de la raíz). Permite override de flags por sub-cat
    # (ej. Video/Montura E muestra distintos en_card que Cámaras raíz).
    op.execute("""
        CREATE TABLE categoria_spec_templates (
            id                  SERIAL PRIMARY KEY,
            categoria_id        INTEGER NOT NULL REFERENCES categorias(id) ON DELETE CASCADE,
            spec_def_id         INTEGER NOT NULL REFERENCES spec_definitions(id) ON DELETE CASCADE,
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
        "CREATE INDEX idx_cst_categoria "
        "ON categoria_spec_templates(categoria_id, prioridad)"
    )
    op.execute(
        "CREATE INDEX idx_cst_def "
        "ON categoria_spec_templates(spec_def_id)"
    )

    # equipo_specs: valores concretos por equipo. Misma forma que antes.
    op.execute("""
        CREATE TABLE equipo_specs (
            equipo_id   INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            spec_def_id INTEGER NOT NULL REFERENCES spec_definitions(id) ON DELETE CASCADE,
            value       TEXT NOT NULL,
            PRIMARY KEY (equipo_id, spec_def_id)
        )
    """)
    op.execute(
        "CREATE INDEX idx_equipo_specs_def_value "
        "ON equipo_specs(spec_def_id, value)"
    )
    # Nuevo índice para queries de compat: "qué equipos tienen value X
    # para esta spec_key" requiere JOIN con spec_definitions. Indexamos
    # equipo_id para acelerar JOINs equipos × specs en filter UIs.
    op.execute(
        "CREATE INDEX idx_equipo_specs_equipo "
        "ON equipo_specs(equipo_id)"
    )


def downgrade() -> None:
    # No reversible — el esquema viejo permitía colisión por diseño.
    raise NotImplementedError(
        "Migración forward-only. Restaurar desde backup si hace falta volver."
    )
