"""backfill de equipos.slug (mueve el self-heal del export a una migración)

Hasta #922 los slugs faltantes se poblaban dentro del EXPORT de dataio
(`_ensure_equipos_slug`), que corría DDL+UPDATE+commit cada vez que se "bajaba
un backup" — un export, read-only por contrato, mutando esquema/datos (locks en
prod, commit incondicional). El esquema (columna + UNIQUE) ya lo crean las
migraciones e4a7c1f8d6b2 / f5b8d2e4a9c1 e `init_db()`; lo que faltaba en el
camino automático era el BACKFILL del valor. Esta migración lo hace, idempotente
(solo `slug IS NULL`), reusando la regla canónica de slug de `dataio.slug`. De
ahí en más el alta de equipo nace con slug y `init_db()` rellena cualquier
straggler, así que el export ya no necesita auto-curar.

Revision ID: c2d4e6f8a0b1
Revises: i9j0k1l2m3n4
Create Date: 2026-06-20
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "c2d4e6f8a0b1"
down_revision: Union[str, Sequence[str], None] = "i9j0k1l2m3n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Regla canónica de generación/desambiguación de slug (fuente única).
    from dataio.slug import equipo_slug, slug_unico

    bind = op.get_bind()
    pendientes = bind.execute(text("""
        SELECT e.id, e.nombre, e.modelo,
               (SELECT m.nombre FROM marcas m WHERE m.id = e.brand_id) AS marca
        FROM equipos e
        WHERE e.slug IS NULL AND e.eliminado_at IS NULL
    """)).mappings().all()
    if not pendientes:
        return
    ocupados = {
        row[0]
        for row in bind.execute(
            text("SELECT slug FROM equipos WHERE slug IS NOT NULL")
        ).all()
    }
    for r in pendientes:
        base = equipo_slug(r["marca"], r["modelo"], r["nombre"]) or f"equipo-{r['id']}"
        slug = slug_unico(base, ocupados)
        ocupados.add(slug)
        bind.execute(
            text("UPDATE equipos SET slug = :s WHERE id = :i"),
            {"s": slug, "i": r["id"]},
        )


def downgrade() -> None:
    # No-op: vaciar slugs poblados rompería el export/import dataio y las URLs.
    pass
