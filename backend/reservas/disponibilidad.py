"""Camino de LECTURA del motor de reservas: disponibilidad (catálogo/calendario).

Funciones puras (reciben `conn`, sin abrir/cerrar transacción y SIN `FOR UPDATE`)
movidas verbatim desde `routes/alquileres.py` (issue #501, Fase 1, Paso 3). SQL
byte-idéntico → move sin cambio de conducta.

Comparten la MISMA semántica que el gate de escritura (reservas directas + vía
kit + mantenimiento + buffer), pero la lectura NUNCA toma locks: es para mostrar
disponibilidad, no para reservar. El gate (`_check_stock`) vive aparte.
"""
import datetime

from database import to_datetime

from reservas.estados import ESTADOS_RESERVADO
from reservas.semantics import get_buffer_horas, rango_con_buffer


def calcular_disponibilidad(conn, fecha_desde, fecha_hasta, exclude_pedido_id=None) -> dict:
    """Unidades libres por equipo en [fecha_desde, fecha_hasta], descontando
    reservas directas + vía kit + mantenimiento, con el buffer global aplicado.

    Devuelve `{str(equipo_id): unidades_libres}`. Solo LECTURA — no lockea.
    `exclude_pedido_id` (o None) excluye el propio pedido al editar.
    """
    # exclude_pedido_id como NULL en SQL → (NULL IS NULL) = TRUE → no filtra nada
    excl = exclude_pedido_id  # None o int, ambos seguros como parámetro

    # Buffer: expandimos el rango consultado para exigir gap entre alquileres.
    buffer_horas = get_buffer_horas(conn)
    fd_buf, fh_buf = rango_con_buffer(fecha_desde, fecha_hasta, buffer_horas)

    directas = conn.execute(f"""
        SELECT e.id, e.cantidad,
               COALESCE(SUM(CASE
                 WHEN p.estado IN {ESTADOS_RESERVADO}
                      AND p.fecha_desde < ?
                      AND p.fecha_hasta > ?
                      AND (? IS NULL OR p.id != ?)
                 THEN pi.cantidad ELSE 0
               END), 0) AS reservado
        FROM equipos e
        LEFT JOIN alquiler_items pi ON pi.equipo_id = e.id
        LEFT JOIN alquileres p ON p.id = pi.pedido_id
        GROUP BY e.id
    """, (fh_buf, fd_buf, excl, excl)).fetchall()

    reservado = {r["id"]: r["reservado"] for r in directas}
    cantidad  = {r["id"]: r["cantidad"]  for r in directas}

    via_kit = conn.execute(f"""
        SELECT kc.componente_id,
               SUM(pi.cantidad * kc.cantidad) AS extra
        FROM kit_componentes kc
        JOIN alquiler_items pi ON pi.equipo_id = kc.equipo_id
        JOIN alquileres p ON p.id = pi.pedido_id
        WHERE p.estado IN {ESTADOS_RESERVADO}
          AND p.fecha_desde < ?
          AND p.fecha_hasta > ?
          AND (? IS NULL OR p.id != ?)
        GROUP BY kc.componente_id
    """, (fh_buf, fd_buf, excl, excl)).fetchall()

    for r in via_kit:
        reservado[r["componente_id"]] = reservado.get(r["componente_id"], 0) + r["extra"]

    # Mantenimiento que bloquea stock (sin buffer — ventana exacta).
    mant = conn.execute("""
        SELECT equipo_id, COALESCE(SUM(cantidad), 0) AS bloqueado
        FROM equipo_mantenimiento
        WHERE bloquea_stock = TRUE
          AND fecha < ?
          AND COALESCE(fecha_hasta, fecha) > ?
        GROUP BY equipo_id
    """, (fecha_hasta, fecha_desde)).fetchall()
    en_mant = {r["equipo_id"]: r["bloqueado"] for r in mant}

    return {
        str(eid): max(0, cantidad.get(eid, 0)
                      - reservado.get(eid, 0)
                      - en_mant.get(eid, 0))
        for eid in cantidad
    }


