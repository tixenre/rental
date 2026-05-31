"""Primitivas semánticas del motor de reservas (compartidas lectura + gate).

Movidas verbatim desde `routes/alquileres.py` (issue #501, Fase 1, Paso 2). El
SQL es byte-idéntico al original: este paso es un MOVE puro, sin cambio de
conducta. El lock `FOR UPDATE` y la transacción NO viven acá — son del gate.

Todos los valores van como bound params (`?`); el único token interpolado en SQL
es la constante interna `ESTADOS_RESERVADO`.
"""
import datetime
import threading
import time

from database import to_datetime

from reservas.estados import ESTADOS_RESERVADO


# ── Cache del buffer global ──────────────────────────────────────────────────
# `buffer_horas_alquiler` (gap de prep entre alquileres) se lee en CADA chequeo
# de disponibilidad y en CADA confirmación, pero cambia rarísimo (lo setea el
# admin, ~1 vez/mes). Lo cacheamos a nivel proceso para no pegarle a
# `app_settings` en cada request:
#   · Invalidación explícita: el writer de settings llama
#     `invalidate_buffer_cache()` al cambiarlo → reflejo INSTANTÁNEO. Prod corre
#     un solo worker uvicorn → la invalidación es 100% efectiva, cero staleness.
#   · TTL de red de seguridad: si algún día hay multi-worker/réplica, cada
#     proceso recarga solo a los `_BUFFER_TTL_SEG`. El buffer es un gap de prep,
#     NO entra en el conteo de stock → un valor viejo por segundos nunca puede
#     causar overbooking (a lo sumo un gap de prep levemente distinto).
_BUFFER_TTL_SEG = 60.0
_buffer_lock = threading.Lock()
_buffer_valor: int | None = None
_buffer_expira_en: float = 0.0


def _leer_buffer_db(conn) -> int:
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?", ("buffer_horas_alquiler",)
    ).fetchone()
    if not row:
        return 0
    try:
        return max(0, int(row["value"]))
    except (ValueError, TypeError):
        return 0


def get_buffer_horas(conn) -> int:
    """Horas de prep/revisión exigidas entre alquileres (setting global, cacheado).

    Devuelve el valor cacheado mientras esté fresco; recarga de `app_settings`
    en el primer acceso, tras un cambio (vía `invalidate_buffer_cache`) o cuando
    vence el TTL. Doble-check con lock: aunque varios threads colisionen en el
    miss, solo uno pega a la DB."""
    global _buffer_valor, _buffer_expira_en
    valor = _buffer_valor
    if valor is not None and time.monotonic() < _buffer_expira_en:
        return valor
    with _buffer_lock:
        if _buffer_valor is not None and time.monotonic() < _buffer_expira_en:
            return _buffer_valor
        _buffer_valor = _leer_buffer_db(conn)
        _buffer_expira_en = time.monotonic() + _BUFFER_TTL_SEG
        return _buffer_valor


def invalidate_buffer_cache() -> None:
    """Descarta el buffer cacheado → la próxima lectura va a la DB. La llama el
    writer de settings al cambiar `buffer_horas_alquiler`; los tests la corren
    entre casos (fixture autouse) para no arrastrar valores entre escenarios."""
    global _buffer_valor, _buffer_expira_en
    with _buffer_lock:
        _buffer_valor = None
        _buffer_expira_en = 0.0


def rango_con_buffer(fecha_desde, fecha_hasta, buffer_horas: int):
    """Expande [desde, hasta] en `buffer_horas` por cada lado. Expandir el
    rango nuevo equivale a exigir `buffer_horas` de gap contra los alquileres
    existentes (el overlap es simétrico). Devuelve datetimes ISO completos
    (con hora) para que el overlap respete la hora de retiro/devolución —no se
    trunca a día.

    Acepta str ISO o datetime (las columnas son TIMESTAMP)."""
    if buffer_horas <= 0:
        return fecha_desde, fecha_hasta
    try:
        d0 = to_datetime(fecha_desde) - datetime.timedelta(hours=buffer_horas)
        d1 = to_datetime(fecha_hasta) + datetime.timedelta(hours=buffer_horas)
        return d0.isoformat(), d1.isoformat()
    except (ValueError, TypeError, AttributeError):
        return fecha_desde, fecha_hasta


def unidades_en_mantenimiento(conn, equipo_id: int, fecha_desde: str, fecha_hasta: str) -> int:
    """Unidades del equipo fuera de servicio por mantenimiento en el rango.

    Una entrada con bloquea_stock=TRUE saca `cantidad` unidades durante
    [fecha, fecha_hasta]. El overlap usa la misma convención half-open que
    los alquileres. El buffer NO aplica acá (la ventana de mantenimiento es
    exacta)."""
    row = conn.execute("""
        SELECT COALESCE(SUM(cantidad), 0)
        FROM equipo_mantenimiento
        WHERE equipo_id = ?
          AND bloquea_stock = TRUE
          AND fecha < ?
          AND COALESCE(fecha_hasta, fecha) > ?
    """, (equipo_id, fecha_hasta, fecha_desde)).fetchone()
    return int((row[0] if row else 0) or 0)


