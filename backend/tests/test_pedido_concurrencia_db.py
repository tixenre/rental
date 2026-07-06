"""El `FOR UPDATE` de `alquileres` serializa de verdad — Postgres REAL.

Dos lost-updates reales encontrados auditando el módulo (#1254), ambos con la
misma causa: un read-modify-write sobre `alquileres` sin `FOR UPDATE` — dos
escritores concurrentes del MISMO pedido podían pisarse sin error ni log.

1. `agregar_pago`/`anular_pago` (pagos.py) escriben `monto_pagado` vía
   `_recalcular_monto_pagado` (un `UPDATE ... SET monto_pagado = (subquery
   sobre alquiler_pagos)`) sin lockear la fila antes — dos pagos concurrentes
   podían dejar `monto_pagado` divergiendo del ledger real.
2. `_recalcular_total_pedido`/`_apply_pedido_items` (core.py) — sin lock, un
   `propagar_descuento_a_presupuestos` corriendo en paralelo con una edición
   manual de ítems del MISMO presupuesto podía persistir un `monto_total` que
   no correspondía a los ítems finales.

El fix: `FOR UPDATE` sobre la fila de `alquileres` en los 4 puntos que hacen
read-modify-write. Mismo patrón de test que ya usa el repo para este tipo de
candado (`test_reportes_cierres_db.py::test_lock_serializa_cerrar_mes_concurrente`,
`_lock_mes` de contabilidad): dos `Event` en vez de un `Barrier` — no se
apuesta a que la carrera "se solape por suerte", se verifica DETERMINÍSTICAMENTE
que la segunda conexión queda bloqueada mientras la primera retiene el lock,
llamando a las funciones REALES de producción (no una reimplementación en el
test).

OPT-IN y SEGURO POR DEFECTO (mismo gating que `test_reservas_concurrency_db.py`):

    DATABASE_URL=postgresql://tincho@localhost/rambla_rental_test \
      RESERVAS_DB_TEST=1 SECRET_KEY=dev \
      python -m pytest tests/test_pedido_concurrencia_db.py -v -m integration
"""
import os
import threading
import time
from urllib.parse import urlparse

import pytest

_OPT_IN = os.getenv("RESERVAS_DB_TEST") == "1"
_DB_URL = os.getenv("DATABASE_URL", "")
_DB_NAME = urlparse(_DB_URL).path.lstrip("/") if _DB_URL else ""


def _looks_like_test_db() -> bool:
    return bool(_DB_NAME) and "test" in _DB_NAME.lower()


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _OPT_IN,
        reason="opt-in: setear RESERVAS_DB_TEST=1 + DATABASE_URL a una base de prueba",
    ),
    pytest.mark.skipif(
        _OPT_IN and not _looks_like_test_db(),
        reason=f"DATABASE_URL ({_DB_NAME!r}) no parece base de test — abortado por seguridad",
    ),
]

EQ_ID = 9_500_001
PEDIDO_PAGOS = 9_500_101
PEDIDO_ITEMS = 9_500_102
CLIENTE_ID = 9_500_201
FD, FH = "2026-09-01T08:00:00", "2026-09-02T20:00:00"


def _limpiar(conn):
    conn.execute(
        "DELETE FROM alquiler_pagos WHERE pedido_id IN (%s,%s)", (PEDIDO_PAGOS, PEDIDO_ITEMS)
    )
    conn.execute(
        "DELETE FROM alquiler_items WHERE pedido_id IN (%s,%s)", (PEDIDO_PAGOS, PEDIDO_ITEMS)
    )
    conn.execute("DELETE FROM alquileres WHERE id IN (%s,%s)", (PEDIDO_PAGOS, PEDIDO_ITEMS))
    conn.execute("DELETE FROM clientes WHERE id = %s", (CLIENTE_ID,))
    conn.execute("DELETE FROM equipos WHERE id = %s", (EQ_ID,))