def dias_no_disponibles(conn, items: dict[int, int], desde: str, hasta: str) -> list[str]:
    """Días (YYYY-MM-DD) en [desde, hasta] donde algún equipo de `items`
    ({equipo_id: cantidad_requerida}) NO tiene unidades libres suficientes.

    Refleja la MISMA semántica que `calcular_disponibilidad` (reservas directas +
    vía kit + mantenimiento + buffer), evaluada día por día. Fuente para
    bloquear días en el calendario del cliente sin divergir del chequeo real
    que corre al confirmar el pedido.
    """
    if not items:
        return []
    ids = list(items.keys())
    ph = ",".join("?" for _ in ids)

    d_desde = to_datetime(desde)
    d_hasta = to_datetime(hasta)
    if d_desde is None or d_hasta is None or d_hasta < d_desde:
        return []
    buffer_horas = get_buffer_horas(conn)
    buf = datetime.timedelta(hours=buffer_horas)
    # Ventana amplia para traer segmentos relevantes (incluye buffer).
    win_lo = (d_desde - buf).isoformat()
    win_hi = (d_hasta + datetime.timedelta(days=1) + buf).isoformat()

    stock = {
        r["id"]: r["cantidad"]
        for r in conn.execute(
            f"SELECT id, cantidad FROM equipos WHERE id IN ({ph})", ids
        ).fetchall()
    }

    # Segmentos de reserva (directos + vía kit), con su cantidad por equipo.
    segs: dict[int, list[tuple]] = {eid: [] for eid in ids}
    directas = conn.execute(
        f"""
        SELECT pi.equipo_id AS eid, p.fecha_desde AS fd, p.fecha_hasta AS fh, pi.cantidad AS cant
        FROM alquiler_items pi
        JOIN alquileres p ON p.id = pi.pedido_id
        WHERE p.estado IN {ESTADOS_RESERVADO}
          AND pi.equipo_id IN ({ph})
          AND p.fecha_hasta > ? AND p.fecha_desde < ?
        """,
        (*ids, win_lo, win_hi),
    ).fetchall()
    for r in directas:
        segs[r["eid"]].append((to_datetime(r["fd"]), to_datetime(r["fh"]), r["cant"]))

    via_kit = conn.execute(
        f"""
        SELECT kc.componente_id AS eid, p.fecha_desde AS fd, p.fecha_hasta AS fh,
               pi.cantidad * kc.cantidad AS cant
        FROM kit_componentes kc
        JOIN alquiler_items pi ON pi.equipo_id = kc.equipo_id
        JOIN alquileres p ON p.id = pi.pedido_id
        WHERE p.estado IN {ESTADOS_RESERVADO}
          AND kc.componente_id IN ({ph})
          AND p.fecha_hasta > ? AND p.fecha_desde < ?
        """,
        (*ids, win_lo, win_hi),
    ).fetchall()
    for r in via_kit:
        segs.setdefault(r["eid"], []).append((to_datetime(r["fd"]), to_datetime(r["fh"]), r["cant"]))

    # Mantenimiento (sin buffer).
    mant: dict[int, list[tuple]] = {eid: [] for eid in ids}
    mrows = conn.execute(
        f"""
        SELECT equipo_id AS eid, fecha AS fd, COALESCE(fecha_hasta, fecha) AS fh, cantidad AS cant
        FROM equipo_mantenimiento
        WHERE bloquea_stock = TRUE
          AND equipo_id IN ({ph})
          AND COALESCE(fecha_hasta, fecha) > ? AND fecha < ?
        """,
        (*ids, win_lo, win_hi),
    ).fetchall()
    for r in mrows:
        mant.setdefault(r["eid"], []).append((to_datetime(r["fd"]), to_datetime(r["fh"]), r["cant"]))

    return _dias_bloqueados(stock, segs, mant, items, d_desde, d_hasta, buf)


def _dias_bloqueados(stock, segs, mant, items, d_desde, d_hasta, buf) -> list[str]:
    """Cómputo puro: días bloqueados dado stock, segmentos de reserva (con
    buffer) y de mantenimiento (sin buffer) por equipo, ya traídos de la DB.

    Event-based (diff-array) en vez de re-escanear todos los segmentos por cada
    día: O(días + segmentos) por equipo en vez de O(días × segmentos). La
    semántica es IDÉNTICA al loop original — cada segmento aporta su `cantidad`
    a los días que pisa, con el MISMO predicado de overlap half-open:

        día i (= [dia_i, dia_i+1)) lo cubre el segmento si  dia_i < sh' ∧ dia_i+1 > sd'

    donde [sd', sh') es el segmento, expandido por el buffer para reservas
    (sd-buf, sh+buf) y exacto para mantenimiento. Reordenar `sd<hi ∧ sh>lo` con
    `lo=dia_i-buf, hi=dia_i+1+buf` da exactamente esa forma. Los índices de día
    se calculan con aritmética ENTERA de timedelta (`.days`) — nada de división
    float — para que los bordes de medianoche no sufran off-by-one.

    El test diferencial `test_dias_no_disponibles_caracterizacion.py` fija que
    coincide con la implementación vieja sobre cientos de casos aleatorios.
    """
    one = datetime.timedelta(days=1)
    micro = datetime.timedelta(microseconds=1)
    dia0 = d_desde.replace(hour=0, minute=0, second=0, microsecond=0)
    fin0 = d_hasta.replace(hour=0, minute=0, second=0, microsecond=0)
    n = (fin0 - dia0).days + 1
    if n <= 0:
        return []

    def _acumular(diff, sd, sh, c, expandir):
        """Suma `c` al rango de días [i_lo, i_hi] que el segmento cubre, vía
        diff-array (incrementa en i_lo, decrementa en i_hi+1)."""
        if sd is None or sh is None:
            return
        sd2 = sd - buf if expandir else sd
        sh2 = sh + buf if expandir else sh
        # i_lo: menor i con dia_{i+1} > sd2  ⟺ i ≥ floor((sd2-dia0)/día) = .days
        # i_hi: mayor i con dia_i < sh2  ⟺ i = ceil((sh2-dia0)/día)-1 = (sh2-dia0-1µs).days
        i_lo = max(0, (sd2 - dia0).days)
        i_hi = min(n - 1, (sh2 - micro - dia0).days)
        if i_lo <= i_hi:
            diff[i_lo] += c
            diff[i_hi + 1] -= c

    bloqueados: list[str] = []
    # Por equipo: prefix-sum de reservas + mantenimiento por día.
    reservado_por_dia: dict = {}
    for eid in items:
        d_res = [0] * (n + 1)
        d_man = [0] * (n + 1)
        for (sd, sh, c) in segs.get(eid, []):
            _acumular(d_res, sd, sh, c, expandir=True)
        for (sd, sh, c) in mant.get(eid, []):
            _acumular(d_man, sd, sh, c, expandir=False)
        res = [0] * n
        man = [0] * n
        acc_r = acc_m = 0
        for i in range(n):
            acc_r += d_res[i]
            acc_m += d_man[i]
            res[i] = acc_r
            man[i] = acc_m
        reservado_por_dia[eid] = (res, man)

    for i in range(n):
        for eid, qty in items.items():
            res, man = reservado_por_dia[eid]
            disp = stock.get(eid, 0) - res[i] - man[i]
            if disp < max(1, qty):
                bloqueados.append((dia0 + i * one).date().isoformat())
                break
    return bloqueados
