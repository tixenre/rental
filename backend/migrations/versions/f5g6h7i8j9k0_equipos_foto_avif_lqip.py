"""equipos: variantes AVIF + LQIP denormalizadas de la foto principal (perf catálogo).

Acompañan a foto_url/foto_url_sm/foto_url_thumb. El front sirve <picture> con AVIF
+ blur-up LQIP. Todas nullable (legacy = NULL → fallback a webp). Paridad con
database/schema.py::init_db() (MEMORIA 2026-06-03).

Revision ID: f5g6h7i8j9k0
Revises: e4f5g6h7i8j9
Create Date: 2026-06-25
"""
from alembic import op

revision = "f5g6h7i8j9k0"
down_revision = "e4f5g6h7i8j9"  # F4: marcas.logo_url_sm
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS foto_url_avif TEXT")
    op.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS foto_url_sm_avif TEXT")
    op.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS foto_url_thumb_avif TEXT")
    op.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS foto_lqip TEXT")


def downgrade():
    op.execute("ALTER TABLE equipos DROP COLUMN IF EXISTS foto_url_avif")
    op.execute("ALTER TABLE equipos DROP COLUMN IF EXISTS foto_url_sm_avif")
    op.execute("ALTER TABLE equipos DROP COLUMN IF EXISTS foto_url_thumb_avif")
    op.execute("ALTER TABLE equipos DROP COLUMN IF EXISTS foto_lqip")
