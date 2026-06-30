"""services/catalogo/proyeccion.py — ensamblador del payload de catálogo.

Orquesta los motores existentes (attach_* de database/, reservas, contenido,
precios) para producir el dict del equipo-de-display que /api/equipos y
/api/equipos/{id} sirven al front. No hace cálculos propios: solo llama
a los motores canónicos y los ensambla.

SUPERFICIE:
    proyectar_lista   — lista paginada (list_equipos)
    proyectar_uno     — detalle de un equipo (get_equipo)
    proyectar_seed    — seed liviano para SSR/LCP (_get_initial_catalog de main.py)

DEPENDENCIAS CANÓNICAS (fuente única de cada motor):
    - stock/disponibilidad → reservas.calcular_disponibilidad (GLOBAL FIXED COST)
    - kit/contenido        → services.contenido
    - precios combo        → services.precios.precios_combo_batch / precio_combo
    - attach_*             → database/equipos.py (tags, kit, categorías, ficha, specs)
    - busqueda/ranking     → pred.score / MARCA_SUBQUERY

NO TOCA: reservas/ (solo lee), kit_componentes directamente,
         create_pedido_retry, dataio/. Ver CLAUDE.md.
"""
from database import (
    row_to_dict,
    attach_tags,
    attach_kit,
    attach_categorias,
    attach_ficha,
    attach_specs_destacados,
    attach_specs_estructuradas,
    MARCA_SUBQUERY,
)
from reservas import calcular_disponibilidad
from reservas.disponibilidad import _derivar_compuestos
from reservas.semantics import componentes_de
from services.contenido import contenido_de


# ── Constantes de ordenamiento (espejo de routes/equipos/core.py) ─────────────

_RANKING = "e.relevancia_manual ASC, e.popularidad_score DESC, e.nombre ASC"

# Precio efectivo por jornada para ordenar: combo → suma de componentes;
# resto → precio propio. Correlado por e.id (no evalúa para no-combos).
_PRECIO_EFECTIVO = (
    "CASE WHEN e.tipo = 'combo' THEN COALESCE(("
    " SELECT ROUND(SUM(ce.precio_jornada * kc.cantidad"
    " * (1 - COALESCE(kc.descuento_pct, 0) / 100.0)))"
    " FROM kit_componentes kc JOIN equipos ce ON ce.id = kc.componente_id"
    " WHERE kc.equipo_id = e.id AND ce.eliminado_at IS NULL"
    "), 0) ELSE e.precio_jornada END"
)


# ── Helpers privados ──────────────────────────────────────────────────────────


def _stock_sin_reservas(conn) -> dict:
    """Stock teórico de kits/combos derivado solo del stock de componentes, sin
    descontar ninguna reserva. Detecta kits imposibles de armar (componentes <
    cantidad requerida) independientemente de las fechas seleccionadas.

    Move-verbatim desde routes/equipos/core.py. Optimizarlo = futuro PR.
    """
    raw = {
        r["id"]: r["cantidad"]
        for r in conn.execute(
            "SELECT id, cantidad FROM equipos WHERE eliminado_at IS NULL"
        ).fetchall()
    }
    return _derivar_compuestos(raw, componentes_de(conn))


def _attach_disponibilidad(conn, equipos: list, desde: str, hasta: str) -> list:
    """Inyecta el campo `disponible` por equipo.

    GLOBAL FIXED COST: `calcular_disponibilidad` corre UNA sola vez para
    TODOS los equipos del catálogo (no per-equipo/per-página). Costo fijo
    independiente del tamaño del lote. Ver reservas/CLAUDE.md.

    Indexa por str(equipo_id) — es como calcular_disponibilidad almacena
    el resultado (bug #619: no cambiar esta clave sin actualizar el motor).
    """
    disp = calcular_disponibilidad(conn, desde, hasta)
    for eq in equipos:
        eid = eq["id"]
        eq["disponible"] = disp.get(str(eid), eq.get("cantidad", 0))
    return equipos


def _build_order_clause(sort: str | None, pred) -> str:
    """Construye la cláusula ORDER BY según el sort y el predicado de búsqueda."""
    use_score = bool(pred and pred.activo) and sort in (None, "ranking")
    if use_score:
        return f"ORDER BY _score DESC, {_RANKING}"
    return {
        None:          f"ORDER BY {_RANKING}",
        "ranking":     f"ORDER BY {_RANKING}",
        "nombre":      "ORDER BY COALESCE(e.nombre_publico, e.nombre) ASC",
        "precio_asc":  f"ORDER BY ({_PRECIO_EFECTIVO}) ASC NULLS LAST, e.nombre ASC",
        "precio_desc": f"ORDER BY ({_PRECIO_EFECTIVO}) DESC NULLS LAST, e.nombre ASC",
        "id":          "ORDER BY e.id ASC",
    }.get(sort, f"ORDER BY {_RANKING}")


