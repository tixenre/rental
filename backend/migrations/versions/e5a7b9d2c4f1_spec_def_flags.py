"""spec_def_flags: persistir flags y prioridad en spec_definitions

Sumar columnas a `spec_definitions`:
- `favorito` (bool, default false) — spec destacada en card / mini-ficha
  / lateral / pills sobre la descripción según prioridad y espacio.
- `en_nombre` (bool, default false) — incluida en el nombre auto-generado.
- `en_filtros` (bool, default false) — aparece en filtros del catálogo.
- `prioridad` (int, default 100) — orden visual; drag-and-drop en UI.

Los valores iniciales se siembran desde `backend/specs/registry.py` en el
próximo boot vía `registry_seeder.py`. A partir de ahí la DB manda.

Revision ID: e5a7b9d2c4f1
Revises: d3e4f5a6b7c8
Create Date: 2026-05-20
"""
from typing import Sequence, Union

from alembic import op

revision: str = "e5a7b9d2c4f1"
down_revision: Union[str, Sequence[str], None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE spec_definitions ADD COLUMN IF NOT EXISTS favorito BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE spec_definitions ADD COLUMN IF NOT EXISTS en_nombre BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE spec_definitions ADD COLUMN IF NOT EXISTS en_filtros BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE spec_definitions ADD COLUMN IF NOT EXISTS prioridad INTEGER NOT NULL DEFAULT 100")


def downgrade() -> None:
    op.execute("ALTER TABLE spec_definitions DROP COLUMN IF EXISTS favorito")
    op.execute("ALTER TABLE spec_definitions DROP COLUMN IF EXISTS en_nombre")
    op.execute("ALTER TABLE spec_definitions DROP COLUMN IF EXISTS en_filtros")
    op.execute("ALTER TABLE spec_definitions DROP COLUMN IF EXISTS prioridad")
