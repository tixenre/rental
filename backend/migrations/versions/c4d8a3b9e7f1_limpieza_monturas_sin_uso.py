"""limpieza_monturas_sin_uso: borrar Montura L/Z/PL/BMD si están vacías

Estas sub-cats estaban declaradas en el registry pero ningún equipo las
usa. Se sacaron del registry para que el seeder no las recree. Esta
migración las borra de la DB sólo si están realmente vacías (guard).

Si en producción algún equipo está asignado a alguna de estas monturas,
el DELETE no la toca y queda como sub-cat huérfana (no en registry, pero
con equipos). El admin la verá y decidirá qué hacer.

Revision ID: c4d8a3b9e7f1
Revises: a8c5d7e2f9b3
Create Date: 2026-05-20
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c4d8a3b9e7f1"
down_revision: Union[str, Sequence[str], None] = "a8c5d7e2f9b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Sólo borrar las sub-cats sin equipos asignados. Si alguien cargó un
    # equipo con "Montura L" en producción, lo respetamos.
    op.execute("""
        DELETE FROM categorias
        WHERE nombre IN ('Montura L', 'Montura Z', 'Montura PL', 'Montura BMD')
          AND id NOT IN (SELECT DISTINCT categoria_id FROM equipo_categorias)
    """)


def downgrade() -> None:
    # No restauramos automáticamente — si las querés de vuelta, agregalas
    # al registry y el seeder las crea al próximo boot.
    pass
