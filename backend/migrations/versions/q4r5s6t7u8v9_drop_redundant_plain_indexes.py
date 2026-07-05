"""Dropea 4 índices planos 100% redundantes contra un UNIQUE ya existente
sobre las mismas columnas — Postgres crea automáticamente un índice de
soporte para todo UNIQUE (constraint o inline), así que un índice plano
adicional sobre esas mismas columnas es puro peso muerto (costo de escritura
para siempre, cero beneficio de lectura). Encontrado auditando en vivo
pg_stat_user_indexes en prod (drift de copy-paste: se agregó el UNIQUE y,
separado, un CREATE INDEX explícito sobre la misma columna).

  - idx_marcas_nombre            → `marcas.nombre` ya es UNIQUE
  - idx_clientes_supabase_uid    → `clientes.supabase_uid` ya es UNIQUE
  - idx_spec_def_categoria       → mismas columnas que
                                    UNIQUE (categoria_raiz_id, spec_key)
  - idx_ediciones_taller_slug    → `ediciones_taller.slug` ya es UNIQUE

No se toca ningún índice PARCIAL (ej. `idx_spec_def_compat`,
`uniq_solicitud_pendiente_por_pedido`, `idx_carritos_activos_no_conf`,
`uq_factura_vigente_por_pedido`) — esos cubren un subconjunto de filas
distinto al índice general y SÍ son necesarios.

Revision ID: q4r5s6t7u8v9
Revises: j2k3l4m5n6o7
Create Date: 2026-07-04
"""
from typing import Sequence, Union
from alembic import op

revision: str = "q4r5s6t7u8v9"
down_revision: Union[str, Sequence[str], None] = "j2k3l4m5n6o7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_marcas_nombre")
    op.execute("DROP INDEX IF EXISTS idx_clientes_supabase_uid")
    op.execute("DROP INDEX IF EXISTS idx_spec_def_categoria")
    op.execute("DROP INDEX IF EXISTS idx_ediciones_taller_slug")


def downgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS idx_marcas_nombre ON marcas(nombre)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_clientes_supabase_uid ON clientes(supabase_uid)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_spec_def_categoria "
        "ON spec_definitions(categoria_raiz_id, spec_key)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ediciones_taller_slug "
        "ON ediciones_taller(slug)"
    )
