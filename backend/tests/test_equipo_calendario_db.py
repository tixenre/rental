"""#923 — el calendario del equipo refleja el consumo vía compuestos ANIDADOS.

`GET /equipos/{id}/calendario` (handler `get_equipo_calendario`) muestra unidades
libres por día. Antes reimplementaba el overlap a 1 SOLO nivel de kit (`directas`
+ `via_kit`) → una hoja reservada vía un combo→kit anidado se mostraba LIBRE
(overbooking visible / fuente única violada, MEMORIA 2026-05-30 / 2026-05-31).
Ahora delega en el motor único `reservas.reservado_total` (recursivo hasta la
hoja). Este test arma `Combo X → Kit Y → Hoja Z` (stock Z = 1), reserva el combo
X y verifica que el calendario de la hoja Z marca 0 libres en los días del rango
(la versión vieja, a 1 nivel, mostraba 1 → la regresión que cazamos).

OPT-IN y SEGURO POR DEFECTO (mismo gating que `test_reservas_nested_db.py`):
se saltea salvo `RESERVAS_DB_TEST=1` + `DATABASE_URL` a una base con 'test' en el
nombre. Trabaja sobre ids altos (>= 9_300_000) y limpia al terminar.

    DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rambla_rental_test \
      RESERVAS_DB_TEST=1 SECRET_KEY=dev ADMIN_EMAILS=admin@test.com \
      python -m pytest tests/test_equipo_calendario_db.py -v -m integration
"""
import os
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
Z, Y, X = 9_300_001, 9_300_002, 9_300_003
PA = 9_300_101
# Rango dentro de septiembre 2026 (días 10 y 11 ocupados).
FD, FH = "2026-09-10T08:00:00", "2026-09-11T20:00:00"
ALL_EQ = (X, Y, Z)


def _limpiar(conn):
    conn.execute("DELETE FROM alquiler_items WHERE pedido_id IN (%s)" % PA)
    conn.execute("DELETE FROM alquileres WHERE id IN (%s)" % PA)
    conn.execute("DELETE FROM kit_componentes WHERE equipo_id IN (%s,%s,%s)" % ALL_EQ)
    conn.execute("DELETE FROM equipos WHERE id IN (%s,%s,%s)" % ALL_EQ)


@pytest.fixture
def nested_setup():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (%s,%s,%s)", (Z, "Hoja Z cal", 1))
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (%s,%s,%s)", (Y, "Kit Y cal", 9999))
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (%s,%s,%s)", (X, "Combo X cal", 9999))
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
        (pid, "Cliente test (calendario)", estado, fd, fh),
    )
    conn.execute(
        "INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad) VALUES (%s,%s,%s)",
        (pid, equipo_id, cant),
    )


def test_calendario_hoja_refleja_combo_anidado(nested_setup):
    """Con el COMBO X reservado, el calendario de la HOJA Z marca 0 libres en los
    días del rango. La versión vieja (overlap a 1 nivel) mostraba 1 → overbooking."""
    from database import get_db
    from routes.equipos.core import get_equipo_calendario

    conn = get_db()
    try:
        _crear_pedido(conn, PA, "confirmado", X)  # se reserva el COMBO, no la hoja
        conn.commit()
    finally:
        conn.close()

    cal = get_equipo_calendario(Z, year=2026, month=9)
    assert cal["2026-09-10"] == 0, f"día 10 debería estar ocupado vía combo anidado: {cal['2026-09-10']}"
    assert cal["2026-09-11"] == 0, f"día 11 debería estar ocupado vía combo anidado: {cal['2026-09-11']}"
    # Día fuera del rango: la hoja sigue libre (stock 1).
    assert cal["2026-09-20"] == 1, f"día 20 debería estar libre: {cal['2026-09-20']}"


def test_calendario_sin_reserva_todo_libre(nested_setup):
    """Sanity: sin pedidos, todos los días del mes muestran el stock completo."""
    from routes.equipos.core import get_equipo_calendario

    cal = get_equipo_calendario(Z, year=2026, month=9)
    assert all(v == 1 for v in cal.values()), cal
    assert len(cal) == 30  # septiembre
