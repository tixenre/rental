"""agregar nombre_publico_template a categorias

Permite que el admin defina por categoría una plantilla para generar
el nombre público del equipo a partir de marca, modelo, specs.

Sintaxis: placeholders entre llaves.
  - {marca}, {modelo}, {tipo}: campos del equipo / nombre de la categoría raíz.
  - {spec:Label}: valor del spec con ese label (case-insensitive).

Ej template para Cámaras:
  "Cámara {marca} {modelo} {spec:Montura} {spec:Formato}"

Si el template es NULL o vacío, el sistema cae al template hardcoded
existente (nombre-publico.ts), preservando comportamiento actual.

Revision ID: f17e3a8b4c92
Revises: c4d28f1b9a07
Create Date: 2026-05-14
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f17e3a8b4c92"
down_revision: Union[str, Sequence[str], None] = "c4d28f1b9a07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE categorias "
        "ADD COLUMN IF NOT EXISTS nombre_publico_template TEXT"
    )


def downgrade() -> None:
    pass
