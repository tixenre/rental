"""Concurrencia del gate con Postgres REAL — la prueba definitiva del FOR UPDATE.

El test unit (`test_reservas_concurrency.py`) emula el row-lock con un
`threading.Lock`: prueba que el gate LEE bajo el lock y que la lógica serializa,
pero NO ejerce el `SELECT ... FOR UPDATE` real de Postgres. Este test cierra ese
hueco: levanta dos transacciones reales, en paralelo, peleando por la última
unidad, y verifica que el candado pesimista de Postgres serializa de verdad →
exactamente una confirmación pasa, cero overbooking.

OPT-IN y SEGURO POR DEFECTO: se saltea (skip) salvo que apuntes `DATABASE_URL` a
una base de PRUEBA descartable. Nunca corre en el CI normal ni toca prod. Para
correrlo localmente (decisión MEMORIA: sesión local para lo que necesita BD):

    createdb rambla_rental_test
    DATABASE_URL=postgresql://postgres:postgres@localhost/rambla_rental_test \
      RESERVAS_DB_TEST=1 \
      python -m pytest tests/test_reservas_concurrency_db.py -v -m integration

Guard-rails para no pisar una base con datos:
  - Exige el opt-in explícito `RESERVAS_DB_TEST=1`.
  - Se niega a correr si la `DATABASE_URL` no parece de test (debe contener
    'test' en el nombre de la base).
  - Trabaja sobre filas con ids altos (>= 9_000_000) y las limpia al terminar.
"""
import os
import threading
from urllib.parse import urlparse

import pytest

# ── Gating: skip salvo opt-in explícito + DB de test ─────────────────────────

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

# IDs altos y reservados para este test, para no chocar con datos existentes.
EQ_ID = 9_000_001
PED_A = 9_000_101
PED_B = 9_000_102
FD = "2026-09-01T08:00:00"
FH = "2026-09-02T20:00:00"


@pytest.fixture
def db_setup():
    """Crea el esquema (idempotente) y siembra: 1 equipo con stock=1 y dos
    pedidos en 'borrador' (no reservan todavía), cada uno con un item de esa
    unidad. Limpia al terminar."""
    from database import get_db, init_db

    init_db()  # idempotente (CREATE TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS)

    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad) VALUES (?, ?, ?)",
            (EQ_ID, "Cámara de test (concurrencia)", 1),
        )
        for pid in (PED_A, PED_B):
            conn.execute(
                "INSERT INTO alquileres (id, cliente_nombre, estado, fecha_desde, fecha_hasta) "
                "VALUES (?, ?, 'borrador', ?, ?)",
                (pid, "Cliente de test (concurrencia)", FD, FH),
            )
            conn.execute(
                "INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad) "
                "VALUES (?, ?, ?)",
                (pid, EQ_ID, 1),
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


def _limpiar(conn):
    conn.execute("DELETE FROM alquiler_items WHERE equipo_id = ?", (EQ_ID,))
    conn.execute("DELETE FROM alquileres WHERE id IN (?, ?)", (PED_A, PED_B))
    conn.execute("DELETE FROM equipos WHERE id = ?", (EQ_ID,))


def _confirmar(pedido_id, barrera, resultados, errores):
    """Replica el patrón del caller real (update_pedido): abre transacción,
    valida stock BAJO el lock, y si pasa confirma + commitea — todo en la misma
    conexión, para que el FOR UPDATE viva hasta el commit."""
    from database import get_db
    from reservas import validar_stock

    conn = get_db()
    try:
        # Sincronizamos el arranque para forzar la colisión.
        barrera.wait(timeout=5)
        problemas = validar_stock(conn, pedido_id, FD, FH)
        if not problemas:
            conn.execute(
                "UPDATE alquileres SET estado = 'confirmado' WHERE id = ?",
                (pedido_id,),
            )
            conn.commit()  # libera el lock recién acá
            resultados[pedido_id] = "confirmado"
        else:
            conn.rollback()
            resultados[pedido_id] = problemas
    except Exception as e:  # noqa: BLE001 — lo re-lanzamos al hilo principal
        errores[pedido_id] = e
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def test_dos_confirmaciones_reales_solo_una_pasa(db_setup):
    """Dos transacciones reales pelean por la única unidad. El FOR UPDATE de
    Postgres serializa: exactamente una confirma, la otra ve 0 disponible."""
    barrera = threading.Barrier(2)
    resultados: dict[int, object] = {}
    errores: dict[int, Exception] = {}

    ta = threading.Thread(target=_confirmar, args=(PED_A, barrera, resultados, errores))
    tb = threading.Thread(target=_confirmar, args=(PED_B, barrera, resultados, errores))
    ta.start()
    tb.start()
    ta.join(timeout=15)
    tb.join(timeout=15)

    assert not ta.is_alive() and not tb.is_alive(), "deadlock: alguna transacción no terminó"
    assert not errores, f"errores en los hilos: {errores}"

    confirmados = [pid for pid, r in resultados.items() if r == "confirmado"]
    rechazados = [pid for pid, r in resultados.items() if r != "confirmado"]
    assert len(confirmados) == 1, f"esperaba exactamente 1 confirmado, hubo {confirmados}"
    assert len(rechazados) == 1
    # El rechazado debe reportar el equipo sin stock.
    probs = resultados[rechazados[0]]
    assert isinstance(probs, list) and any("test" in p.lower() for p in probs)


def test_la_verdad_quedo_consistente_en_la_db(db_setup):
    """Tras la pelea, en la base hay exactamente UN pedido confirmado sobre la
    unidad — la disponibilidad real no quedó negativa (cero overbooking)."""
    from database import get_db
    from reservas import calcular_disponibilidad

    barrera = threading.Barrier(2)
    resultados: dict[int, object] = {}
    errores: dict[int, Exception] = {}
    ta = threading.Thread(target=_confirmar, args=(PED_A, barrera, resultados, errores))
    tb = threading.Thread(target=_confirmar, args=(PED_B, barrera, resultados, errores))
    ta.start(); tb.start(); ta.join(timeout=15); tb.join(timeout=15)
    assert not errores, f"errores en los hilos: {errores}"

    conn = get_db()
    try:
        confirmados = conn.execute(
            "SELECT COUNT(*) AS n FROM alquileres "
            "WHERE id IN (?, ?) AND estado = 'confirmado'",
            (PED_A, PED_B),
        ).fetchone()["n"]
        assert confirmados == 1, f"esperaba 1 pedido confirmado en la DB, hay {confirmados}"

        # La disponibilidad de la unidad nunca es negativa.
        disp = calcular_disponibilidad(conn, FD, FH)
        assert disp.get(str(EQ_ID), 0) >= 0
    finally:
        conn.close()


# ── Creación concurrente: regresión del deadlock de `create_pedido` ───────────
# El test de arriba ejerce el path de CONFIRMACIÓN (validar_stock sobre pedidos
# ya insertados). Este cubre el path de CREACIÓN (`create_pedido`), donde el
# insert de `alquiler_items` toma FK KEY-SHARE sobre la fila de `equipos` y el
# gate pide FOR UPDATE → bajo concurrencia se deadlockeaban y salía 500. La fix
# (advisory xact-lock por equipo, en orden de id, antes del insert) los serializa.

EQ_ID2 = 9_000_002
STOCK2 = 3
N_CONC = 10
FD2 = "2026-10-01T08:00:00"
FH2 = "2026-10-02T20:00:00"
_NOMBRE_TEST = "Test concurrencia crear"


@pytest.fixture
def db_setup_crear():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar_crear(conn)
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, precio_jornada) VALUES (?, ?, ?, ?)",
            (EQ_ID2, "Equipo de test (crear concurrente)", STOCK2, 1000),
        )
        conn.commit()
    finally:
        conn.close()

    yield

    conn = get_db()
    try:
        _limpiar_crear(conn)
        conn.commit()
    finally:
        conn.close()


