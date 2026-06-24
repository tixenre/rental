"""equipos: agregar foto_url_thumb (variante 160px de la principal para srcset)

La columna ya va en init_db() (schema en dos capas, decisión 2026-06-03). Esta
migración la agrega de forma idempotente en ambientes existentes. Queda NULL
hasta que un upload nuevo (genera display-thumb) o el backfill la llenen → mientras
tanto el front cae a foto_url_sm (cero rotura).

Revision ID: t1h2u3m4b5
Revises: m3rg3h34ds02
Create Date: 2026-06-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "t1h2u3m4b5"
down_revision: Union[str, Sequence[str], None] = "m3rg3h34ds02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS foto_url_thumb TEXT"))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE equipos DROP COLUMN IF EXISTS foto_url_thumb"))
