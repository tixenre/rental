"""categoria_specs en equipos

Agregar `categoria_specs TEXT` a `equipos`: la categoría que define qué specs
técnicas aplican (1 de las 5 del registry: Cámaras/Lentes/Iluminación/
Adaptadores/Filtros) y la generación del nombre público. Desacoplado del árbol
de categorías de catálogo (`equipo_categorias`), que pasa a ser una agrupación
manual web-managed para el front-office, independiente de los specs.

Backfill: para cada equipo se camina el árbol de sus categorías de catálogo
hasta la raíz; si la raíz es una de las 5 funcionales, se asigna como
`categoria_specs`. Así no se pierde el ruteo de specs existente.

Revision ID: f4b9d2a7c3e8
Revises: e2c6f4a8b1d7
Create Date: 2026-05-24
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f4b9d2a7c3e8"
down_revision: Union[str, Sequence[str], None] = "e2c6f4a8b1d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS categoria_specs TEXT")

    # Backfill desde el árbol de catálogo: para cada categoría, resolver su raíz
    # (walk parent_id), y si la raíz es funcional, asignarla al equipo. DISTINCT
    # ON garantiza un único valor determinístico cuando un equipo cuelga de más
    # de una raíz funcional (gana la de menor id de raíz).
    op.execute(
        """
        WITH RECURSIVE up AS (
            SELECT id, parent_id, nombre, id AS start_id
            FROM categorias
            UNION ALL
            SELECT c.id, c.parent_id, c.nombre, up.start_id
            FROM categorias c
            JOIN up ON c.id = up.parent_id
        ),
        roots AS (
            SELECT start_id AS cat_id, id AS root_id, nombre AS root_name
            FROM up
            WHERE parent_id IS NULL
        ),
        elegidas AS (
            SELECT DISTINCT ON (ec.equipo_id)
                   ec.equipo_id, roots.root_name
            FROM equipo_categorias ec
            JOIN roots ON roots.cat_id = ec.categoria_id
            WHERE roots.root_name IN
                  ('Cámaras', 'Lentes', 'Iluminación', 'Adaptadores', 'Filtros')
            ORDER BY ec.equipo_id, roots.root_id
        )
        UPDATE equipos e
        SET categoria_specs = elegidas.root_name
        FROM elegidas
        WHERE e.id = elegidas.equipo_id
          AND e.categoria_specs IS NULL
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE equipos DROP COLUMN IF EXISTS categoria_specs")
