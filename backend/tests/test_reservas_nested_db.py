"""C4 #635 — overbooking de combos ANIDADOS contra Postgres REAL.

El gate y la lectura expanden RECURSIVAMENTE hasta las hojas, en AMBAS
direcciones (forward: mi pedido baja hasta la hoja; backward: lo que otros
reservaron vía un compuesto anidado descuenta la hoja). A 1 nivel un
combo→kit→hoja se contaba de menos → overbooking. Este test lo ejerce contra una
base real: grafo `Combo X → Kit Y → Hoja Z` (stock Z = 1) y verifica que ninguna
de las tres formas de pelear por la hoja deja pasar dos reservas, incluyendo una
carrera concurrente (el `FOR UPDATE` serializa sobre la hoja profunda).

OPT-IN y SEGURO POR DEFECTO (mismo gating que `test_reservas_concurrency_db.py`):
se saltea salvo `RESERVAS_DB_TEST=1` + `DATABASE_URL` a una base con 'test' en el
nombre. Trabaja sobre ids altos (>= 9_200_000) y limpia al terminar.

    DATABASE_URL=postgresql://tincho@localhost/rambla_rental_test \
      RESERVAS_DB_TEST=1 SECRET_KEY=dev \
      python -m pytest tests/test_reservas_nested_db.py -v -m integration
"""
import os
import threading
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

# Grafo:  Combo X → Kit Y → Hoja Z   (stock Z = 1)
Z, Y, X = 9_200_001, 9_200_002, 9_200_003
PA, PB = 9_200_101, 9_200_102
FD, FH = "2026-09-01T08:00:00", "2026-09-02T20:00:00"
OTHER_FD, OTHER_FH = "2026-10-01T08:00:00", "2026-10-02T20:00:00"  # rango sin overlap
ALL_EQ = (X, Y, Z)
ALL_PED = (PA, PB)


def _limpiar(conn):
    conn.execute("DELETE FROM alquiler_items WHERE pedido_id IN (%s,%s)" % ALL_PED)
    conn.execute("DELETE FROM alquileres WHERE id IN (%s,%s)" % ALL_PED)
    conn.execute("DELETE FROM kit_componentes WHERE equipo_id IN (%s,%s,%s)" % ALL_EQ)
    conn.execute("DELETE FROM equipos WHERE id IN (%s,%s,%s)" % ALL_EQ)


@pytest.fixture
def nested_setup():
    """Crea el grafo combo→kit→hoja (idempotente) y limpia al terminar. Z stock=1;
    X e Y con stock alto (no limitan por sí mismos → la hoja Z es el cuello)."""
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (%s,%s,%s)", (Z, "Hoja Z", 1))
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (%s,%s,%s)", (Y, "Kit Y", 9999))
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (%s,%s,%s)", (X, "Combo X", 9999))
        conn.execute("INSERT INTO kit_componentes (equipo_id, componente_id, cantidad) VALUES (%s,%s,%s)", (Y, Z, 1))
        conn.execute("INSERT INTO kit_componentes (equipo_id, componente_id, cantidad) VALUES (%s,%s,%s)", (X, Y, 1))
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


def _crear_pedido(conn, pid, estado, equipo_id, fd=FD, fh=FH, cant=1):
    conn.execute(
        "INSERT INTO alquileres (id, cliente_nombre, estado, fecha_desde, fecha_hasta) VALUES (%s,%s,%s,%s,%s)",
        (pid, "Cliente test (anidado)", estado, fd, fh),
    )
    conn.execute(
        "INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad) VALUES (%s,%s,%s)",
        (pid, equipo_id, cant),
    )


# ── Gate: las tres formas de pelear por la hoja profunda BLOQUEAN ────────────

