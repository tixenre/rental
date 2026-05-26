"""spec_definitions: aliases JSONB + rename potencia_w → consumo_w en Iluminación

- Agrega columna `aliases JSONB NOT NULL DEFAULT '[]'` en spec_definitions.
  El seeder la puebla en el siguiente boot.
- Renombra spec_key 'potencia_w' → 'consumo_w' (label: 'Consumo eléctrico')
  en Iluminación. Los watts = consumo eléctrico, no potencia óptica (esa = lúmenes).
- Elimina la spec 'power_consumption_w' de Iluminación (era duplicado de
  'potencia_w'). Los equipo_specs de ese spec_def se migran a consumo_w primero.

Revision ID: b3d5e7f9a1c2
Revises: a1b3c5e7f9d2
Create Date: 2026-05-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3d5e7f9a1c2"
down_revision: Union[str, Sequence[str], None] = "a1b3c5e7f9d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Columna aliases (idempotente via IF NOT EXISTS)
    op.execute(
        "ALTER TABLE spec_definitions "
        "ADD COLUMN IF NOT EXISTS aliases JSONB NOT NULL DEFAULT '[]'::jsonb"
    )

    # 2. Rename potencia_w → consumo_w en Iluminación
    bind.execute(sa.text("""
        UPDATE spec_definitions
        SET spec_key = 'consumo_w',
            label    = 'Consumo eléctrico',
            updated_at = NOW()
        WHERE spec_key = 'potencia_w'
          AND categoria_raiz_id = (
              SELECT id FROM categorias WHERE nombre = 'Iluminación'
          )
    """))

    # 3. Migrar equipo_specs de power_consumption_w → consumo_w (en Iluminación).
    # Solo si el equipo no tiene ya un valor de consumo_w.
    bind.execute(sa.text("""
        INSERT INTO equipo_specs (equipo_id, spec_def_id, value)
        SELECT es.equipo_id, consumo.id, es.value
        FROM equipo_specs es
        JOIN spec_definitions old_sd ON old_sd.id = es.spec_def_id
        JOIN categorias c ON c.id = old_sd.categoria_raiz_id
        JOIN spec_definitions consumo
             ON consumo.spec_key = 'consumo_w'
            AND consumo.categoria_raiz_id = c.id
        WHERE old_sd.spec_key = 'power_consumption_w'
          AND c.nombre = 'Iluminación'
          AND NOT EXISTS (
              SELECT 1 FROM equipo_specs es2
              WHERE es2.equipo_id = es.equipo_id
                AND es2.spec_def_id = consumo.id
          )
        ON CONFLICT (equipo_id, spec_def_id) DO NOTHING
    """))

    # 4. Eliminar power_consumption_w en Iluminación.
    # CASCADE elimina automáticamente equipo_specs y categoria_spec_templates.
    bind.execute(sa.text("""
        DELETE FROM spec_definitions
        WHERE spec_key = 'power_consumption_w'
          AND categoria_raiz_id = (
              SELECT id FROM categorias WHERE nombre = 'Iluminación'
          )
    """))


def downgrade() -> None:
    # Solo revertimos la columna aliases — el rename no se puede deshacer
    # sin riesgo de pérdida de datos (se necesitaría recrear la spec y los valores).
    op.execute(
        "ALTER TABLE spec_definitions DROP COLUMN IF EXISTS aliases"
    )
