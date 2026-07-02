"""queries/equipo_specs.py — specs YA PERSISTIDAS de un lote de equipos.

Fuente única del JOIN equipo_specs+spec_definitions+categoria_spec_templates
que arma "qué specs tiene este equipo, con su label/tipo/unidad/flags". Antes
esto vivía duplicado: `database/equipos.py::attach_specs_estructuradas`
(ficha pública) y `attach_specs_destacados` (quick facts) cada uno escribía
su propio SQL contra las mismas 3 tablas — hueco marcado en el propio
CLAUDE.md de este paquete ("queries/equipo_specs.py — Fase futura, no
existe") hasta que se resolvió acá.

Devuelve rows CRUDOS (value canónico, sin renderizar) — cada caller sigue
decidiendo su propia política de display sobre esos mismos rows. Eso NO es
duplicación: un bool=false se omite en la ficha pública, se muestra
explícito "No" en el preview pre-persist de specs_ingesta, y es un checkbox
en el form admin — 3 audiencias, 3 decisiones de UX legítimamente distintas
(ver Gotcha #2 de `services/specs_ingesta/parse/serialize.py`). Lo que NO
tenía que estar duplicado era el QUERY en sí.
"""

from __future__ import annotations


def get_equipo_specs_rows(conn, equipo_ids: list[int]) -> dict[int, list[dict]]:
    """{equipo_id: [{spec_def_id, spec_key, label, tipo, unidad, value,
    prioridad, en_card, en_filtros, destacado}]} para el lote de equipo_ids.

    Dedup por (equipo_id, spec_def_id) — un equipo puede estar en varias
    categorías de la misma raíz, quedándose con la de mayor prioridad
    (DISTINCT ON). `{}` si `equipo_ids` está vacío (no ejecuta el IN () inválido)."""
    if not equipo_ids:
        return {}
    placeholders = ",".join(["%s"] * len(equipo_ids))
    rows = conn.execute(
        f"""
        SELECT DISTINCT ON (es.equipo_id, sd.id)
            es.equipo_id, sd.id AS spec_def_id, sd.spec_key, sd.label,
            sd.tipo, sd.unidad, es.value,
            COALESCE(sd.prioridad, 100) AS prioridad,
            COALESCE(sd.favorito, FALSE) AS en_card,
            COALESCE(sd.en_filtros, FALSE) AS en_filtros,
            COALESCE(sd.favorito, FALSE) AS destacado
        FROM equipo_specs es
        JOIN equipo_categorias ec ON ec.equipo_id = es.equipo_id
        JOIN spec_definitions sd ON sd.id = es.spec_def_id
        JOIN categoria_spec_templates t
            ON t.spec_def_id = es.spec_def_id
           AND t.categoria_id = ec.categoria_id
        WHERE es.equipo_id IN ({placeholders})
        ORDER BY es.equipo_id, sd.id, COALESCE(sd.prioridad, 100)
        """,
        tuple(equipo_ids),
    ).fetchall()

    out: dict[int, list[dict]] = {eid: [] for eid in equipo_ids}
    for r in rows:
        row = dict(r)
        out[row["equipo_id"]].append(row)
    return out
