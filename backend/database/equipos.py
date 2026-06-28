"""database/equipos.py — enriquecimiento de equipos (#501 Fase 5).

Helpers `attach_*` que, dado un lote de equipos (list[dict]), les adjuntan en vivo
sus tags, kit, categorías, ficha y specs (destacadas + estructuradas). Move-verbatim
desde `database.py`. `attach_kit` deriva el contenido de la puerta única
`services.contenido` (fuente única del "qué incluye").
"""


def attach_tags(conn, equipos: list[dict]) -> list[dict]:
    """Agrega etiquetas a la lista de equipos (ordenadas por `orden`)."""
    if not equipos:
        return equipos

    ids = [e["id"] for e in equipos]
    placeholders = ",".join(["%s"] * len(ids))

    cur = conn.cursor()
    cur.execute(f"""
        SELECT ee.equipo_id, et.nombre, et.prioridad
        FROM equipo_etiquetas ee
        JOIN etiquetas et ON et.id = ee.etiqueta_id
        WHERE ee.equipo_id IN ({placeholders})
        ORDER BY ee.equipo_id, ee.orden
    """, ids)

    rows = cur.fetchall()
    tag_map: dict[int, list] = {e["id"]: [] for e in equipos}

    for r in rows:
        tag_map[r["equipo_id"]].append(r["nombre"])

    for e in equipos:
        e["etiquetas"] = tag_map[e["id"]]

    cur.close()
    return equipos


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
    ids = [e["id"] for e in equipos]
    placeholders = ",".join(["%s"] * len(ids))
    cur = conn.cursor()
    cur.execute(f"""
        SELECT ec.equipo_id, c.id, c.nombre, c.parent_id
        FROM equipo_categorias ec
        JOIN categorias c ON c.id = ec.categoria_id
        WHERE ec.equipo_id IN ({placeholders})
        ORDER BY ec.equipo_id, ec.orden
    """, ids)
    rows = cur.fetchall()
    cat_map: dict[int, list] = {e["id"]: [] for e in equipos}
    for r in rows:
        cat_map[r["equipo_id"]].append({
            "id": r["id"], "nombre": r["nombre"], "parent_id": r["parent_id"],
        })
    for e in equipos:
        e["categorias"] = cat_map[e["id"]]
    cur.close()
    return equipos


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
    placeholders = ",".join(["%s"] * len(ids))
    cur = conn.cursor()
    cur.execute(f"""
        SELECT equipo_id, descripcion, notas,
               keywords_json, nombre_publico_template,
               incluye_json, conectividad_json, compatible_con_json,
               video_url, precio_bh_usd, fuente_url, fuente_titulo,
               enriquecido_at, enriquecido_fuente,
               contenido_incluido_json
        FROM equipo_fichas
        WHERE equipo_id IN ({placeholders})
    """, ids)
    rows = cur.fetchall()
    _ficha_keys = (
        "descripcion", "notas",
        "keywords_json", "nombre_publico_template",
        "incluye_json", "conectividad_json", "compatible_con_json",
        "video_url", "precio_bh_usd", "fuente_url", "fuente_titulo",
        "enriquecido_at", "enriquecido_fuente",
        "contenido_incluido_json",
    )
    f_map: dict[int, dict] = {}
    for r in rows:
        f_map[r["equipo_id"]] = {k: r[k] for k in _ficha_keys}
    _empty = {k: None for k in _ficha_keys}
    for e in equipos:
        e["ficha"] = f_map.get(e["id"]) or dict(_empty)
    cur.close()
    return equipos


def attach_specs_destacados(conn, equipos: list[dict]) -> list[dict]:
    """Agrega `specs_destacados` a cada equipo: lista [{label, value}] de las
    specs con sd.favorito=true en spec_definitions."""
    if not equipos:
        return equipos
    from services.spec_render import render_spec_value
    ids = [e["id"] for e in equipos]
    placeholders = ",".join(["%s"] * len(ids))
    cur = conn.cursor()
    # Para destacadas de tipo bool, solo emitir cuando el valor es "Sí"/true.
    # Una spec "Macro: No" no aporta como quick fact en la card — destacar
    # solo cuando el lente ES macro, no cuando no lo es.
    cur.execute(f"""
        SELECT es.equipo_id, sd.label, sd.tipo, sd.unidad, es.value,
               COALESCE(sd.prioridad, 100) AS prioridad
        FROM equipo_specs es
        JOIN equipo_categorias ec ON ec.equipo_id = es.equipo_id
        JOIN spec_definitions sd ON sd.id = es.spec_def_id
        JOIN categoria_spec_templates t
            ON t.spec_def_id = es.spec_def_id
           AND t.categoria_id = ec.categoria_id
        WHERE COALESCE(sd.favorito, FALSE) = TRUE
          AND es.equipo_id IN ({placeholders})
          AND (
            sd.tipo != 'bool'
            OR LOWER(TRIM(es.value)) IN ('sí', 'si', 'yes', 'true', '1')
          )
        ORDER BY es.equipo_id, COALESCE(sd.prioridad, 100), sd.label
    """, ids)
    rows = cur.fetchall()
    cur.close()

    dest_map: dict[int, list[dict]] = {e["id"]: [] for e in equipos}
    seen: dict[int, set] = {e["id"]: set() for e in equipos}
    for r in rows:
        eid = r["equipo_id"]
        key = r["label"]
        if key not in seen[eid]:
            # Para bool, el value queda vacío — el frontend muestra solo el
            # label como badge (ej. "MACRO" en lugar de "MACRO Sí").
            # El resto pasa por el renderer canónico (mismo que el nombre
            # público) → "[24, 70]" mm → "24-70 mm", "[2.8]" f/ → "f/2.8".
            value = "" if r["tipo"] == "bool" else render_spec_value(
                r["value"], r["tipo"], r["unidad"]
            )
            dest_map[eid].append({"label": r["label"], "value": value})
            seen[eid].add(key)

    for e in equipos:
        e["specs_destacados"] = dest_map[e["id"]]
    return equipos


def attach_specs_estructuradas(conn, equipos: list[dict]) -> list[dict]:
    """Agrega `specs` (dict) a cada equipo con TODAS las specs estructuradas
    desde equipo_specs JOIN spec_definitions JOIN categoria_spec_templates.

    Shape: {spec_key: {label, value, tipo, unidad, prioridad, en_card,
    destacado}}. El catálogo público lee esto en vez de las columnas
    legacy (montura/formato/specs_json) de equipo_fichas.

    Solo incluye specs cuyo `spec_def` esté asignado al template de
    alguna categoría del equipo (descartando orfanos cross-cat).
    Flags y prioridad vienen de spec_definitions (sd), no de categoria_spec_templates.
    """
    if not equipos:
        return equipos
    from services.spec_render import render_spec_value, _is_empty_value
    ids = [e["id"] for e in equipos]
    placeholders = ",".join(["%s"] * len(ids))
    cur = conn.cursor()
    cur.execute(f"""
        SELECT DISTINCT ON (es.equipo_id, sd.id)
            es.equipo_id, sd.spec_key, sd.label, sd.tipo, sd.unidad,
            es.value,
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
    """, ids)
    rows = cur.fetchall()
    cur.close()

    _BOOL_FALSE = frozenset({"false", "no", "0", "n", "falso", "off", "disabled"})

    specs_map: dict[int, dict[str, dict]] = {e["id"]: {} for e in equipos}
    for r in rows:
        eid = r["equipo_id"]
        key = r["spec_key"]
        if key in specs_map[eid]:
            continue  # dedup: mantenemos el de mayor prioridad (DISTINCT ON)
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