@pytest.mark.parametrize(
    "nombre, a_equipo, b_equipo",
    [
        ("forward (B combo, A hoja)", Z, X),
        ("backward (B hoja, A combo)", X, Z),
        ("ambos combo", X, X),
        ("backward profundo (B hoja, A kit)", Y, Z),
    ],
)
def test_overbooking_anidado_bloquea(nested_setup, nombre, a_equipo, b_equipo):
    from database import get_db
    from reservas import validar_stock

    conn = get_db()
    try:
        _crear_pedido(conn, PA, "confirmado", a_equipo)  # A ya tomó la hoja
        _crear_pedido(conn, PB, "borrador", b_equipo)    # B intenta
        conn.commit()
        problemas = validar_stock(conn, PB, FD, FH)
        assert problemas, f"[{nombre}] esperaba bloqueo, pasó (OVERBOOKING): {problemas!r}"
        assert any("Hoja Z" in p for p in problemas), problemas
        conn.rollback()
    finally:
        conn.close()


def test_sin_overlap_no_bloquea(nested_setup):
    """Sanity: si A reservó el combo en OTRO rango, B sí puede tomar la hoja."""
    from database import get_db
    from reservas import validar_stock

    conn = get_db()
    try:
        _crear_pedido(conn, PA, "confirmado", X, fd=OTHER_FD, fh=OTHER_FH)
        _crear_pedido(conn, PB, "borrador", Z)
        conn.commit()
        assert validar_stock(conn, PB, FD, FH) == []
        conn.rollback()
    finally:
        conn.close()


def test_disponibilidad_lectura_anidada(nested_setup):
    """Lectura: con la hoja Z tomada por un combo anidado, `calcular_disponibilidad`
    deriva 0 para Z, para el kit Y y para el combo X (no optimista)."""
    from database import get_db
    from reservas import calcular_disponibilidad

    conn = get_db()
    try:
        _crear_pedido(conn, PA, "confirmado", X)
        conn.commit()
        disp = calcular_disponibilidad(conn, FD, FH)
        assert disp.get(str(Z)) == 0
        assert disp.get(str(Y)) == 0   # kit derivado de Z
        assert disp.get(str(X)) == 0   # combo derivado de Y (recursivo)
        conn.rollback()
    finally:
        conn.close()


# ── Concurrencia real: dos combos anidados pelean por la hoja profunda ───────

def _confirmar(pedido_id, equipo_id, barrera, resultados, errores):
    from database import get_db
    from reservas import validar_stock

    conn = get_db()
    try:
        _crear_pedido(conn, pedido_id, "borrador", equipo_id)
        conn.commit()
        barrera.wait(timeout=5)
        problemas = validar_stock(conn, pedido_id, FD, FH)
        if not problemas:
            conn.execute("UPDATE alquileres SET estado='confirmado' WHERE id=%s", (pedido_id,))
            conn.commit()
            resultados[pedido_id] = "confirmado"
        else:
            conn.rollback()
            resultados[pedido_id] = problemas
    except Exception as e:  # noqa: BLE001
        errores[pedido_id] = e
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def test_concurrencia_anidada_solo_una_pasa(nested_setup):
    """Dos pedidos reservan el MISMO combo anidado a la vez; pelean por la única
    Hoja Z (combo→kit→hoja). El `FOR UPDATE` sobre la hoja profunda serializa:
    exactamente una confirma. Sin la expansión recursiva, ninguna lockearía Z y
    ambas pasarían (overbooking)."""
    barrera = threading.Barrier(2)
    resultados: dict[int, object] = {}
    errores: dict[int, Exception] = {}
    ta = threading.Thread(target=_confirmar, args=(PA, X, barrera, resultados, errores))
    tb = threading.Thread(target=_confirmar, args=(PB, X, barrera, resultados, errores))
    ta.start(); tb.start(); ta.join(timeout=15); tb.join(timeout=15)

    assert not ta.is_alive() and not tb.is_alive(), "deadlock: alguna transacción no terminó"
    assert not errores, f"errores en los hilos: {errores}"
    confirmados = [pid for pid, r in resultados.items() if r == "confirmado"]
    assert len(confirmados) == 1, f"esperaba 1 confirmado, hubo {confirmados}: {resultados}"

    from database import get_db
    from reservas import calcular_disponibilidad
    conn = get_db()
    try:
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM alquileres WHERE id IN (%s,%s) AND estado='confirmado'",
            (PA, PB),
        ).fetchone()["n"]
        assert n == 1, f"esperaba 1 confirmado en la DB, hay {n}"
        assert calcular_disponibilidad(conn, FD, FH).get(str(Z), 0) >= 0
    finally:
        conn.close()
