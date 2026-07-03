"""queries/search_source.py — proyección de specs a texto buscable (#1163 F4).

Simétrico a `_FICHA_EXPR` en routes/equipos/core.py: una expresión escalar
más para `busqueda.construir(campos, q)`. EN VIVO, no materializada — el
motor único de búsqueda (backend/busqueda/, decisión 2026-06-06) sigue
siendo la única fuente de "cómo se busca"; esto solo le agrega un campo.

Por equipo, agrega al texto buscable: el VALUE persistido (ya canónico
gracias al embudo, F3), el LABEL del spec ("Formato"), los alias de
CONCEPTO (`spec_definitions.aliases`, ej. "Sensor Type"→matchea el campo) y
los alias de VALOR (`spec_value_aliases`, ej. "FF"→matchea "Full-frame").
Así "FF" o "IBIS" encuentran equipos aunque esas palabras no estén en el
nombre/ficha.
"""

from __future__ import annotations

from typing import Literal


def specs_search_expr(table_alias: Literal["e"] = "e") -> str:
    """Expresión escalar SQL: todas las specs de un equipo, aplanadas a un
    string. NULL si el equipo no tiene specs (NULL-safe, como _FICHA_EXPR).

    `table_alias` se interpola directo en el SQL (nunca es input de
    usuario — mismo patrón que `sql_filtro_categoria` en categorias/ancestry.py)."""
    return f"""
        (SELECT string_agg(t.txt, ' ') FROM (
            SELECT es.value || ' ' || sd.label
                || ' ' || coalesce(
                    (SELECT string_agg(al, ' ') FROM jsonb_array_elements_text(sd.aliases) al), ''
                )
                || ' ' || coalesce(
                    (SELECT string_agg(sva.alias, ' ') FROM spec_value_aliases sva
                     WHERE sva.spec_def_id = sd.id AND sva.valor_canonico = es.value), ''
                )
                AS txt
            FROM equipo_specs es
            JOIN spec_definitions sd ON sd.id = es.spec_def_id
            WHERE es.equipo_id = {table_alias}.id
        ) t)
    """
