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

import json as _json


def specs_en_nombre_de_equipo(conn, equipo_id: int) -> list[dict]:
    """Specs marcadas `en_nombre=true` del equipo, para armar el nombre público.

    Resuelve la categoría por **`equipos.categoria_specs`** (la taxonomía de
    specs — Cámaras/Lentes/Filtros/…), NO por `equipo_categorias` (el árbol de
    catálogo): son fuentes distintas y el equipo puede estar bien clasificado en
    specs pero mal-tageado en el árbol (o al revés). Antes esto se leía por el
    árbol de catálogo (JOIN equipo_categorias con `categoria_raiz_id = c.id OR
    c.parent_id`), lo que dejaba el nombre público **vacío** para equipos con
    specs cargadas pero sin el tag de catálogo correcto (bug real: un filtro
    tageado solo en "Lentes" en vez de "Filtros"). Mismo criterio de resolución
    que usa el editor de specs del admin (`routes/specs/equipo_specs.py`).

    LEFT JOIN a `equipo_specs`: incluye specs SIN valor (el placeholder del
    template rinde vacío y el builder lo colapsa) para que el molde sea
    estable — el conjunto de placeholders lo define la categoría, no qué specs
    tenga cargadas este equipo puntual.

    Devuelve [{label, spec_key, value, tipo, unidad, tabla_columnas,
    output_config}] ordenado por prioridad, deduplicado por label. `[]` si el
    equipo no tiene `categoria_specs` o su nombre no resuelve a una categoría.
    """
    cs_row = conn.execute(
        "SELECT categoria_specs FROM equipos WHERE id = %s", (equipo_id,)
    ).fetchone()
    categoria_specs = dict(cs_row).get("categoria_specs") if cs_row else None
    if not categoria_specs:
        return []

    # Import lazy: evita el ciclo services.specs ↔ services.categorias al cargar
    # el módulo (mismo patrón que routes/specs/equipo_specs.py).
    from services.categorias import buscar_id_por_nombre
    raiz_id = buscar_id_por_nombre(conn, categoria_specs)
    if not raiz_id:
        return []

    rows = conn.execute(
        """
        SELECT sd.label, sd.spec_key, sd.tipo, sd.unidad,
               sd.tabla_columnas, sd.output_config,
               COALESCE(es.value, '') AS value,
               COALESCE(sd.prioridad, 100) AS prioridad
        FROM spec_definitions sd
        LEFT JOIN equipo_specs es
               ON es.equipo_id = %s AND es.spec_def_id = sd.id
        WHERE COALESCE(sd.en_nombre, FALSE) = TRUE
          AND sd.categoria_raiz_id = %s
        ORDER BY COALESCE(sd.prioridad, 100), sd.label
        """,
        (equipo_id, raiz_id),
    ).fetchall()

    out: list[dict] = []
    seen_labels: set[str] = set()
    for r in rows:
        d = dict(r)
        label = d["label"]
        key = (label or "").lower().strip()
        if key in seen_labels:
            continue
        seen_labels.add(key)
        cols = d["tabla_columnas"]
        if isinstance(cols, str):
            try:
                cols = _json.loads(cols)
            except Exception:
                cols = None
        oc = d["output_config"]
        if isinstance(oc, str):
            try:
                oc = _json.loads(oc)
            except Exception:
                oc = None
        out.append({
            "label": label,
            "spec_key": d["spec_key"],
            "value": d["value"] or "",
            "tipo": d["tipo"],
            "unidad": d["unidad"],
            "tabla_columnas": cols,
            "output_config": oc,
        })
    return out


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
