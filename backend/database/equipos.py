"""database/equipos.py — enriquecimiento de equipos (#501 Fase 5).

Helpers `attach_*` que, dado un lote de equipos (list[dict]), les adjuntan en vivo
su kit, categorías, ficha y specs (destacadas + estructuradas). Move-verbatim
desde `database.py`. `attach_kit` deriva el contenido de la puerta única
`services.contenido` (fuente única del "qué incluye").
"""


def attach_kit(conn, equipos: list[dict]) -> list[dict]:
    """Agrega componentes de kit a cada equipo, vía la puerta única
    `services.contenido` (fuente única del "qué incluye"). `solo_activos=True`:
    el catálogo NO muestra componentes soft-deleted — preserva el criterio previo
    de esta función. Import lazy para evitar el ciclo database↔services."""
    if not equipos:
        return equipos

    from services.contenido import contenido_de_batch

    ids = [e["id"] for e in equipos]
    por_equipo = contenido_de_batch(conn, ids, solo_activos=True)
    for e in equipos:
        e["kit"] = [{
            "componente_id": c["componente_id"],
            "nombre":        c["nombre"],
            "marca":         c["marca"],
            "foto_url":      c["foto_url"],
            "cantidad":      c["cantidad"],
            "descuento_pct": c["descuento_pct"],
            "esencial":      c["esencial"],
        } for c in por_equipo.get(e["id"], [])]

    return equipos


def attach_categorias(conn, equipos: list[dict]) -> list[dict]:
    """Agrega `categorias` (lista de {id, nombre, parent_id}) a cada equipo."""
    if not equipos:
        return equipos
    from services.categorias.queries.ancestry import categorias_de_equipos
    ids = [e["id"] for e in equipos]
    cat_map = categorias_de_equipos(conn, ids)
    for e in equipos:
        e["categorias"] = cat_map.get(e["id"], [])
    return equipos


_FICHA_KEYS = (
    "descripcion", "notas",
    "keywords_json", "nombre_publico_template",
    "conectividad_json", "compatible_con_json",
    "video_url", "precio_bh_usd", "fuente_url", "fuente_titulo",
    "enriquecido_at", "enriquecido_fuente",
    "contenido_incluido_json",
)


def query_ficha_batch(equipo_ids: list[int]) -> tuple[str, tuple] | None:
    """SQL + params de `attach_ficha` — separado de la ejecución para que un
    caller que ya corre OTRAS queries independientes (ej. el pipeline de
    `services.catalogo.proyeccion.proyectar_lista`, #1240) pueda incluir esta
    en el mismo lote. `None` si `equipo_ids` está vacío."""
    if not equipo_ids:
        return None
    placeholders = ",".join(["%s"] * len(equipo_ids))
    sql = f"""
        SELECT equipo_id, descripcion, notas,
               keywords_json, nombre_publico_template,
               conectividad_json, compatible_con_json,
               video_url, precio_bh_usd, fuente_url, fuente_titulo,
               enriquecido_at, enriquecido_fuente,
               contenido_incluido_json
        FROM equipo_fichas
        WHERE equipo_id IN ({placeholders})
    """
    return sql, tuple(equipo_ids)


def shape_ficha_rows(rows, equipo_ids: list[int]) -> dict[int, dict]:
    """Da forma `{equipo_id: ficha_dict}` a filas YA obtenidas de
    `query_ficha_batch`. Un equipo sin ficha propia aparece con todos los
    campos en `None` (mismo default que `attach_ficha` siempre dio)."""
    f_map: dict[int, dict] = {}
    for r in rows:
        f_map[r["equipo_id"]] = {k: r[k] for k in _FICHA_KEYS}
    _empty = {k: None for k in _FICHA_KEYS}
    return {eid: f_map.get(eid) or dict(_empty) for eid in equipo_ids}


def attach_ficha(conn, equipos: list[dict]) -> list[dict]:
    """Agrega la ficha textual (descripcion, notas, keywords, enriquecimiento
    extra). Las specs estructuradas viven en `equipo_specs` y se atachan
    vía `attach_specs_estructuradas`.

    Post-Fase F: montura/formato/resolucion/peso/dimensiones/alimentacion
    fueron droppeadas — esos campos son specs en equipo_specs.
    Post-Fase E: specs_json y raw_json fueron droppeados.
    """
    if not equipos:
        return equipos
    ids = [e["id"] for e in equipos]
    query = query_ficha_batch(ids)
    cur = conn.cursor()
    cur.execute(*query)
    ficha_map = shape_ficha_rows(cur.fetchall(), ids)
    cur.close()
    for e in equipos:
        e["ficha"] = ficha_map.get(e["id"])
    return equipos


