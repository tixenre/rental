"""multi_enum siempre como JSON array (no CSV)

Hasta ahora el storage de `equipo_specs.value` para specs tipo `multi_enum`
era ambiguo: el frontend guardaba CSV (`"HDMI 2.0, SDI 12G"`) y el
autocompletar IA a veces guardaba JSON array (`["HDMI 2.0", "SDI 12G"]`).
La función `_parse_multi_enum_value` toleraba ambos por defensa.

Esta migración canoniza: cualquier value tipo multi_enum se persiste como
JSON array. Backfill convierte los CSV existentes. El endpoint PUT
`/admin/equipos/{id}/specs` valida y normaliza al persistir (sin
romper callers viejos).

Revision ID: f3a5c7d9e1b6
Revises: e2f4a6b8c1d5
Create Date: 2026-05-15
"""
import json as _json
from typing import Sequence, Union

revision: str = "f3a5c7d9e1b6"
down_revision: Union[str, Sequence[str], None] = "e2f4a6b8c1d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    import sqlalchemy as sa
    from alembic import op
    bind = op.get_bind()

    # Buscar todos los valores cargados para specs tipo multi_enum.
    rows = bind.execute(
        sa.text("""
            SELECT es.equipo_id, es.spec_def_id, es.value
            FROM equipo_specs es
            JOIN spec_definitions sd ON sd.id = es.spec_def_id
            WHERE sd.tipo = 'multi_enum'
              AND es.value IS NOT NULL
              AND TRIM(es.value) <> ''
        """)
    ).fetchall()

    for row in rows:
        equipo_id = row[0]
        spec_def_id = row[1]
        value = (row[2] or "").strip()
        # Si ya es JSON array válido, skip.
        if value.startswith("["):
            try:
                _json.loads(value)
                continue
            except Exception:
                pass
        # Convertir CSV → JSON array.
        items = [p.strip() for p in value.split(",") if p.strip()]
        if not items:
            continue
        new_value = _json.dumps(items, ensure_ascii=False)
        bind.execute(
            sa.text("""
                UPDATE equipo_specs SET value = :val
                WHERE equipo_id = :eid AND spec_def_id = :sid
            """),
            {"val": new_value, "eid": equipo_id, "sid": spec_def_id},
        )


def downgrade() -> None:
    # No-op: degradar a CSV pierde info y rompe shapes recientes.
    # Para revertir, restore desde backup.
    pass
