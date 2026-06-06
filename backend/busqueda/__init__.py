"""Paquete `busqueda` — motor único de búsqueda fuzzy del sistema.

Fuente única de "cómo se normaliza y cómo se matchea/rankea un término". Lo
consumen los routes que buscan texto (clientes, equipos) en vez de copiar
`ILIKE` ad-hoc. Espeja el patrón de `reservas/` y `reportes/`.

- `normalizar` / `tokenizar`: forma canónica del término (sin acentos, sin
  guiones, espacios colapsados). El front la espeja en `src/lib/search/`.
- `construir`: arma el WHERE + score (con params) para enchufar en una query.

Requiere las extensiones Postgres `pg_trgm` y `unaccent` y la función inmutable
`f_unaccent`, creadas en `database.init_db()` (y su migración espejo).
"""

from busqueda.normalizar import (
    MAX_LEN,
    MIN_LEN,
    normalizar,
    normalizar_para_registro,
    quitar_acentos,
    tokenizar,
)
from busqueda.motor import (
    UMBRAL_FUZZY,
    Predicado,
    campo_sql,
    construir,
)

__all__ = [
    "MAX_LEN",
    "MIN_LEN",
    "Predicado",
    "UMBRAL_FUZZY",
    "campo_sql",
    "construir",
    "normalizar",
    "normalizar_para_registro",
    "quitar_acentos",
    "tokenizar",
]
