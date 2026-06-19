"""baseline: marca el estado pre-Alembic del schema actual.

NO crea ni modifica nada. Su único propósito es marcar el punto de partida:
la versión del schema que ya existía cuando se introdujo Alembic.

Workflow:

- Sobre **una BD nueva** (dev local desde cero):
    1. El código de `database.py::init_db()` crea todo el schema con
       `CREATE TABLE IF NOT EXISTS` y `ALTER TABLE IF NOT EXISTS`.
    2. Después: `alembic upgrade head` — corre esta migración (no-op) +
       cualquier migración nueva posterior.

- Sobre la **BD existente de producción** (al primer deploy con Alembic):
    1. `alembic stamp head` marca el estado actual como esta revisión sin
       correr nada (el schema ya existe).
    2. Futuros deploys: `alembic upgrade head` aplica solo las migraciones
       nuevas que se agreguen después.

- Para **agregar una nueva migración** (cambio de schema):
    cd backend && alembic revision -m "agregar columna foo a equipos"
    # editar el archivo generado en migrations/versions/
    alembic upgrade head  # local; en prod corre automático

Revision ID: 905bd97562e1
Revises:
Create Date: 2026-05-11
"""
from typing import Sequence, Union



# revision identifiers, used by Alembic.
revision: str = "905bd97562e1"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op. El schema actual ya fue creado por database.py::init_db()."""
    pass


def downgrade() -> None:
    """No-op. No tiene sentido revertir el baseline."""
    pass
