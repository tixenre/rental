"""Backfill columnas legacy de equipo_fichas → equipo_specs.

Las columnas `montura`, `formato`, `resolucion`, `peso`, `dimensiones`,
`alimentacion` de equipo_fichas tenían valores que el catálogo público
todavía consumía como fallback. Fase F las migra a equipo_specs (fuente
canónica única) para poder dropearlas sin perder data.

Conversiones:
- `montura` (string) → spec_key `lens_mount` (value tal cual, el frontend
  matchea contra LENS_MOUNT_ENUM)
- `formato` (string) → spec_key `formato` (tal cual)
- `resolucion` (string) → spec_key `resolucion_max` (tal cual)
- `peso` (string "640 g") → spec_key `peso_g` (number, parseamos el primer
  número del string; "640 g" → "640")
- `dimensiones` (string) → spec_key `dimensions_mm` (tal cual)
- `alimentacion` (string) → spec_key `alimentacion` (multi_enum, JSON array;
  si el legacy es "V-mount, AC" → '["V-mount", "AC"]')

Para cada equipo, se busca el spec_def en la categoría raíz aplicable. Si
el equipo está en varias raíces (ej. Cámaras + Iluminación), se prefiere
la primera por orden de inserción (`equipo_categorias.orden ASC`).

Idempotente: INSERT ON CONFLICT (equipo_id, spec_def_id) DO NOTHING.
Si el equipo ya tiene la spec en equipo_specs, no se pisa.

NO se borran las columnas legacy en esta migration — eso lo hace la
siguiente migration (`drop_legacy_ficha_columns`) después de validar que
el backfill quedó OK en producción.

Revision ID: e8f4d9c2b1a3
Revises: d7e9b3c5a8f2
Create Date: 2026-05-25
"""
from __future__ import annotations

import json
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e8f4d9c2b1a3"
down_revision: Union[str, Sequence[str], None] = "d7e9b3c5a8f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (columna_legacy, spec_key, conversor opcional)
_MAPPINGS = [
    ("montura",      "lens_mount",     None),
    ("formato",      "formato",        None),
    ("resolucion",   "resolucion_max", None),
    ("peso",         "peso_g",         "extract_number"),
    ("dimensiones",  "dimensions_mm",  None),
    ("alimentacion", "alimentacion",   "csv_to_json"),
]


def _convert_value(raw: str, conversor: str | None) -> str | None:
    """Aplica el conversor al valor legacy. Devuelve None si no se puede
    parsear (skip ese equipo para esa spec)."""
    if raw is None:
        return None
    raw = str(raw).strip()
    if not raw:
        return None

    if conversor == "extract_number":
        # "640 g" / "1.5 kg" / "640" → "640" (number como string)
        # Por simpleza extraemos el primer número. Las unidades quedan
        # implícitas en el spec_def (unidad='g').
        m = re.search(r"\d+(?:[.,]\d+)?", raw)
        if not m:
            return None
        return m.group(0).replace(",", ".")

    if conversor == "csv_to_json":
        # "V-mount, AC" → '["V-mount", "AC"]'
        # "V-mount" → '["V-mount"]'
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if not parts:
            return None
        return json.dumps(parts, ensure_ascii=False)

    # Sin conversor: tal cual.
    return raw


def upgrade() -> None:
    conn = op.get_bind()
    total_inserted = 0

    for legacy_col, spec_key, conversor in _MAPPINGS:
        # 1. Obtener todos los equipos con valor en esta columna legacy +
        #    su categoría raíz aplicable. La categoría raíz se resuelve
        #    via WITH RECURSIVE subiendo desde la cat con menor `orden`
        #    del equipo (la "primera" asignada).
        rows = conn.execute(sa.text(f"""
            WITH RECURSIVE
              eq_first_cat AS (
                SELECT DISTINCT ON (ec.equipo_id)
                  ec.equipo_id, ec.categoria_id
                FROM equipo_categorias ec
                ORDER BY ec.equipo_id, ec.orden ASC, ec.categoria_id ASC
              ),
              up AS (
                SELECT c.id AS cat_id, c.parent_id, efc.equipo_id
                FROM eq_first_cat efc
                JOIN categorias c ON c.id = efc.categoria_id
                UNION
                SELECT c.id, c.parent_id, up.equipo_id
                FROM categorias c
                JOIN up ON up.parent_id = c.id
              )
            SELECT
              ef.equipo_id,
              ef.{legacy_col} AS legacy_value,
              (SELECT cat_id FROM up u
                 WHERE u.equipo_id = ef.equipo_id AND u.parent_id IS NULL
                 LIMIT 1) AS raiz_id
            FROM equipo_fichas ef
            WHERE ef.{legacy_col} IS NOT NULL
              AND ef.{legacy_col} != ''
        """)).fetchall()

        col_inserted = 0
        for r in rows:
            equipo_id = r.equipo_id
            raw = r.legacy_value
            raiz_id = r.raiz_id
            if not raiz_id:
                continue  # equipo sin categorías → no podemos mapear

            value = _convert_value(raw, conversor)
            if value is None:
                continue

            # 2. Buscar el spec_def en la raíz del equipo.
            sd = conn.execute(sa.text("""
                SELECT id FROM spec_definitions
                WHERE categoria_raiz_id = :raiz AND spec_key = :key
                LIMIT 1
            """), {"raiz": raiz_id, "key": spec_key}).fetchone()
            if not sd:
                continue  # la cat no declara este spec_key

            # 3. Insertar a equipo_specs idempotente.
            result = conn.execute(sa.text("""
                INSERT INTO equipo_specs (equipo_id, spec_def_id, value)
                VALUES (:eid, :sd, :val)
                ON CONFLICT (equipo_id, spec_def_id) DO NOTHING
                RETURNING id
            """), {"eid": equipo_id, "sd": sd.id, "val": value})
            if result.fetchone():
                col_inserted += 1

        total_inserted += col_inserted
        print(f"  backfill {legacy_col} → {spec_key}: {col_inserted} inserts")

    print(f"  TOTAL: {total_inserted} entries insertadas en equipo_specs")


def downgrade() -> None:
    # No revertible: las filas insertadas se mezclaron con las existentes.
    # Si hace falta rollback, ejecutar la migration anterior y restaurar
    # backup de equipo_specs.
    pass