def consolidar_items_por_equipo(items) -> dict:
    """Consolida items del mismo equipo sumando cantidades.

    Si un pedido tiene 2 items con equipo_id=42 (cantidad=2 cada uno),
    necesitamos validar 4 vs stock, no 2 cada uno por separado. Sino
    pasaría la validación con falsa negativa (cada iteración chequea
    2 < stock sin sumar el otro item del mismo equipo).

    Issue #102 — bug latente cuando el frontend permite items duplicados
    o si se usa la API directamente.

    Acepta iterable de filas con keys: equipo_id, cantidad, nombre, stock_total.
    Devuelve dict[equipo_id, {equipo_id, cantidad_total, nombre, stock_total}].
    """
    out: dict[int, dict] = {}
    for it in items:
        eq_id = it["equipo_id"]
        if eq_id not in out:
            out[eq_id] = {
                "equipo_id": eq_id,
                "cantidad": 0,
                "nombre": it["nombre"],
                "stock_total": it["stock_total"],
            }
        out[eq_id]["cantidad"] += it["cantidad"]
    return out


def componentes_de(conn, equipo_ids=None) -> dict:
    """Componentes (1 nivel) de cada equipo compuesto:
    `{equipo_id: [(componente_id, cantidad), ...]}`.

    Si `equipo_ids` se pasa, filtra a esos equipos; si no, trae todos. NO filtra
    por tipo ni por `esencial` — espeja la expansión del gate (`validar_stock`),
    que toma todos los `kit_componentes`. El best-effort (esencial=false) lo
    introduce C2; la recursión (componente que es a su vez compuesto), C4.
    """
    if equipo_ids is not None:
        ids = list(equipo_ids)
        if not ids:
            return {}
        ph = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"SELECT equipo_id, componente_id, cantidad FROM kit_componentes "
            f"WHERE equipo_id IN ({ph})",
            tuple(ids),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT equipo_id, componente_id, cantidad FROM kit_componentes"
        ).fetchall()
    out: dict[int, list] = {}
    for r in rows:
        out.setdefault(r["equipo_id"], []).append((r["componente_id"], r["cantidad"]))
    return out


def expandir_demanda(conn, items: dict) -> dict:
    """Expande `items` ({equipo_id: cantidad}) a demanda consolidada por equipo
    ({equipo_id: demanda}), 1 nivel.

    Espeja EXACTAMENTE la expansión del gate (`validar_stock`): cada item aporta
    su demanda propia + la de cada componente (cantidad ponderada por la del kit),
    sumando si varios items comparten un equipo. Fuente única para que la LECTURA
    (catálogo/calendario) exija la misma demanda que el gate de escritura — así no
    pueden divergir. La unificación física con el gate se hace en C4.
    """
    comps_by = componentes_de(conn, items.keys())
    demanda: dict[int, int] = {}
    for eid, qty in items.items():
        demanda[eid] = demanda.get(eid, 0) + qty
        for (cid, cqty) in comps_by.get(eid, []):
            demanda[cid] = demanda.get(cid, 0) + qty * cqty
    return demanda


def reservado_directo(conn, equipo_id: int, excl_pedido_id: int, fh_buf, fd_buf) -> int:
    """Unidades de `equipo_id` reservadas DIRECTAMENTE (items que lo apuntan) por
    otros pedidos activos que se pisan con el rango ya bufferizado [fd_buf, fh_buf].

    Fuente única de la subquery de reserva directa: la comparten el gate
    (`_check_stock`) y el chequeo hipotético del portal (`_check_stock_hipotetico`)
    con SQL idéntico. Todos los valores van como bound params; el único token
    interpolado es la constante interna ESTADOS_RESERVADO.
    """
    return conn.execute(f"""
        SELECT COALESCE(SUM(pi2.cantidad), 0)
        FROM alquiler_items pi2
        JOIN alquileres p ON p.id = pi2.pedido_id
        WHERE pi2.equipo_id = ?
          AND p.id != ?
          AND p.estado IN {ESTADOS_RESERVADO}
          AND p.fecha_desde < ?
          AND p.fecha_hasta > ?
    """, (equipo_id, excl_pedido_id, fh_buf, fd_buf)).fetchone()[0]


def reservado_via_kit(conn, equipo_id: int, excl_pedido_id: int, fh_buf, fd_buf) -> int:
    """Unidades de `equipo_id` reservadas INDIRECTAMENTE: otros pedidos activos
    reservan un kit que tiene a `equipo_id` como componente (cantidad ponderada
    por kc.cantidad), pisándose con el rango bufferizado [fd_buf, fh_buf].

    Sin esto, dos pedidos podrían confirmarse sobre la misma unidad — uno vía kit
    y otro directo. Mismas garantías de parametrización que `reservado_directo`.
    """
    return conn.execute(f"""
        SELECT COALESCE(SUM(pi2.cantidad * kc.cantidad), 0)
        FROM alquiler_items pi2
        JOIN alquileres p ON p.id = pi2.pedido_id
        JOIN kit_componentes kc ON kc.equipo_id = pi2.equipo_id
        WHERE kc.componente_id = ?
          AND p.id != ?
          AND p.estado IN {ESTADOS_RESERVADO}
          AND p.fecha_desde < ?
          AND p.fecha_hasta > ?
    """, (equipo_id, excl_pedido_id, fh_buf, fd_buf)).fetchone()[0]