# ── Proyectores públicos ──────────────────────────────────────────────────────


def proyectar_lista(
    conn,
    *,
    filtro_sql: str,
    filtro_params: list,
    sort: str | None = None,
    pred=None,
    page: int = 1,
    per_page: int = 200,
    desde: str | None = None,
    hasta: str | None = None,
    is_admin: bool = False,
) -> dict:
    """Ensambla la lista paginada de equipos para el catálogo.

    Recibe el filtro SQL ya construido por el route (`FROM equipos e WHERE …`)
    y produce el payload completo que /api/equipos devuelve: COUNT, SELECT,
    attach_*, precios combo, filtro de stock, disponibilidad.

    Args:
        conn:           Conexión activa (PGConnection).
        filtro_sql:     Cláusula "FROM equipos e WHERE …" con marcadores %s.
        filtro_params:  Params ligados a filtro_sql.
        sort:           Criterio de ordenamiento (ranking|nombre|precio_asc|…).
        pred:           Predicado de búsqueda fuzzy (busqueda.construir) o None.
        page:           Número de página (1-based).
        per_page:       Items por página.
        desde, hasta:   Fechas YYYY-MM-DD para disponibilidad (ambas o ninguna).
        is_admin:       Si True, incluye equipos no visibles y salta el filtro
                        de stock teórico.

    Returns:
        {"total": N, "page": P, "per_page": PP, "items": [...]}
    """
    offset = (page - 1) * per_page
    order_clause = _build_order_clause(sort, pred)
    use_score = bool(pred and pred.activo) and sort in (None, "ranking")

    total = conn.execute(f"SELECT COUNT(*) {filtro_sql}", filtro_params).fetchone()[0]

    if use_score:
        select_cols = f"e.*, {MARCA_SUBQUERY}, ({pred.score}) AS _score"
        select_params = pred.score_params + filtro_params + [per_page, offset]
    else:
        select_cols = f"e.*, {MARCA_SUBQUERY}"
        select_params = filtro_params + [per_page, offset]

    rows = conn.execute(
        f"SELECT {select_cols} {filtro_sql} {order_clause} LIMIT %s OFFSET %s",
        select_params,
    ).fetchall()
    equipos = [row_to_dict(r) for r in rows]
    for e in equipos:
        e.pop("_score", None)

    # Attach brand object (id, nombre, logo_url) — batched.
    brand_ids = {e["brand_id"] for e in equipos if e.get("brand_id")}
    brands_map: dict = {}
    if brand_ids:
        placeholders = ",".join(["%s"] * len(brand_ids))
        brand_rows = conn.execute(
            f"SELECT id, nombre, logo_url FROM marcas WHERE id IN ({placeholders})",
            tuple(brand_ids),
        ).fetchall()
        brands_map = {r["id"]: row_to_dict(r) for r in brand_rows}
    for equipo in equipos:
        bid = equipo.get("brand_id")
        equipo["brand"] = brands_map.get(bid) if bid else None

    equipos = attach_tags(conn, equipos)
    equipos = attach_kit(conn, equipos)
    equipos = attach_categorias(conn, equipos)
    equipos = attach_ficha(conn, equipos)
    equipos = attach_specs_estructuradas(conn, equipos)
    equipos = attach_specs_destacados(conn, equipos)

    # Combos: precio efectivo (derivado de componentes), no el crudo de la tabla.
    combo_ids = [e["id"] for e in equipos if e.get("tipo") == "combo"]
    if combo_ids:
        from services.precios import precios_combo_batch
        efectivos = precios_combo_batch(conn, combo_ids)
        for e in equipos:
            if e.get("tipo") == "combo":
                e["precio_jornada"] = efectivos.get(e["id"], 0)

    # Filtrar kits/combos que no pueden armarse ni una vez (stock insuficiente).
    # Solo catálogo público (admin los ve para poder corregirlos).
    if not is_admin:
        stock_teo = _stock_sin_reservas(conn)
        equipos = [
            e for e in equipos
            if not e.get("kit")
            or stock_teo.get(str(e["id"]), 0) > 0
        ]

    if desde and hasta:
        equipos = _attach_disponibilidad(conn, equipos, desde, hasta)

    return {"total": total, "page": page, "per_page": per_page, "items": equipos}