@pytest.fixture
def db_setup():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, precio_jornada) VALUES (%s,%s,%s,%s)",
            (EQ_ID, "Equipo test (concurrencia pedido)", 5, 1000),
        )
        conn.execute(
            "INSERT INTO clientes (id, nombre, apellido, descuento) VALUES (%s,%s,%s,%s)",
            (CLIENTE_ID, "Test", "Concurrencia", 10),
        )
        conn.commit()
    finally:
        conn.close()

    yield

    conn = get_db()
    try:
        _limpiar(conn)
        conn.commit()
    finally:
        conn.close()


# ── 1. El FOR UPDATE de agregar_pago serializa dos pagos concurrentes ────────
#
# Diseño (importante, ver el porqué en el docstring del test): NINGÚN hilo
# reimplementa el lock — los dos llaman a `_agregar_pago` REAL. Un hilo A que
# solo sostuviera un lock ocioso (sin escribir) no alcanza para discriminar
# fix-de-no-fix: `_apply_pedido_items`/`_recalcular_monto_pagado` YA hacen un
# `UPDATE` propio al final (con o sin el fix) que igual bloquea contra CUALQUIER
# lock existente en la fila — bloquear no es la parte que hay que probar. Lo
# que hay que probar es si el SEGUNDO escritor VE el pago del primero antes de
# calcular su propia suma — para eso, los dos tienen que ser escritores reales
# compitiendo por la MISMA fila, no uno ocioso y otro activo.

def test_lock_serializa_agregar_pago_concurrente(db_setup):
    """Dos `_agregar_pago` reales sobre el MISMO pedido, compitiendo:
    A inserta $500 y se queda con la transacción ABIERTA (no commitea);
    B espera a que A haya insertado, e intenta agregar $700 al mismo pedido.

    Con el fix: el `FOR UPDATE` inicial de B bloquea hasta que A commitea — la
    subquery de B (`_recalcular_monto_pagado`) recién corre viendo el pago de
    A ya confirmado → suma correcta: 500+700=1200.

    Sin el fix (verificado que este test FALLA contra el código stasheado):
    B no espera nada, lee el estado ANTES de que A commitee (bajo MVCC, A ni
    siquiera es visible para B todavía — normal), calcula su propia suma
    (700) y commitea. Cuando A finalmente commitea con SU cálculo (500,
    hecho antes de que B insertara), la última escritura en pisar gana → el
    pago del otro se pierde en silencio. `_agregar_pago` no commitea sola (el
    caller lo hace) — eso es lo que permite mantener la transacción de A
    abierta a propósito acá, sin ningún hook de test en el código real."""
    from database import get_db

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO alquileres (id, cliente_nombre, estado, monto_pagado) "
            "VALUES (%s,'Cliente test (pagos concurrentes)','confirmado',0)",
            (PEDIDO_PAGOS,),
        )
        conn.commit()
    finally:
        conn.close()

    orden: list[str] = []
    a_inserto = threading.Event()
    liberar_a = threading.Event()
    errores: dict[str, Exception] = {}

    def _pago_a_transaccion_abierta():
        conn = None
        try:
            from database import get_db
            from routes.alquileres.pagos import _agregar_pago, PagoCreate

            conn = get_db()
            _agregar_pago(conn, PEDIDO_PAGOS, PagoCreate(monto=500), "a@rambla.local")
            orden.append("A_inserto")
            a_inserto.set()
            liberar_a.wait(timeout=5)
            conn.commit()
            orden.append("A_commiteo")
        except Exception as e:  # noqa: BLE001
            errores["A"] = e
            a_inserto.set()  # no dejar a B esperando para siempre si A explota
        finally:
            if conn is not None:
                conn.close()

    def _pago_b_concurrente():
        a_inserto.wait(timeout=5)
        conn = None
        try:
            from database import get_db
            from routes.alquileres.pagos import _agregar_pago, PagoCreate

            conn = get_db()
            _agregar_pago(conn, PEDIDO_PAGOS, PagoCreate(monto=700), "b@rambla.local")
            conn.commit()
            orden.append("B_commiteo")
        except Exception as e:  # noqa: BLE001
            errores["B"] = e
        finally:
            if conn is not None:
                conn.close()

    ta = threading.Thread(target=_pago_a_transaccion_abierta)
    tb = threading.Thread(target=_pago_b_concurrente)
    ta.start()
    a_inserto.wait(timeout=5)
    tb.start()
    time.sleep(0.3)  # con el fix, B debería seguir esperando el lock acá.
    assert "B_commiteo" not in orden, (
        "B no debería poder commitear mientras A sigue con la transacción abierta "
        "— si esto falla, el FOR UPDATE no está bloqueando de verdad"
    )
    liberar_a.set()
    ta.join(timeout=5)
    tb.join(timeout=5)

    assert not ta.is_alive() and not tb.is_alive(), "deadlock: algún hilo no terminó"
    assert not errores, f"excepciones inesperadas: {errores}"
    assert orden == ["A_inserto", "A_commiteo", "B_commiteo"], orden

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT monto_pagado FROM alquileres WHERE id=%s", (PEDIDO_PAGOS,)
        ).fetchone()
        real = conn.execute(
            "SELECT COALESCE(SUM(monto),0) AS s FROM alquiler_pagos WHERE pedido_id=%s AND NOT anulado",
            (PEDIDO_PAGOS,),
        ).fetchone()["s"]
        assert row["monto_pagado"] == 1200, (
            f"esperaba 1200 (500+700, ambos pagos contados) — el lost-update sin "
            f"el fix da 500 (el de A, pisado por su propio commit tardío con datos "
            f"stale) o 700 (el de B, si conmiteó después); fue {row['monto_pagado']}"
        )
        assert row["monto_pagado"] == real, "monto_pagado divergió del ledger real"
    finally:
        conn.close()


