"""Gate de ESCRITURA del motor de reservas — la última línea contra el overbooking.

`validar_stock` es el chequeo que corre al crear/confirmar un pedido. Movido
VERBATIM desde `routes/alquileres._check_stock` (issue #501, Fase 1, Paso 4),
SQL byte-idéntico → move sin cambio de conducta.

⚠️ NÚCLEO SAGRADO. Invariantes que este paso NO toca:
  - El `SELECT ... FOR UPDATE` (lock pesimista de la fila del equipo) queda en
    esta función con el MISMO texto SQL — no se factoriza a un helper, para que
    ningún refactor pueda "perder" el lock por accidente.
  - El lock y la transacción son del CALLER: `validar_stock` recibe `conn` y solo
    emite SELECTs; NUNCA llama commit/rollback/get_db/close. El lock vive hasta
    que el caller (update_pedido / crear_reserva_estudio) commitea, en su misma
    sesión → mover el código de archivo no cambia el alcance ni la duración del
    lock (es propiedad de la conexión+transacción, no del módulo).
"""
from reservas.semantics import (
    consolidar_items_por_equipo,
    get_buffer_horas,
    rango_con_buffer,
    reservado_directo,
    reservado_via_kit,
    unidades_en_mantenimiento,
)


def validar_stock(conn, pedido_id: int, fecha_desde: str, fecha_hasta: str) -> list[str]:
    """Devuelve lista de nombres de equipos sin stock suficiente para el rango dado.

    Usa SELECT ... FOR UPDATE en equipos para evitar race conditions de concurrencia.

    Si el pedido tiene varios items del MISMO equipo (raro pero posible si el
    frontend tiene un bug o si se usa la API directamente), suma las cantidades
    antes de validar — sino la validación pasaría con falsa negativa. Issue #102.

    Para cada equipo del pedido, suma el stock reservado por TODOS los pedidos
    activos en el rango, contando:
      (a) `alquiler_items` que reserven directamente ese equipo, +
      (b) `alquiler_items` de OTROS equipos que sean kits y tengan a este
          equipo como componente (cantidad ponderada por kc.cantidad).
    Sin (b) un kit no chequearía la disponibilidad de sus componentes y dos
    pedidos podían quedar confirmados sobre la misma unidad — uno vía kit y
    otro directo. `calcular_disponibilidad` ya sumaba (b); acá lo igualamos.

    Además, expande los items del pedido para chequear también sus
    componentes (si un item es un kit, exigimos stock para cada componente
    multiplicando por su cantidad en el kit).
    """
    items = conn.execute("""
        SELECT pi.equipo_id, pi.cantidad, e.nombre, e.cantidad AS stock_total
        FROM alquiler_items pi
        JOIN equipos e ON e.id = pi.equipo_id
        WHERE pi.pedido_id = ?
    """, (pedido_id,)).fetchall()

    # Expandimos kits: cada item del pedido aporta demanda al equipo directo
    # y también a cada componente del kit (cantidad ponderada).
    expanded: list[dict] = [dict(r) for r in items]
    for r in items:
        comps = conn.execute("""
            SELECT kc.componente_id, kc.cantidad AS kc_cant,
                   e.nombre, e.cantidad AS stock_total
            FROM kit_componentes kc
            JOIN equipos e ON e.id = kc.componente_id
            WHERE kc.equipo_id = ?
        """, (r["equipo_id"],)).fetchall()
        for c in comps:
            expanded.append({
                "equipo_id": c["componente_id"],
                "cantidad": r["cantidad"] * c["kc_cant"],
                "nombre": c["nombre"],
                "stock_total": c["stock_total"],
            })

    consolidated = consolidar_items_por_equipo(expanded)

    # Buffer entre alquileres: expandimos el rango para exigir gap. Mantenimiento
    # usa el rango original (ventana exacta).
    buffer_horas = get_buffer_horas(conn)
    fd_buf, fh_buf = rango_con_buffer(fecha_desde, fecha_hasta, buffer_horas)

    problemas = []
    for it in consolidated.values():
        # Lock la fila de equipo durante el chequeo para evitar race conditions.
        # SELECT ... FOR UPDATE evita que otra transacción concurrente lea el stock
        # mientras estamos validando.
        lock_result = conn.execute(
            "SELECT cantidad FROM equipos WHERE id = ? FOR UPDATE",
            (it["equipo_id"],)
        ).fetchone()

        if not lock_result:
            problemas.append(f"{it['nombre']} (equipo no encontrado)")
            continue

        stock_total = lock_result["cantidad"]

        # (a) Reservas directas — items que apuntan a este equipo.
        reservado_dir = reservado_directo(conn, it["equipo_id"], pedido_id, fh_buf, fd_buf)

        # (b) Reservas vía kits — items que reservan un kit que tiene a este
        # equipo como componente (cantidad ponderada por kc.cantidad).
        reservado_kit = reservado_via_kit(conn, it["equipo_id"], pedido_id, fh_buf, fd_buf)

        # (c) Unidades fuera de servicio por mantenimiento (rango original).
        en_mantenimiento = unidades_en_mantenimiento(
            conn, it["equipo_id"], fecha_desde, fecha_hasta
        )

        reservado = reservado_dir + reservado_kit + en_mantenimiento
        disponible = stock_total - reservado
        if disponible < it["cantidad"]:
            problemas.append(
                f"{it['nombre']} (necesitás {it['cantidad']}, disponible: {max(0, disponible)})"
            )
    return problemas