def _limpiar_crear(conn):
    conn.execute(
        "DELETE FROM alquiler_items WHERE pedido_id IN "
        "(SELECT id FROM alquileres WHERE cliente_nombre = ?)",
        (_NOMBRE_TEST,),
    )
    conn.execute("DELETE FROM alquileres WHERE cliente_nombre = ?", (_NOMBRE_TEST,))
    conn.execute("DELETE FROM equipos WHERE id = ?", (EQ_ID2,))


def _crear(barrera, idx, resultados, errores):
    from fastapi import BackgroundTasks, HTTPException
    from routes.alquileres import create_pedido_retry, PedidoCreate, PedidoItem

    data = PedidoCreate(
        cliente_nombre=_NOMBRE_TEST, fecha_desde=FD2, fecha_hasta=FH2,
        estado="presupuesto",
        items=[PedidoItem(equipo_id=EQ_ID2, cantidad=1, precio_jornada=1000)],
    )
    try:
        barrera.wait(timeout=5)
        pedido = create_pedido_retry(data, background=BackgroundTasks())
        resultados[idx] = ("ok", pedido["id"])
    except HTTPException as e:
        resultados[idx] = ("http", e.status_code)
    except Exception as e:  # noqa: BLE001 — lo capturamos para fallar el test
        errores[idx] = repr(e)


def test_crear_pedidos_concurrentes_sin_deadlock_ni_overbooking(db_setup_crear):
    """N reservas concurrentes del mismo equipo (stock=STOCK2): exactamente
    STOCK2 se crean, el resto recibe 409 (sin stock) o 503 (carga) — NUNCA 500
    ni excepción no controlada (el deadlock), y cero overbooking en la DB."""
    barrera = threading.Barrier(N_CONC)
    resultados: dict[int, object] = {}
    errores: dict[int, str] = {}
    threads = [
        threading.Thread(target=_crear, args=(barrera, i, resultados, errores))
        for i in range(N_CONC)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert all(not t.is_alive() for t in threads), "deadlock: algún hilo no terminó"
    # CLAVE: ninguna excepción no controlada (el deadlock salía como 500).
    assert not errores, f"excepciones no controladas (¿deadlock?): {errores}"

    oks = [v for v in resultados.values() if v[0] == "ok"]
    codes = [v[1] for v in resultados.values() if v[0] == "http"]
    assert len(oks) == STOCK2, f"esperaba {STOCK2} creados, hubo {len(oks)}: {resultados}"
    assert all(c in (409, 503) for c in codes), f"códigos inesperados (¿500?): {codes}"

    # La verdad en la DB: exactamente STOCK2 pedidos y disponibilidad no negativa.
    from database import get_db
    from reservas import calcular_disponibilidad

    conn = get_db()
    try:
        creados = conn.execute(
            "SELECT COUNT(*) AS n FROM alquileres WHERE cliente_nombre = ?",
            (_NOMBRE_TEST,),
        ).fetchone()["n"]
        assert creados == STOCK2, f"esperaba {STOCK2} pedidos en la DB, hay {creados}"
        disp = calcular_disponibilidad(conn, FD2, FH2)
        assert disp.get(str(EQ_ID2), 0) >= 0
    finally:
        conn.close()