def attach_specs_destacados(conn, equipos: list[dict], rows_by_equipo: dict | None = None) -> list[dict]:
    """Agrega `specs_destacados` a cada equipo: lista [{label, value}] de las
    specs con sd.favorito=true en spec_definitions.

    `rows_by_equipo`: resultado ya calculado de `get_equipo_specs_rows` (mismo
    JOIN que pide `attach_specs_estructuradas`) — pasalo si ya lo pediste vos,
    para no ejecutar el mismo query dos veces en la misma carga de catálogo."""
    if not equipos:
        return equipos
    from services.spec_render import render_spec_value
    from services.specs import get_equipo_specs_rows

    ids = [e["id"] for e in equipos]
    if rows_by_equipo is None:
        rows_by_equipo = get_equipo_specs_rows(conn, ids)

    dest_map: dict[int, list[dict]] = {e["id"]: [] for e in equipos}
    for eid in ids:
        # get_equipo_specs_rows ordena por (equipo_id, spec_def_id) — lo
        # reordenamos acá por (prioridad, label), el orden real de esta
        # pantalla (y el que decide qué gana un empate de label más abajo).
        rows = sorted(rows_by_equipo.get(eid, []), key=lambda r: (r["prioridad"], r["label"]))
        seen: set[str] = set()
        for r in rows:
            if not r["en_card"]:
                continue
            # Para destacadas de tipo bool, solo emitir cuando el valor es
            # "Sí"/true. Una spec "Macro: No" no aporta como quick fact en
            # la card — destacar solo cuando el lente ES macro, no cuando no lo es.
            if r["tipo"] == "bool" and str(r["value"]).strip().lower() not in (
                "sí", "si", "yes", "true", "1"
            ):
                continue
            key = r["label"]
            if key in seen:
                continue
            seen.add(key)
            # Para bool, el value queda vacío — el frontend muestra solo el
            # label como badge (ej. "MACRO" en lugar de "MACRO Sí").
            # El resto pasa por el renderer canónico (mismo que el nombre
            # público) → "[24, 70]" mm → "24-70 mm", "[2.8]" f/ → "f/2.8".
            value = "" if r["tipo"] == "bool" else render_spec_value(
                r["value"], r["tipo"], r["unidad"]
            )
            dest_map[eid].append({"label": r["label"], "value": value})

    for e in equipos:
        e["specs_destacados"] = dest_map[e["id"]]
    return equipos


def attach_specs_estructuradas(conn, equipos: list[dict], rows_by_equipo: dict | None = None) -> list[dict]:
    """Agrega `specs` (dict) a cada equipo con TODAS las specs estructuradas
    desde equipo_specs JOIN spec_definitions JOIN categoria_spec_templates.

    Shape: {spec_key: {label, value, tipo, unidad, prioridad, en_card,
    destacado}}. El catálogo público lee esto en vez de las columnas
    legacy (montura/formato/specs_json) de equipo_fichas.

    Solo incluye specs cuyo `spec_def` esté asignado al template de
    alguna categoría del equipo (descartando orfanos cross-cat).
    Flags y prioridad vienen de spec_definitions (sd), no de categoria_spec_templates.

    `rows_by_equipo`: resultado ya calculado de `get_equipo_specs_rows` (mismo
    JOIN que pide `attach_specs_destacados`) — pasalo si ya lo pediste vos,
    para no ejecutar el mismo query dos veces en la misma carga de catálogo.
    """
    if not equipos:
        return equipos
    from services.spec_render import render_spec_value, _is_empty_value
    from services.specs import get_equipo_specs_rows

    ids = [e["id"] for e in equipos]
    if rows_by_equipo is None:
        rows_by_equipo = get_equipo_specs_rows(conn, ids)

    _BOOL_FALSE = frozenset({"false", "no", "0", "n", "falso", "off", "disabled"})

    specs_map: dict[int, dict[str, dict]] = {e["id"]: {} for e in equipos}
    for eid in ids:
        for r in rows_by_equipo.get(eid, []):
            key = r["spec_key"]
            if key in specs_map[eid]:
                continue  # dedup: get_equipo_specs_rows ya se quedó con el de mayor prioridad
            raw_val: str | None = r["value"]
            # Omitir specs efectivamente vacías o bool-false: no aportan en la ficha.
            if _is_empty_value(raw_val):
                continue
            if r["tipo"] == "bool" and str(raw_val).lower().strip() in _BOOL_FALSE:
                continue
            value_display = render_spec_value(raw_val, r["tipo"], r["unidad"])
            if not value_display:
                continue
            specs_map[eid][key] = {
                "label": r["label"],
                # `value` queda CRUDO (lo usan los filtros públicos por specsRaw).
                # `value_display` es el render canónico (mismo que el nombre
                # público) para mostrar en la ficha — "[24,70]" mm → "24-70 mm".
                "value": raw_val,
                "value_display": value_display,
                "tipo": r["tipo"],
                "unidad": r["unidad"],
                "prioridad": r["prioridad"],
                "en_card": bool(r["en_card"]),
                "en_filtros": bool(r["en_filtros"]),
                "destacado": bool(r["destacado"]),
            }
    for e in equipos:
        e["specs"] = specs_map[e["id"]]
    return equipos
