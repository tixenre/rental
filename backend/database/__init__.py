"""Paquete `database` (#501 Fase 5 — split del god-module `database.py`).

Conexión PostgreSQL con pool, esquema y helpers. La superficie pública es amplia
y la importa casi todo el backend (`from database import get_db, MARCA_SUBQUERY,
…`). El split es interno:

- `core`      → spine: paths, fragmentos SQL canónicos (marca), config + pool de
                conexiones, wrappers sqlite-compat (`PGConnection`/`PGCursor`/`PGRow`),
                helpers de conexión/fecha (`get_db`, `row_to_dict`, `to_datetime`,
                `now_ar`, `to_iso`).
- `equipos`   → enriquecimiento de equipos (`attach_*`).
- `schema`    → bootstrap idempotente del esquema (`init_db`).

Este `__init__` re-exporta la superficie pública estable para que
`from database import X` (y el acceso por atributo `database.X`) sigan funcionando
sin cambios. Cada submódulo importa de `core`; `core` no importa de vuelta.
"""
from database.core import (
    # ── Paths ──
    BASE,
    FRONT,
    FRONT_NEW,
    # ── Config + pool ──
    DATABASE_URL,
    get_connection_params,
    pool_max,
    # ── Fragmentos SQL canónicos (marca) ──
    MARCA_NOMBRE_EXPR,
    MARCA_SUBQUERY,
    marca_nombre_expr,
    marca_subquery,
    # ── Wrappers sqlite-compat ──
    PGConnection,
    PGCursor,
    PGRow,
    # ── Helpers de conexión / fecha ──
    get_db,
    row_to_dict,
    to_datetime,
    to_iso,
    now_ar,
)
from database.equipos import (
    attach_kit,
    attach_categorias,
    attach_ficha,
    attach_specs_destacados,
    attach_specs_estructuradas,
    query_ficha_batch,
    shape_ficha_rows,
)
from database.schema import init_db

__all__ = [
    "BASE", "FRONT", "FRONT_NEW",
    "DATABASE_URL", "get_connection_params", "pool_max",
    "MARCA_NOMBRE_EXPR", "MARCA_SUBQUERY", "marca_nombre_expr", "marca_subquery",
    "PGConnection", "PGCursor", "PGRow",
    "get_db", "row_to_dict", "to_datetime", "to_iso", "now_ar",
    "attach_kit", "attach_categorias", "attach_ficha",
    "attach_specs_destacados", "attach_specs_estructuradas",
    "query_ficha_batch", "shape_ficha_rows",
    "init_db",
]
