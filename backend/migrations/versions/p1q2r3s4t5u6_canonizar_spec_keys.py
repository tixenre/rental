"""spec_definitions: canonizar spec_keys (#535)

Renombres de spec_key que alinean el código del registry con la DB:

- Cámaras: 'power_consumption_w' → 'consumo_w' (mismo key canónico que
  Iluminación, label 'Consumo eléctrico'). Unifica extracción/aliases.
- Lentes: 'distancia_minima_m' → 'distancia_minima_cm' (la unidad ya era cm;
  la key decía '_m' por error histórico).

El rename preserva la MISMA fila de spec_definitions (mismo id) → equipo_specs y
categoria_spec_templates quedan intactos (referencian por spec_def_id, no por
spec_key). El guard NOT EXISTS evita violar UNIQUE(categoria_raiz_id, spec_key)
si la key canónica ya existiera en esa categoría.

Nota: el mismo rename está espejado en init_db() (database.py), que corre en
cada arranque ANTES del seeder del registry — esa es la red que impide que el
seeder purgue la key vieja con CASCADE si esta migración no llegara a correr.

Revision ID: p1q2r3s4t5u6
Revises: o1p2q3r4s5t6
Create Date: 2026-06-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p1q2r3s4t5u6"
down_revision: Union[str, Sequence[str], None] = "o1p2q3r4s5t6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Cámaras: power_consumption_w → consumo_w
    bind.execute(sa.text("""
        UPDATE spec_definitions sd
           SET spec_key = 'consumo_w', label = 'Consumo eléctrico', updated_at = NOW()
         WHERE sd.spec_key = 'power_consumption_w'
           AND sd.categoria_raiz_id = (SELECT id FROM categorias WHERE nombre = 'Cámaras')
           AND NOT EXISTS (
               SELECT 1 FROM spec_definitions x
                WHERE x.categoria_raiz_id = sd.categoria_raiz_id AND x.spec_key = 'consumo_w'
           )
    """))

    # Lentes: distancia_minima_m → distancia_minima_cm
    bind.execute(sa.text("""
        UPDATE spec_definitions sd
           SET spec_key = 'distancia_minima_cm', updated_at = NOW()
         WHERE sd.spec_key = 'distancia_minima_m'
           AND sd.categoria_raiz_id = (SELECT id FROM categorias WHERE nombre = 'Lentes')
           AND NOT EXISTS (
               SELECT 1 FROM spec_definitions x
                WHERE x.categoria_raiz_id = sd.categoria_raiz_id AND x.spec_key = 'distancia_minima_cm'
           )
    """))


def downgrade() -> None:
    bind = op.get_bind()
    # Revertir los renames (el registry del código tendría que revertirse también).
    bind.execute(sa.text("""
        UPDATE spec_definitions sd
           SET spec_key = 'power_consumption_w', label = 'Consumo', updated_at = NOW()
         WHERE sd.spec_key = 'consumo_w'
           AND sd.categoria_raiz_id = (SELECT id FROM categorias WHERE nombre = 'Cámaras')
    """))
    bind.execute(sa.text("""
        UPDATE spec_definitions sd
           SET spec_key = 'distancia_minima_m', updated_at = NOW()
         WHERE sd.spec_key = 'distancia_minima_cm'
           AND sd.categoria_raiz_id = (SELECT id FROM categorias WHERE nombre = 'Lentes')
    """))
