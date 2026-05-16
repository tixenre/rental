"""spec_familia_jerarquia — familias jerárquicas a DB editable

Hasta ahora las familias jerárquicas de multi_enum (HDMI 1.4 < 2.0 < 2.1,
SDI 3G < 6G < 12G) vivían hardcodeadas en `routes/specs.py:_MULTI_ENUM_FAMILIES`.
Eso significa que agregar una versión nueva (HDMI 2.1a, SDI 24G) o una
familia nueva (USB-C versions, DisplayPort, NDI) requería tocar código.

Esta migración:
  1. Crea la tabla `spec_familia_jerarquia` (familia, valor, posicion).
  2. Backfill: pre-popula HDMI y SDI con la jerarquía actual.
  3. El motor `_compute_multi_enum_compat` ahora lee de DB con fallback al
     constant hardcoded — coexistencia segura.
  4. El admin puede editar via UI nueva `/admin/specs/familias` (commit
     siguiente).

Idempotente: ON CONFLICT DO NOTHING en los inserts.

Revision ID: a5c2e4f8b1d6
Revises: f3a5c7d9e1b6
Create Date: 2026-05-15
"""
from typing import Sequence, Union

revision: str = "a5c2e4f8b1d6"
down_revision: Union[str, Sequence[str], None] = "f3a5c7d9e1b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Seed inicial: las familias hardcodeadas que vivían en
# `routes/specs.py:_MULTI_ENUM_FAMILIES`. Una vez la tabla esté poblada,
# el motor lee de DB. El admin las edita desde la UI.
SEED_FAMILIAS: list[tuple[str, str, int]] = [
    # (familia, valor, posicion). Mayor posicion = más capaz.
    ("hdmi", "HDMI 1.4", 0),
    ("hdmi", "HDMI 2.0", 1),
    ("hdmi", "HDMI 2.1", 2),
    ("sdi",  "SDI 3G",   0),
    ("sdi",  "SDI 6G",   1),
    ("sdi",  "SDI 12G",  2),
]


def upgrade() -> None:
    import sqlalchemy as sa
    from alembic import op

    op.execute("""
        CREATE TABLE IF NOT EXISTS spec_familia_jerarquia (
            id          SERIAL PRIMARY KEY,
            familia     VARCHAR(64) NOT NULL,
            valor       VARCHAR(64) NOT NULL,
            posicion    INTEGER NOT NULL,
            spec_def_id INTEGER REFERENCES spec_definitions(id) ON DELETE CASCADE,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (familia, valor)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_fam_jer_familia_pos "
        "ON spec_familia_jerarquia (familia, posicion)"
    )

    bind = op.get_bind()
    for familia, valor, posicion in SEED_FAMILIAS:
        bind.execute(
            sa.text("""
                INSERT INTO spec_familia_jerarquia (familia, valor, posicion)
                VALUES (:f, :v, :p)
                ON CONFLICT (familia, valor) DO NOTHING
            """),
            {"f": familia, "v": valor, "p": posicion},
        )


def downgrade() -> None:
    from alembic import op
    op.execute("DROP INDEX IF EXISTS idx_fam_jer_familia_pos")
    op.execute("DROP TABLE IF EXISTS spec_familia_jerarquia")