def proyectar_uno(conn, equipo_id: int) -> dict | None:
    """Ensambla el detalle de un equipo para /api/equipos/{id}.

    Retorna None si el equipo no existe. El route se encarga del 404.

    Args:
        conn:       Conexión activa (PGConnection).
        equipo_id:  ID numérico del equipo.

    Returns:
        Dict con el equipo completo (incluyendo fotos y kit) o None.
    """
    row = conn.execute(
        f"SELECT *, {MARCA_SUBQUERY} FROM equipos e WHERE id = %s", (equipo_id,)
    ).fetchone()
    if not row:
        return None

    equipo = attach_tags(conn, [row_to_dict(row)])[0]
    equipo = attach_ficha(conn, [equipo])[0]
    equipo = attach_categorias(conn, [equipo])[0]
    equipo = attach_specs_estructuradas(conn, [equipo])[0]

    # Componentes vía la puerta única (services.contenido). solo_activos=False:
    # preserva el comportamiento de la ficha (no filtraba soft-deleted).
    equipo["kit"] = [{
        "componente_id": c["componente_id"],
        "cantidad":      c["cantidad"],
        "descuento_pct": c["descuento_pct"],
        "esencial":      c["esencial"],
        "nombre":        c["nombre"],
        "marca":         c["marca"],
        "foto_url":      c["foto_url"],
    } for c in contenido_de(conn, equipo_id, solo_activos=False)]

    # Galería multi-foto (#125): principal primero.
    fotos = conn.execute(
        "SELECT url, es_principal FROM equipo_fotos "
        "WHERE equipo_id = %s AND url IS NOT NULL AND url <> '' "
        "ORDER BY es_principal DESC, orden ASC, id ASC",
        (equipo_id,),
    ).fetchall()
    equipo["fotos"] = [
        {"url": r["url"], "es_principal": bool(r["es_principal"])} for r in fotos
    ]

    # Combo: precio efectivo (derivado de componentes), igual en todas las superficies.
    if equipo.get("tipo") == "combo":
        from services.precios import precio_combo
        equipo["precio_jornada"] = precio_combo(conn, equipo_id)

    return equipo


def proyectar_seed(conn) -> dict:
    """Serializa el seed liviano para el script __INITIAL__ del catálogo (SSR/LCP).

    Subconjunto de proyectar_lista sin attach_*, suficiente para el primer
    render de las cards sin round-trip. El front (backendToEquipment) tolera
    campos ausentes (etiquetas/kit/specs → arrays vacíos o None).

    Emite los mismos campos que _get_initial_catalog de main.py (move-verbatim).
    """
    rows = conn.execute(f"""
        SELECT
            e.id, e.nombre, e.nombre_publico, e.modelo,
            e.foto_url, e.foto_url_sm, e.foto_url_thumb,
            e.foto_url_avif, e.foto_url_sm_avif, e.foto_url_thumb_avif, e.foto_lqip,
            e.precio_jornada, e.precio_usd, e.cantidad,
            e.estado, e.visible_catalogo, e.relevancia_manual,
            e.popularidad_score, e.destacado, e.tipo,
            {MARCA_SUBQUERY}
        FROM equipos e
        WHERE e.visible_catalogo = 1
          AND e.estado != 'fuera_servicio'
          AND e.eliminado_at IS NULL
          AND e.es_recurso_interno = FALSE
        ORDER BY e.relevancia_manual ASC, e.popularidad_score DESC, e.nombre ASC
        LIMIT 500
    """).fetchall()

    items = []
    for row in rows:
        item = dict(row)
        item.setdefault("etiquetas", [])
        item.setdefault("kit", [])
        items.append(item)

    cats = conn.execute(
        "SELECT id, nombre, COALESCE(total, 0) AS total, prioridad, parent_id "
        "FROM categorias ORDER BY COALESCE(prioridad, 999), nombre"
    ).fetchall()

    estudio_fotos = conn.execute(
        "SELECT url, url_sm, url_avif, url_sm_avif, es_principal, orden "
        "FROM estudio_fotos WHERE estudio_id = 1 "
        "ORDER BY es_principal DESC, orden ASC LIMIT 5"
    ).fetchall()

    return {
        "equipos": {"total": len(items), "items": items},
        "categorias": [dict(c) for c in cats],
        "estudio": {"fotos": [dict(f) for f in estudio_fotos]},
    }
