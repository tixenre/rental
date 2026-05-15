"""spec_definitions.unidad_id — FK al catálogo unidades

Hasta ahora `spec_definitions.unidad` era VARCHAR(32) libre. El catálogo
`unidades` existía como entidad propia pero no había vínculo formal —
cada spec_def repetía el string "lm", "K", "fps", etc. de forma aislada.

Esta migración:
  1. Agrega `unidad_id INTEGER REFERENCES unidades(id) ON DELETE SET NULL`.
  2. Backfill: para cada spec_def con `unidad` no vacía, busca o crea
     `unidades(simbolo)` (dimension=NULL para curar después) y setea
     `unidad_id` consistente.
  3. La columna `unidad` (VARCHAR) se mantiene como cache denormalizado
     para evitar JOINs en el hot path (render del placeholder, listado
     del catálogo). El sync `unidad ↔ unidad_id` lo cuida el endpoint
     PATCH/POST de `/admin/spec-definitions`.

Beneficios:
  - Integridad referencial (no borrar una unidad si está en uso).
  - Query por dimensión: "qué specs usan unidades de luminosidad".
  - Base para conversiones imperial/métrico futuras.
  - Cambio del símbolo en `unidades` propaga a todas las specs vía
    sync explícito en CRUD.

Revision ID: e2f4a6b8c1d5
Revises: d8a1e5b2c4f7
Create Date: 2026-05-15
"""
from typing import Sequence, Union

revision: str = "e2f4a6b8c1d5"
down_revision: Union[str, Sequence[str], None] = "d8a1e5b2c4f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    import sqlalchemy as sa
    from alembic import op

    # 1) Columna FK (idempotente).
    op.execute(
        "ALTER TABLE spec_definitions "
        "ADD COLUMN IF NOT EXISTS unidad_id INTEGER "
        "REFERENCES unidades(id) ON DELETE SET NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_spec_def_unidad_id "
        "ON spec_definitions(unidad_id) WHERE unidad_id IS NOT NULL"
    )

    bind = op.get_bind()

    # 2) Backfill: para cada spec_def con unidad no vacía y unidad_id NULL,
    # asegurar la entry en `unidades` y vincular `unidad_id`.
    specs_con_unidad = bind.execute(
        sa.text("""
            SELECT id, unidad
            FROM spec_definitions
            WHERE unidad IS NOT NULL AND TRIM(unidad) <> '' AND unidad_id IS NULL
        """)
    ).fetchall()

    for row in specs_con_unidad:
        spec_id = row[0]
        simbolo = (row[1] or "").strip()
        if not simbolo:
            continue
        # Insertar unidad si no existe (idempotent). nombre = simbolo como
        # placeholder; el admin la edita después con su nombre canónico.
        bind.execute(
            sa.text("""
                INSERT INTO unidades (simbolo, nombre, dimension)
                VALUES (:simbolo, :nombre, NULL)
                ON CONFLICT (simbolo) DO NOTHING
            """),
            {"simbolo": simbolo, "nombre": simbolo},
        )
        unidad_row = bind.execute(
            sa.text("SELECT id FROM unidades WHERE simbolo = :simbolo"),
            {"simbolo": simbolo},
        ).fetchone()
        if unidad_row is None:
            continue
        bind.execute(
            sa.text("UPDATE spec_definitions SET unidad_id = :uid WHERE id = :sid"),
            {"uid": unidad_row[0], "sid": spec_id},
        )


def downgrade() -> None:
    from alembic import op
    op.execute("DROP INDEX IF EXISTS idx_spec_def_unidad_id")
    op.execute("ALTER TABLE spec_definitions DROP COLUMN IF EXISTS unidad_id")
