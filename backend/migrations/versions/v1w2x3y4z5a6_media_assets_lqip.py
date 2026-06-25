"""media_assets: columna lqip para blur-up placeholder (F0e)

Agrega `lqip TEXT`: data URI base64 de un JPEG 4×4px generado del original.
Se usa en el frontend como fondo CSS mientras carga la variante CDN (blur-up).
Null para assets anteriores a F0e (el frontend trata null como sin placeholder).

Idempotente: ADD COLUMN IF NOT EXISTS.
Espeja init_db() (database/schema.py) según MEMORIA 2026-06-03.

Revision ID: v1w2x3y4z5a6
Revises: u2v3w4x5y6z7
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa

revision = "v1w2x3y4z5a6"
down_revision = "u2v3w4x5y6z7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS lqip TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS lqip")
