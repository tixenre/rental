"""normalizar_lumens: consolidar `lumens` legacy en `lumens_at_5600k`

El registry tenía 3 specs para output de luz en Iluminación:
- `lumens` (genérico, ambiguo)
- `lumens_at_5600k` (daylight, estándar cine/video)
- `lumens_at_3200k` (tungsten)

Como `lumens_at_5600k` es el estándar real, consolidamos: los valores
ya cargados como `lumens` se migran a `lumens_at_5600k`, y luego se
elimina el spec genérico. Los parsers (migracion_specs.py,
equipo_html_extractor.py) ya apuntan a `lumens_at_5600k`.

También marcamos `lumens_at_5600k` como `favorito=true` para que el
flag persistente refleje el registry actualizado (el seeder no
sobreescribe en ON CONFLICT, pero acá fuerzo el sync porque el cambio
es semántico, no preferencia del admin).

Revision ID: a8c5d7e2f9b3
Revises: f2a8c9e1b3d4
Create Date: 2026-05-20
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a8c5d7e2f9b3"
down_revision: Union[str, Sequence[str], None] = "f2a8c9e1b3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Para cada equipo con value cargado en `lumens` pero NO en
    #    `lumens_at_5600k`, copiar el value.
    op.execute("""
        INSERT INTO equipo_specs (equipo_id, spec_def_id, value)
        SELECT
            es_old.equipo_id,
            sd_new.id,
            es_old.value
        FROM equipo_specs es_old
        JOIN spec_definitions sd_old
          ON sd_old.id = es_old.spec_def_id
        JOIN categorias c
          ON c.id = sd_old.categoria_raiz_id
        JOIN spec_definitions sd_new
          ON sd_new.categoria_raiz_id = c.id
         AND sd_new.spec_key = 'lumens_at_5600k'
        WHERE sd_old.spec_key = 'lumens'
          AND c.nombre = 'Iluminación'
          AND NOT EXISTS (
              SELECT 1 FROM equipo_specs es_existing
              WHERE es_existing.equipo_id = es_old.equipo_id
                AND es_existing.spec_def_id = sd_new.id
          )
    """)

    # 2) Borrar valores cargados de la spec vieja.
    op.execute("""
        DELETE FROM equipo_specs
        WHERE spec_def_id IN (
            SELECT sd.id
            FROM spec_definitions sd
            JOIN categorias c ON c.id = sd.categoria_raiz_id
            WHERE sd.spec_key = 'lumens'
              AND c.nombre = 'Iluminación'
        )
    """)

    # 3) Borrar la spec_definition vieja (`lumens` en Iluminación).
    op.execute("""
        DELETE FROM spec_definitions
        WHERE spec_key = 'lumens'
          AND categoria_raiz_id IN (
              SELECT id FROM categorias WHERE nombre = 'Iluminación'
          )
    """)

    # 4) Forzar flags actualizados en lumens_at_5600k: favorito=true.
    op.execute("""
        UPDATE spec_definitions
           SET favorito = TRUE,
               updated_at = CURRENT_TIMESTAMP
         WHERE spec_key = 'lumens_at_5600k'
           AND categoria_raiz_id IN (
               SELECT id FROM categorias WHERE nombre = 'Iluminación'
           )
    """)


def downgrade() -> None:
    # No es razonable revertir: los valores fueron mergeados y no podemos
    # saber cuáles eran originalmente genéricos vs ya 5600K.
    # Re-crear la spec vacía con la metadata original.
    op.execute("""
        INSERT INTO spec_definitions
            (categoria_raiz_id, spec_key, label, tipo, unidad,
             es_compatibilidad, compatibilidad_modo, validado,
             favorito, en_nombre, en_filtros, prioridad)
        SELECT c.id, 'lumens', 'Lúmenes', 'number', 'lm',
               FALSE, 'exacta', FALSE, FALSE, FALSE, TRUE, 58
        FROM categorias c
        WHERE c.nombre = 'Iluminación'
        ON CONFLICT (categoria_raiz_id, spec_key) DO NOTHING
    """)
