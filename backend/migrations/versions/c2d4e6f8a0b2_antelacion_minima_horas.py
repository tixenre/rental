"""antelacion_minima_horas: seed del setting de lead-time (#1126)

Siembra `app_settings.antelacion_minima_horas = '0'` (apagado por default; el
admin lo sube desde /admin/settings para exigir un mínimo de horas entre el
pedido y el retiro). La tabla `app_settings` ya existe (init_db); esto solo
agrega la fila para entornos que avanzan por migración (espeja el patrón de
`modificacion_ventana_horas`).

Revision ID: c2d4e6f8a0b2
Revises: b1a2c3d4e5f6
Create Date: 2026-06-30
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c2d4e6f8a0b2"
down_revision: Union[str, Sequence[str], None] = "b1a2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO app_settings (key, value, updated_by)
        VALUES ('antelacion_minima_horas', '0', 'system-seed')
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM app_settings WHERE key = 'antelacion_minima_horas'")
