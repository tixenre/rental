"""bust cache equipos foto_url

Cache-bust de las fotos viejas que se subieron antes del #311 (timestamp
en el filename). Esas fotos tienen URLs sin query string, y muchos
dispositivos cachearon un 404 contra esas URLs (R2 sirve con immutable
max-age=1año). Re-subir manualmente equipo por equipo no es viable.

Solución: agregar `?v={epoch_de_updated_at}` a cada foto_url. La nueva
URL es distinta del cache key viejo → los dispositivos hacen fetch
fresco. Si en el futuro el admin actualiza el equipo (updated_at cambia),
una nueva migración o aplicar la misma lógica online lo re-bust.

Idempotente: solo afecta URLs que NO tienen ya un parámetro v=.

Revision ID: c4d28f1b9a07
Revises: 9b27c84e5a01
Create Date: 2026-05-14
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c4d28f1b9a07"
down_revision: Union[str, Sequence[str], None] = "9b27c84e5a01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Agrega ?v=<epoch> a foto_url si no tiene un parámetro v= existente.
    # Usa ? si la URL no tiene query string, & si ya tiene.
    op.execute(
        """
        UPDATE equipos
        SET foto_url = foto_url
            || CASE WHEN foto_url LIKE '%?%' THEN '&' ELSE '?' END
            || 'v=' || EXTRACT(EPOCH FROM updated_at)::bigint
        WHERE foto_url IS NOT NULL
          AND foto_url NOT LIKE '%?v=%'
          AND foto_url NOT LIKE '%&v=%'
        """
    )


def downgrade() -> None:
    pass
