"""spec_value_aliases: embudo de alias de valor (rediseño specs, #1163 F2)

Sinónimos que apuntan a un value canónico de un spec enum/multi_enum (ej.
"FF" → "Full-frame"). Sirve cuádruple: normaliza al persistir, valida
mapeando, alimenta la búsqueda, y de paso arregla la compatibilidad (el
motor matchea por igualdad exacta de value — con el embudo, dos equipos
que dijeron "FF" y "Full-frame" terminan guardando lo mismo).

Espejada en init_db() (database/schema.py) — esquema en dos capas, decisión
2026-06-03 — así existe aunque esta migración no llegue a correr.

Todavía sin consumidor (Fase 2, el embudo está apagado):
services/specs/normalize/value_funnel.py la lee, pero coerce/validation no
lo llaman hasta la Fase 3. Ver docs/PLAN_SPECS_REDISENO.md.

Revision ID: e111286012ff
Revises: d3e5f7a9b1c2
Create Date: 2026-07-01 19:50:59.672701

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e111286012ff'
down_revision: Union[str, Sequence[str], None] = 'd3e5f7a9b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS spec_value_aliases (
            spec_def_id    INTEGER NOT NULL REFERENCES spec_definitions(id) ON DELETE CASCADE,
            alias          TEXT NOT NULL,
            valor_canonico TEXT NOT NULL,
            PRIMARY KEY (spec_def_id, alias)
        )
    """))
    bind.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_value_alias_canon "
        "ON spec_value_aliases(spec_def_id, valor_canonico)"
    ))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP TABLE IF EXISTS spec_value_aliases"))
