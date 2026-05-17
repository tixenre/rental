"""spec_observacion — tabla de relevamiento de specs reales

Crea la base del "observatorio de specs": una tabla denormalizada que
guarda cada (equipo, label, value) observado en el cache de scrapes
B&H/Adorama (`equipo_fichas.raw_json`).

Propósito:
  - Detectar qué labels aparecen en los datos reales del scraper que
    NO matchean el template canónico (gaps en el seed).
  - Ver qué valores frecuenta cada label por categoría (¿conviene
    enum vs string libre?).
  - Calibrar las familias jerárquicas (HDMI, SDI, sensor formats) con
    cómo realmente B&H escribe las versiones.
  - Detectar specs duplicadas/divergentes para el dedup tool futuro.

Idempotente: si se borra y reinserta con `recompute`, no hay datos
huérfanos. Cada equipo tiene UNA fila por `label_normalizado`.

Revision ID: d8a1e5b2c4f7
Revises: b9d4e7c3a1f5
Create Date: 2026-05-15
"""
from typing import Sequence, Union

revision: str = "d8a1e5b2c4f7"
down_revision: Union[str, Sequence[str], None] = "b9d4e7c3a1f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic import op
    op.execute("""
        CREATE TABLE IF NOT EXISTS spec_observacion (
            id                  SERIAL PRIMARY KEY,
            equipo_id           INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            categoria_raiz      VARCHAR(64),
            label_observado     VARCHAR(255) NOT NULL,
            label_normalizado   VARCHAR(255) NOT NULL,
            value_observado     TEXT NOT NULL,
            spec_def_id         INTEGER REFERENCES spec_definitions(id) ON DELETE SET NULL,
            matched_template    BOOLEAN NOT NULL DEFAULT FALSE,
            source              VARCHAR(64),
            observed_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (equipo_id, label_normalizado)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_obs_categoria_label "
        "ON spec_observacion (categoria_raiz, label_normalizado)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_obs_matched "
        "ON spec_observacion (matched_template) WHERE matched_template = FALSE"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_obs_spec_def "
        "ON spec_observacion (spec_def_id) WHERE spec_def_id IS NOT NULL"
    )


def downgrade() -> None:
    from alembic import op
    op.execute("DROP INDEX IF EXISTS idx_obs_spec_def")
    op.execute("DROP INDEX IF EXISTS idx_obs_matched")
    op.execute("DROP INDEX IF EXISTS idx_obs_categoria_label")
    op.execute("DROP TABLE IF EXISTS spec_observacion")
