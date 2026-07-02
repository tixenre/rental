"""emisores_arca: razon_social (retroactiva) + domicilio/iibb/inicio_actividades.

`razon_social` se agregó en 2026-06-30 solo al bootstrap (`init_db()`), sin su
migración Alembic espejo (MEMORIA 2026-06-03) — se cierra ese gap acá. Los tres
campos nuevos (domicilio, iibb, inicio_actividades) sacan del código hardcodeado
por nombre de emisor en `services/facturacion/pdf.py::_EMISORES_DATA` (bug: un
emisor nuevo que no fuera "pablo"/"santini" heredaba en silencio los datos
legales de Santini) — quedan como columnas administrables desde el back-office,
mismo patrón que razon_social.

Espeja init_db() (esquema en dos capas, MEMORIA 2026-06-03). Todo `IF NOT
EXISTS` para idempotencia aunque el bootstrap ya haya creado las columnas.

Revision ID: e4f6a8b0c2d4
Revises: d3e5f7a9b1c2
Create Date: 2026-07-02
"""

from typing import Sequence, Union

from alembic import op

revision: str = "e4f6a8b0c2d4"
down_revision: Union[str, Sequence[str], None] = "d3e5f7a9b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE emisores_arca ADD COLUMN IF NOT EXISTS razon_social TEXT")
    op.execute("ALTER TABLE emisores_arca ADD COLUMN IF NOT EXISTS domicilio TEXT")
    op.execute("ALTER TABLE emisores_arca ADD COLUMN IF NOT EXISTS iibb TEXT")
    op.execute("ALTER TABLE emisores_arca ADD COLUMN IF NOT EXISTS inicio_actividades TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE emisores_arca DROP COLUMN IF EXISTS inicio_actividades")
    op.execute("ALTER TABLE emisores_arca DROP COLUMN IF EXISTS iibb")
    op.execute("ALTER TABLE emisores_arca DROP COLUMN IF EXISTS domicilio")
    # razon_social no se dropea acá: preexistía sin migración propia antes de
    # esta (downgrade de ESTA revisión no debería borrar un campo que ya
    # estaba en uso desde antes).
