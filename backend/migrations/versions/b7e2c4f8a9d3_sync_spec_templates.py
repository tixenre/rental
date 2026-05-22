"""sync_spec_templates: rellenar asignaciones faltantes para todos los specs

Para cada spec_definition con categoria_raiz_id (es decir, las que viven
en una raíz del registry), asegurar que exista la asignación
correspondiente en categoria_spec_templates contra esa raíz.

El seeder normalmente lo hace al boot, pero si en algún momento corrió
parcialmente (ej. los specs nuevos del registry expandido se crearon
pero no se asignaron al template), los equipos solo ven los specs viejos.

Idempotente — ON CONFLICT DO NOTHING. Si ya hay asignación, no la toca.
Si falta, la crea con los flags del registry (a través de la spec_def).

Revision ID: b7e2c4f8a9d3
Revises: a8c5d7e2f9b3
Create Date: 2026-05-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b7e2c4f8a9d3"
down_revision: Union[str, Sequence[str], None] = "c4d8a3b9e7f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # INSERT ON CONFLICT DO NOTHING: para cada spec_definition con
    # categoria_raiz_id, asegurar asignación a esa raíz.
    op.execute("""
        INSERT INTO categoria_spec_templates
            (categoria_id, spec_def_id, prioridad,
             destacado, obligatorio,
             visible_en_card, visible_en_filtros, visible_en_nombre,
             ayuda)
        SELECT
            sd.categoria_raiz_id,
            sd.id,
            COALESCE(sd.prioridad, 100),
            COALESCE(sd.favorito, FALSE),
            FALSE,
            COALESCE(sd.favorito, FALSE),
            COALESCE(sd.en_filtros, FALSE),
            COALESCE(sd.en_nombre, FALSE),
            sd.ayuda
        FROM spec_definitions sd
        WHERE sd.categoria_raiz_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM categoria_spec_templates t
              WHERE t.categoria_id = sd.categoria_raiz_id
                AND t.spec_def_id = sd.id
          )
        ON CONFLICT (categoria_id, spec_def_id) DO NOTHING
    """)


def downgrade() -> None:
    # No revertimos: las asignaciones creadas no se pueden distinguir de
    # las que existían antes.
    pass
