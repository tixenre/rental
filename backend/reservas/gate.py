"""Gate de ESCRITURA del motor de reservas — la última línea contra el overbooking.

Dos entradas públicas, UN solo núcleo:
  - `validar_stock(conn, pedido_id, ...)` — el chequeo AUTORITATIVO que corre al
    crear/confirmar un pedido: lee los items del pedido desde `alquiler_items`.
  - `validar_stock_hipotetico(conn, excl_pedido_id, ..., items)` — el pre-chequeo
    en SECO (dry-run) de una propuesta que TODAVÍA no se guardó (portal del
    cliente): recibe los items hipotéticos y excluye el propio pedido.

Ambas consolidan sus items en `roots` ({equipo_id: cantidad}) y delegan en el
núcleo único `_validar_demanda` — la MISMA expansión, el MISMO lock, el MISMO
conteo. Esto MATERIALIZA "el core de reservas es sagrado / motor único"
(MEMORIA 2026-05-30 y 2026-05-31): el dry-run y el gate real NO PUEDEN divergir
porque son la misma pieza; antes el portal re-implementaba la expansión "en seco"
importando internos y se desincronizaba en silencio si el gate cambiaba.

Originado como move VERBATIM desde `routes/alquileres._check_stock` (issue #501,
Fase 1, Paso 4). C4 (#635) reescribió SOLO la EXPANSIÓN para que sea recursiva
hasta las hojas (forward + backward), cerrando el overbooking en combos anidados;
la semántica del lock/transacción NO cambió (ver invariantes abajo). La red que
fija "mismo comportamiento donde no hay anidamiento" es el test diferencial
`test_gate_caracterizacion_c4.py`.

⚠️ NÚCLEO SAGRADO. Invariantes que C4 (ni ningún refactor) toca:
  - El `SELECT ... FOR UPDATE` (lock pesimista de la fila del equipo) vive en
    `_validar_demanda` con el MISMO texto SQL, en UN solo lugar — no se factoriza a
    un sub-helper más chico ni se duplica por entrada, para que ningún refactor
    pueda "perder" el lock por accidente. Los nodos se lockean en orden ascendente
    de id (`ORDER BY id`) — la recursión lockea más filas, así el orden total evita
    deadlocks entre transacciones concurrentes.
  - El lock y la transacción son del CALLER: el núcleo recibe `conn` y solo emite
    SELECTs; NUNCA llama commit/rollback/get_db/close. El lock vive hasta que el
    caller (update_pedido / crear_reserva_estudio / la propuesta del portal)
    commitea, en su misma sesión → mover o compartir el código entre entradas no
    cambia el alcance ni la duración del lock (es propiedad de la
    conexión+transacción, no del módulo ni de la función).
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
    """Gate AUTORITATIVO: equipos sin stock suficiente para el rango, leyendo los
    items YA guardados del pedido (`alquiler_items`). Corre al crear/confirmar.

    Si el pedido tiene varios items del MISMO equipo (raro pero posible si el
    frontend tiene un bug o si se usa la API directamente), suma las cantidades
    antes de validar — sino la validación pasaría con falsa negativa. Issue #102.

    Lee los items, los consolida en `roots` ({equipo_id: cantidad}) y delega TODO
    el chequeo (expansión recursiva forward+backward, lock `FOR UPDATE`, conteo de
    consumo y mantenimiento) en el núcleo único `_validar_demanda`. El propio
    pedido se excluye del consumo de OTROS pedidos (`excl_pedido_id=pedido_id`).
    """
    # `equipo_id IS NOT NULL` excluye las líneas personalizadas (#805): no son del
    # catálogo y no reservan stock, así que no entran al gate.
    items = conn.execute(
        "SELECT equipo_id, cantidad FROM alquiler_items "
        "WHERE pedido_id = ? AND equipo_id IS NOT NULL",
        (pedido_id,),
    ).fetchall()

    # Consolidar items repetidos del MISMO equipo SUMANDO cantidades (issue #102):
    # un pedido con dos líneas del mismo equipo exige la suma, no la última.
    roots: dict[int, int] = {}
    for r in items:
        roots[r["equipo_id"]] = roots.get(r["equipo_id"], 0) + r["cantidad"]

    return _validar_demanda(conn, roots, pedido_id, fecha_desde, fecha_hasta)


def validar_stock_hipotetico(
    conn, excl_pedido_id: int, fecha_desde: str, fecha_hasta: str, items,
) -> list[str]:
    """Pre-chequeo en SECO (dry-run) de un set HIPOTÉTICO de items + fechas que aún
    NO se guardaron — el portal del cliente lo usa para rechazar una propuesta sin
    stock antes de registrarla.

    Es la MISMA pieza que el gate real (`validar_stock`): consolida los items
    propuestos en `roots` y delega en `_validar_demanda`. Antes el portal
    re-implementaba la expansión "en seco" importando internos del motor y se
    desincronizaba en silencio si el gate cambiaba; ahora no pueden divergir.

    `items` es un iterable de objetos con `.equipo_id` y `.cantidad` (p. ej.
    `ModificacionItemIn`). `excl_pedido_id` es el pedido que se está modificando:
    sus reservas actuales NO compiten con la propuesta para el mismo rango, así que
    se excluyen del consumo. Es de SOLO LECTURA salvo el `FOR UPDATE` del núcleo
    (que vive y muere en la transacción del caller, igual que el gate real).
    """
    if not items or not fecha_desde or not fecha_hasta:
        return []

    # Consolidar la propuesta sumando duplicados del mismo equipo (issue #102).
    # Las líneas personalizadas (#805, sin equipo_id) no reservan stock → se saltean.
    roots: dict[int, int] = {}
    for it in items:
        if getattr(it, "equipo_id", None) is None:
            continue
        roots[it.equipo_id] = roots.get(it.equipo_id, 0) + it.cantidad

    return _validar_demanda(conn, roots, excl_pedido_id, fecha_desde, fecha_hasta)


def _validar_demanda(
    conn, roots: dict, excl_pedido_id: int, fecha_desde: str, fecha_hasta: str,
) -> list[str]:
    """NÚCLEO ÚNICO del gate (lo comparten `validar_stock` y
    `validar_stock_hipotetico` — el dry-run y el autoritativo no pueden divergir).

    Dado un set ya consolidado de `roots` ({equipo_id: cantidad}), devuelve la lista
    de nombres de equipos sin stock suficiente para el rango, excluyendo del consumo
    al pedido `excl_pedido_id`.

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
            conn, eid, excl_pedido_id, fh_buf, fd_buf,
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
