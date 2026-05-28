"""estudio: mapa_url (lo que pega el dueño) + mapa_embed_url (resuelto).

Revision ID: e3f7a9c2b5d4
Revises: d2e4f6a8c1b3
Create Date: 2026-05-27

El dueño puede pegar en el admin un link de Google Maps (`maps.app.goo.gl/...`),
una URL larga de `google.com/maps/...` o el código `<iframe>` que da "Compartir →
Insertar mapa". El backend lo parsea/resuelve y guarda dos campos:
- `mapa_url`: lo que pegó el dueño (sirve para el botón "Ver en Google Maps").
- `mapa_embed_url`: URL embebible para el iframe (resuelta si era shortlink).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e3f7a9c2b5d4"
# Re-encadenada después de mergear main: PR #564 + PR #569 agregaron
# e7c3a9f5d1b8 → c1e9f3a7b5d2 al chain. Quedamos como head linealizado.
down_revision: Union[str, Sequence[str], None] = "c1e9f3a7b5d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE estudio ADD COLUMN IF NOT EXISTS mapa_url TEXT NOT NULL DEFAULT ''"))
    conn.execute(sa.text("ALTER TABLE estudio ADD COLUMN IF NOT EXISTS mapa_embed_url TEXT NOT NULL DEFAULT ''"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE estudio DROP COLUMN IF EXISTS mapa_url"))
    conn.execute(sa.text("ALTER TABLE estudio DROP COLUMN IF EXISTS mapa_embed_url"))
