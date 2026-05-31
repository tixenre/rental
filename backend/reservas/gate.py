"""Gate de ESCRITURA del motor de reservas — la última línea contra el overbooking.

`validar_stock` es el chequeo que corre al crear/confirmar un pedido. Originado
como move VERBATIM desde `routes/alquileres._check_stock` (issue #501, Fase 1,
Paso 4). C4 (#635) reescribió SOLO la EXPANSIÓN para que sea recursiva hasta las
hojas (forward + backward), cerrando el overbooking en combos anidados; la
semántica del lock/transacción NO cambió (ver invariantes abajo). La red que fija
"mismo comportamiento donde no hay anidamiento" es el test diferencial
`test_gate_caracterizacion_c4.py`.

⚠️ NÚCLEO SAGRADO. Invariantes que C4 (ni ningún refactor de expansión) toca:
  - El `SELECT ... FOR UPDATE` (lock pesimista de la fila del equipo) queda en
    esta función con el MISMO texto SQL — no se factoriza a un helper, para que
    ningún refactor pueda "perder" el lock por accidente. Los nodos se lockean en
    orden ascendente de id (`ORDER BY id`) — la recursión lockea más filas, así el
    orden total evita deadlocks entre transacciones concurrentes.
  - El lock y la transacción son del CALLER: `validar_stock` recibe `conn` y solo
    emite SELECTs; NUNCA llama commit/rollback/get_db/close. El lock vive hasta
    que el caller (update_pedido / crear_reserva_estudio) commitea, en su misma
    sesión → mover el código de archivo no cambia el alcance ni la duración del
    lock (es propiedad de la conexión+transacción, no del módulo).
"""
from reservas.semantics import (
    expandir_demanda,
    get_buffer_horas,
    parientes_de,
    rango_con_buffer,
    reservado_total,
    unidades_en_mantenimiento,
)


def validar_stock(conn, pedido_id: int, fecha_desde: str, fecha_hasta: str) -> list[str]:
    """Devuelve lista de nombres de equipos sin stock suficiente para el rango dado.

    Usa SELECT ... FOR UPDATE en equipos para evitar race conditions de concurrencia.

    Si el pedido tiene varios items del MISMO equipo (raro pero posible si el
    frontend tiene un bug o si se usa la API directamente), suma las cantidades
    antes de validar — sino la validación pasaría con falsa negativa. Issue #102.
    La consolidación la hace `expandir_demanda` (un equipo repetido o alcanzado por
    varios caminos suma su demanda).

    Para cada equipo de la demanda, suma el stock reservado por TODOS los pedidos
    activos en el rango (`reservado_total`), contando la reserva DIRECTA y la que
    llega a través de CUALQUIER compuesto que lo contenga, a cualquier profundidad.
    Sin esto dos pedidos podían quedar confirmados sobre la misma unidad — uno vía
    combo anidado y otro directo.

    C4 #635 — la expansión es RECURSIVA hasta las hojas en AMBAS direcciones:
      · Forward (`expandir_demanda`): un item combo→kit→hoja exige stock de la hoja.
      · Backward (`reservado_total`): un combo→kit→hoja reservado por otro pedido
        descuenta la hoja.
    A 1 nivel ambas se contaban de menos → overbooking en anidados. Los nodos se
    lockean en orden ascendente de id (`ORDER BY id`) para que la recursión, que
    lockea más filas, no genere deadlocks entre transacciones concurrentes.

    NÚCLEO SAGRADO: el `SELECT ... FOR UPDATE`, la transacción y el commit son del
    caller; acá solo se emite ese lock (texto SQL intacto) + SELECTs de conteo.
    """
    items = conn.execute(
        "SELECT equipo_id, cantidad FROM alquiler_items WHERE pedido_id = ?",
        (pedido_id,),
    ).fetchall()

    # Consolidar items repetidos del MISMO equipo SUMANDO cantidades (issue #102):
    # un pedido con dos líneas del mismo equipo exige la suma, no la última.
    roots: dict[int, int] = {}
    for r in items:
        roots[r["equipo_id"]] = roots.get(r["equipo_id"], 0) + r["cantidad"]

    # Forward: demanda recursiva hasta las hojas (todos los componentes — el gate
    # sigue estricto; la lógica blanda de best-effort se resuelve afuera).
    demanda = expandir_demanda(conn, roots, solo_esenciales=False)
    if not demanda:
        return []

    # Nombres para los mensajes (el stock AUTORITATIVO sale del lock de abajo, no
    # de acá). Orden ascendente de id → locking determinístico, sin deadlock.
    ids = sorted(demanda)
    ph = ",".join("?" for _ in ids)
    nombres = {
        r["id"]: r["nombre"]
        for r in conn.execute(
            f"SELECT id, nombre FROM equipos WHERE id IN ({ph})", tuple(ids)
        ).fetchall()
    }

    # Buffer entre alquileres: expandimos el rango para exigir gap. Mantenimiento
    # usa el rango original (ventana exacta).
    buffer_horas = get_buffer_horas(conn)
    fd_buf, fh_buf = rango_con_buffer(fecha_desde, fecha_hasta, buffer_horas)

    # Grafo inverso (una sola lectura) + memo de reserva directa: al subir por
    # antecesores compartidos entre nodos no repetimos sub-consultas. No cambian el
    # resultado, solo evitan trabajo (el batch O(N)→1 de #626 queda diferido).
    rev_graph = parientes_de(conn)
    rd_cache: dict[int, int] = {}

    problemas = []
    for eid in ids:  # ascendente por id (ORDER BY id)
        nombre = nombres.get(eid, f"equipo #{eid}")
        # Lock la fila de equipo durante el chequeo para evitar race conditions.
        # SELECT ... FOR UPDATE evita que otra transacción concurrente lea el stock
        # mientras estamos validando.
        lock_result = conn.execute(
            "SELECT cantidad FROM equipos WHERE id = ? FOR UPDATE",
            (eid,)
        ).fetchone()

        if not lock_result:
            problemas.append(f"{nombre} (equipo no encontrado)")
            continue

        stock_total = lock_result["cantidad"]

        # Consumo recursivo de este equipo por OTROS pedidos: directo + vía
        # cualquier compuesto que lo contenga, a cualquier profundidad (C4).
        reservado = reservado_total(
            conn, eid, pedido_id, fh_buf, fd_buf,
            rev_graph=rev_graph, cache=rd_cache,
        )

        # Unidades fuera de servicio por mantenimiento (rango original).
        en_mantenimiento = unidades_en_mantenimiento(
            conn, eid, fecha_desde, fecha_hasta
        )

        disponible = stock_total - reservado - en_mantenimiento
        if disponible < demanda[eid]:
            problemas.append(
                f"{nombre} (necesitás {demanda[eid]}, disponible: {max(0, disponible)})"
            )
    return problemas
