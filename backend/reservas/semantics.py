"""Primitivas semánticas del motor de reservas (compartidas lectura + gate).

Movidas verbatim desde `routes/alquileres.py` (issue #501, Fase 1, Paso 2). El
SQL es byte-idéntico al original: este paso es un MOVE puro, sin cambio de
conducta. El lock `FOR UPDATE` y la transacción NO viven acá — son del gate.

Todos los valores van como bound params (`?`); el único token interpolado en SQL
es la constante interna `ESTADOS_RESERVADO`.
"""
import datetime

from database import to_datetime

from reservas.estados import ESTADOS_RESERVADO


def get_buffer_horas(conn) -> int:
    """Horas de prep/revisión exigidas entre alquileres (setting global)."""
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?", ("buffer_horas_alquiler",)
    ).fetchone()
    if not row:
        return 0
    try:
        return max(0, int(row["value"]))
    except (ValueError, TypeError):
        return 0


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
