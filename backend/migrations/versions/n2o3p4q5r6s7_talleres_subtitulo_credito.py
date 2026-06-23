"""Actualiza subtítulo del taller Jime Troncoso a 'rambla × jime troncoso'.

Convención de crédito: el campo subtitulo refleja la autoría/co-hosting del taller.
Variantes: 'rambla × nombre' (colaboración), nombre solo, o vacío (solo Rambla).
"""

from __future__ import annotations

from typing import Union, Sequence

from alembic import op

revision: str = "n2o3p4q5r6s7"
down_revision: Union[str, Sequence[str], None] = "m1e2r3g4e5h6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE talleres
        SET subtitulo = 'rambla × jime troncoso'
        WHERE slug = 'direccion-de-arte-jime-troncoso'
          AND subtitulo = 'x Jime Troncoso'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE talleres
        SET subtitulo = 'x Jime Troncoso'
        WHERE slug = 'direccion-de-arte-jime-troncoso'
          AND subtitulo = 'rambla × jime troncoso'
    """)
