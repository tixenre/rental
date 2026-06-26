"""merge: une la cadena de trabajos del estudio con la cadena principal.

La galería de trabajos del estudio se versionó en una rama propia (base
z0a1b2c3d4e5) que nunca reconvergió con la cadena principal (head
f5g6h7i8j9k0), dejando dos heads. Esta migración de merge (no-op) las une
en una sola head para que `alembic upgrade head` sea inequívoco.

Contexto: las tres primeras migraciones de la rama de estudio reusaban IDs
ya existentes en la cadena de contabilidad/marcas (a1b2c3d4e5f6 /
b2c3d4e5f6a7 / c3d4e5f6a7b8), lo que generaba un ciclo. Se renombraron a
estud1trabaj / estud2social / estud3catdsc; este merge cierra el arreglo.

Revision ID: mrgestudmain
Revises: c9853df02b18, f5g6h7i8j9k0
Create Date: 2026-06-25
"""

from typing import Sequence, Union

revision: str = "mrgestudmain"
down_revision: Union[str, Sequence[str], None] = ("c9853df02b18", "f5g6h7i8j9k0")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge no-op: sólo une las dos ramas del grafo de revisiones.
    pass


def downgrade() -> None:
    pass