# ── 2. propagar_descuento_a_presupuestos vs editar ítems del mismo presupuesto

def test_lock_serializa_propagar_descuento_vs_apply_items(db_setup):
    """`_apply_pedido_items` (retenido sin commitear) reemplaza los ítems a
    cantidad=3 — pero NO commitea todavía. `propagar_descuento_a_presupuestos`
    arranca DESPUÉS y, para el mismo pedido, dispara `_recalcular_total_pedido`.

    Ojo con la asimetría: probar esto al revés (propagar reteniendo, items
    aplicando después) NO discrimina nada — Postgres serializa cualquier
    UPDATE-vs-UPDATE sobre la misma fila aunque falte el `FOR UPDATE`
    explícito (el propio `UPDATE` ya toma el lock), y `_apply_pedido_items`
    calcula su total a partir de la cantidad que RECIBE por parámetro, no de
    lo que lee — autoconsistente pase lo que pase. La carrera solo es
    observable en ESTE sentido: `_recalcular_total_pedido` sí decide su
    cálculo en base a lo que LEE de `alquiler_items`, así que importa si esa
    lectura espera al primer escritor o no.

    Sin el fix, la lectura de la fila en `_recalcular_total_pedido` es un
    `SELECT` plano: no espera el lock de la transacción de ítems, así que lee
    los ítems VIEJOS (cantidad=1, aún no comiteados) y computa un total
    stale; cuando por fin commitea (después de que la de ítems ya liberó el
    suyo), pisa el total correcto con uno calculado sobre ítems que ya no
    existen — ítems y total quedan de dos "versiones" distintas del pedido.

    Con el fix: el `FOR UPDATE` de `_recalcular_total_pedido` bloquea hasta
    que la transacción de ítems commitee, y al desbloquear RELEE la fila +
    los ítems ya frescos (cantidad=3) — el recálculo coincide con lo que
    `_apply_pedido_items` ya persistió, sin pisar nada. Verificado que este
    test FALLA sin el fix (monto_total=1000 en vez de 3000, con cantidad=3 ya
    en la tabla — inconsistente)."""
    from database import get_db

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO alquileres (id, cliente_id, cliente_nombre, estado, fecha_desde, fecha_hasta) "
            "VALUES (%s,%s,%s,'presupuesto',%s,%s)",
            (PEDIDO_ITEMS, CLIENTE_ID, "Cliente test (items concurrentes)", FD, FH),
        )
        conn.execute(
            "INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad, precio_jornada) VALUES (%s,%s,1,1000)",
            (PEDIDO_ITEMS, EQ_ID),
        )
        # El bump de descuento del cliente NO es parte de la carrera en sí —
        # ya está commiteado antes de arrancar los hilos, como en la vida real
        # (el admin sube el descuento, y RECIÉN AHÍ dispara la propagación).
        conn.execute("UPDATE clientes SET descuento=50 WHERE id=%s", (CLIENTE_ID,))
        conn.commit()
    finally:
        conn.close()

    orden: list[str] = []
    items_aplico = threading.Event()
    liberar_items = threading.Event()
    errores: dict[str, Exception] = {}

    def _items_transaccion_abierta():
        conn = None
        try:
            from database import get_db
            from routes.alquileres import _apply_pedido_items, PedidoItem

            conn = get_db()
            _apply_pedido_items(
                conn, PEDIDO_ITEMS,
                [PedidoItem(equipo_id=EQ_ID, cantidad=3, precio_jornada=1000, cobro_modo="jornada")],
            )
            orden.append("items_aplico")
            items_aplico.set()
            liberar_items.wait(timeout=5)
            conn.commit()
            orden.append("items_commiteo")
        except Exception as e:  # noqa: BLE001
            errores["items"] = e
            items_aplico.set()
        finally:
            if conn is not None:
                conn.close()

    def _propagar_concurrente():
        items_aplico.wait(timeout=5)
        conn = None
        try:
            from database import get_db
            from routes.alquileres import propagar_descuento_a_presupuestos

            conn = get_db()
            propagar_descuento_a_presupuestos(conn, CLIENTE_ID)
            conn.commit()
            orden.append("propagar_commiteo")
        except Exception as e:  # noqa: BLE001
            errores["propagar"] = e
        finally:
            if conn is not None:
                conn.close()

    t_items = threading.Thread(target=_items_transaccion_abierta)
    t_propagar = threading.Thread(target=_propagar_concurrente)
    t_items.start()
    items_aplico.wait(timeout=5)
    t_propagar.start()
    time.sleep(0.3)  # con el fix, propagar debería seguir esperando el lock acá.
    assert "propagar_commiteo" not in orden, (
        "propagar no debería poder commitear mientras la transacción de ítems sigue "
        "abierta — si esto falla, el FOR UPDATE no está bloqueando de verdad"
    )
    liberar_items.set()
    t_items.join(timeout=5)
    t_propagar.join(timeout=5)

    assert not t_items.is_alive() and not t_propagar.is_alive(), "deadlock: algún hilo no terminó"
    assert not errores, f"excepciones inesperadas: {errores}"
    assert orden == ["items_aplico", "items_commiteo", "propagar_commiteo"], orden

    conn = get_db()
    try:
        p = conn.execute("SELECT * FROM alquileres WHERE id=%s", (PEDIDO_ITEMS,)).fetchone()
        items = conn.execute(
            "SELECT equipo_id, cantidad, precio_jornada, cobro_modo FROM alquiler_items WHERE pedido_id=%s",
            (PEDIDO_ITEMS,),
        ).fetchall()
        assert len(items) == 1 and items[0]["cantidad"] == 3, "el cambio de ítems no debería haberse perdido"

        # FD/FH cubren 36hs → jornadas_periodo (ceil/24h) = 2. Neto esperado =
        # 1000 (precio) × 3 (cantidad) × 2 (jornadas) × 0.5 (desc.) = 3000.
        # Sin el fix, propagar relee ítems VIEJOS (cantidad=1, aún no
        # comiteados) y pisa el total correcto con uno calculado sobre ellos.
        assert p["monto_total"] == 3000, (
            f"esperaba 3000 (3 ítems × 1000 × 2 jornadas × 50% desc.) — el "
            f"lost-update sin el fix pisa con 1000 (calculado sobre la "
            f"cantidad VIEJA, 1, antes de reemplazarla por 3); fue {p['monto_total']}"
        )
    finally:
        conn.close()
