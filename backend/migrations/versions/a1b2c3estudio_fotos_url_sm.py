"""estudio_fotos: agregar url_sm (variante 800px hero para srcset)

La columna ya va en init_db() (schema en dos capas, decisión 2026-06-03). Esta
migración la agrega de forma idempotente en ambientes existentes. Queda NULL
hasta que un upload nuevo (genera display-sm) o el backfill la llenen → mientras
tanto el front cae a url (cero rotura).

Revision ID: a1b2c3estudio
Revises: s1r2c3s4e5t6
Create Date: 2026-06-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3estudio"
down_revision: Union[str, Sequence[str], None] = "s1r2c3s4e5t6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE estudio_fotos ADD COLUMN IF NOT EXISTS url_sm TEXT"))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE estudio_fotos DROP COLUMN IF EXISTS url_sm"))
