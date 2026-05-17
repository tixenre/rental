"""hotfix: restaurar unidad_id + FKs perdidas por DROP CASCADE

La migración previa `c1f9e5d3b7a8` hace `DROP TABLE spec_definitions CASCADE`
y recrea la tabla. El CREATE TABLE nuevo omite la columna `unidad_id` que
había agregado `e2f4a6b8c1d5_spec_def_unidad_id_fk`, y el CASCADE dropea
silenciosamente las FKs de `spec_observacion.spec_def_id` y
`spec_familia_jerarquia.spec_def_id`.

Síntoma en prod: `GET /admin/specs/definitions` 500 con
`column "sd.unidad_id" does not exist`. Además, las filas viejas en
spec_observacion y spec_familia_jerarquia quedaron con spec_def_id apuntando
a IDs huérfanos del schema anterior.

Este hotfix:
  1. Re-agrega `spec_definitions.unidad_id` (FK a unidades) + índice
  2. Nullifica/limpia spec_def_id huérfanos en spec_observacion y
     spec_familia_jerarquia
  3. Re-crea las FKs ON DELETE SET NULL / CASCADE

Idempotente. Si el restart de Railway hizo correr init_db() antes de alembic,
la columna ya existe — los `IF NOT EXISTS` lo hacen no-op.

Revision ID: d2a4f6b8e1c3
Revises: c1f9e5d3b7a8
Create Date: 2026-05-17
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d2a4f6b8e1c3"
down_revision: Union[str, Sequence[str], None] = "c1f9e5d3b7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Restaurar spec_definitions.unidad_id (FK a unidades).
    op.execute(
        "ALTER TABLE spec_definitions "
        "ADD COLUMN IF NOT EXISTS unidad_id INTEGER "
        "REFERENCES unidades(id) ON DELETE SET NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_spec_def_unidad_id "
        "ON spec_definitions(unidad_id) WHERE unidad_id IS NOT NULL"
    )

    # 2) Limpiar referencias huérfanas a IDs del schema anterior antes de
    # recrear las FKs (sino el ADD CONSTRAINT falla).
    op.execute("""
        UPDATE spec_observacion
        SET spec_def_id = NULL, matched_template = FALSE
        WHERE spec_def_id IS NOT NULL
          AND spec_def_id NOT IN (SELECT id FROM spec_definitions)
    """)
    op.execute("""
        UPDATE spec_familia_jerarquia
        SET spec_def_id = NULL
        WHERE spec_def_id IS NOT NULL
          AND spec_def_id NOT IN (SELECT id FROM spec_definitions)
    """)

    # 3) Re-crear FKs. DROP IF EXISTS por idempotencia (en algunos boots la FK
    # puede no haberse caído todavía, o este hotfix corrió antes parcialmente).
    op.execute(
        "ALTER TABLE spec_observacion "
        "DROP CONSTRAINT IF EXISTS spec_observacion_spec_def_id_fkey"
    )
    op.execute(
        "ALTER TABLE spec_observacion "
        "ADD CONSTRAINT spec_observacion_spec_def_id_fkey "
        "FOREIGN KEY (spec_def_id) REFERENCES spec_definitions(id) "
        "ON DELETE SET NULL"
    )

    op.execute(
        "ALTER TABLE spec_familia_jerarquia "
        "DROP CONSTRAINT IF EXISTS spec_familia_jerarquia_spec_def_id_fkey"
    )
    op.execute(
        "ALTER TABLE spec_familia_jerarquia "
        "ADD CONSTRAINT spec_familia_jerarquia_spec_def_id_fkey "
        "FOREIGN KEY (spec_def_id) REFERENCES spec_definitions(id) "
        "ON DELETE CASCADE"
    )


def downgrade() -> None:
    # No hay nada que revertir — restaura estado pre-c1f9e5d3b7a8 esperado.
    raise NotImplementedError(
        "Hotfix forward-only. Restaura columna y FKs que el wipe de "
        "c1f9e5d3b7a8 perdió. No tiene sentido bajarlo."
    )
