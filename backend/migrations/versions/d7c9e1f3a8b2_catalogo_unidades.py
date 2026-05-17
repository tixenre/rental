"""catálogo global de unidades

Tabla `unidades` con todas las unidades del sistema (lm, K, V, A, W, etc.).
Cada unidad tiene símbolo único + nombre + dimensión (luminosidad, temperatura…).

Los specs tipo tabla con columnas `valor_unidad` pueden referenciar este
catálogo para que el dueño elija de una lista cerrada en lugar de escribir
libre. La unidad en cada celda sigue guardándose como string (símbolo) para
mantener compat — el catálogo es solo fuente de verdad de qué existe.

Plus: ALTER TABLE idempotente para `spec_definitions.tabla_columnas` (que
ya se aplicó manualmente fuera de alembic durante el wipe, esta línea asegura
que un init fresh tenga la columna).

Revision ID: d7c9e1f3a8b2
Revises: f8a2b4c6d9e1
Create Date: 2026-05-15
"""
from typing import Sequence, Union

from alembic import op


revision: str = "d7c9e1f3a8b2"
down_revision: Union[str, None] = "f8a2b4c6d9e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tabla catálogo. Idempotente para fresh installs y reaplicaciones.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS unidades (
            id          SERIAL PRIMARY KEY,
            simbolo     VARCHAR(16) UNIQUE NOT NULL,
            nombre      VARCHAR(64) NOT NULL,
            dimension   VARCHAR(32),
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_unidades_dimension ON unidades(dimension)"
    )

    # ALTER idempotente para spec_definitions.tabla_columnas — esta columna ya
    # se agregó manualmente durante el wipe (F11), pero un fresh install vendría
    # sin ella si no estuviera acá.
    op.execute(
        "ALTER TABLE spec_definitions ADD COLUMN IF NOT EXISTS tabla_columnas JSONB"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS unidades")
    # tabla_columnas la dejamos — la usan specs existentes.
