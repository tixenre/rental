"""búsqueda fuzzy — pg_trgm + unaccent + f_unaccent + índices GIN + search_clicks

Motor único de búsqueda (backend/busqueda): matching sin tildes/guiones, con
tolerancia a typos y ranking por relevancia. Necesita las extensiones `pg_trgm`
y `unaccent`, la función inmutable `f_unaccent` (envuelve `unaccent()`, que es
STABLE y no se puede indexar) y los índices GIN trigram sobre las columnas
buscables de `equipos` y `clientes`.

Todo está espejado en `database.init_db()` (esquema en dos capas, decisión
2026-06-03) → existe aunque esta migración no llegue a correr. Idempotente
(IF NOT EXISTS / OR REPLACE) para convivir con el bootstrap.

`search_clicks` registra qué resultado abre el usuario tras una búsqueda
(click-through): la señal para, a futuro, aprender qué encontró la gente.

Revision ID: s3t4u5v6w7x8
Revises: d8b2f4a6c0e1
Create Date: 2026-06-06
"""

from typing import Union

from alembic import op

revision: str = "s3t4u5v6w7x8"
down_revision: Union[str, None] = "d8b2f4a6c0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extensiones + helper inmutable (la forma canónica que usan queries e índices).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute(
        "CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text AS "
        "$$ SELECT public.unaccent('public.unaccent', $1) $$ "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT"
    )

    # Índices GIN trigram — la expresión es la canónica de busqueda.campo_sql:
    # btrim(regexp_replace(f_unaccent(lower(coalesce(col,''))), '[^a-z0-9]+', ' ', 'g')).
    op.execute("CREATE INDEX IF NOT EXISTS idx_equipos_nombre_trgm ON equipos USING gin (btrim(regexp_replace(f_unaccent(lower(coalesce(nombre, ''))), '[^a-z0-9]+', ' ', 'g')) gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_equipos_modelo_trgm ON equipos USING gin (btrim(regexp_replace(f_unaccent(lower(coalesce(modelo, ''))), '[^a-z0-9]+', ' ', 'g')) gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_equipos_serie_trgm ON equipos USING gin (btrim(regexp_replace(f_unaccent(lower(coalesce(serie, ''))), '[^a-z0-9]+', ' ', 'g')) gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_clientes_nombre_apellido_trgm ON clientes USING gin (btrim(regexp_replace(f_unaccent(lower(coalesce((nombre || ' ' || apellido), ''))), '[^a-z0-9]+', ' ', 'g')) gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_clientes_email_trgm ON clientes USING gin (btrim(regexp_replace(f_unaccent(lower(coalesce(email, ''))), '[^a-z0-9]+', ' ', 'g')) gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_clientes_cuit_trgm ON clientes USING gin (btrim(regexp_replace(f_unaccent(lower(coalesce(cuit, ''))), '[^a-z0-9]+', ' ', 'g')) gin_trgm_ops)")

    # Click-through del catálogo público.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS search_clicks (
            id           SERIAL PRIMARY KEY,
            query_id     INTEGER NOT NULL REFERENCES search_queries(id) ON DELETE CASCADE,
            equipo_id    INTEGER REFERENCES equipos(id) ON DELETE SET NULL,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_search_clicks_query ON search_clicks(query_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_search_clicks_equipo ON search_clicks(equipo_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS search_clicks")
    op.execute("DROP INDEX IF EXISTS idx_clientes_cuit_trgm")
    op.execute("DROP INDEX IF EXISTS idx_clientes_email_trgm")
    op.execute("DROP INDEX IF EXISTS idx_clientes_nombre_apellido_trgm")
    op.execute("DROP INDEX IF EXISTS idx_equipos_serie_trgm")
    op.execute("DROP INDEX IF EXISTS idx_equipos_modelo_trgm")
    op.execute("DROP INDEX IF EXISTS idx_equipos_nombre_trgm")
    # f_unaccent y las extensiones se dejan: otros objetos pueden depender de ellas.
