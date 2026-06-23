"""equipos: agregar foto_url_sm (variante 600px de la principal para srcset)

La columna ya va en init_db() (schema en dos capas, decisión 2026-06-03). Esta
migración la agrega de forma idempotente en ambientes existentes. Queda NULL
hasta que un upload nuevo (genera display-sm) o el backfill la llenen → mientras
tanto el front cae a foto_url (cero rotura).

Revision ID: s1r2c3s4e5t6
Revises: cart0sact1vos
Create Date: 2026-06-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "s1r2c3s4e5t6"
down_revision: Union[str, Sequence[str], None] = "cart0sact1vos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS foto_url_sm TEXT"))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE equipos DROP COLUMN IF EXISTS foto_url_sm"))
