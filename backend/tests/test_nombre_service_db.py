"""`services.nombre_service.actualizar_nombres_de` contra Postgres REAL — verifica
el fix de dead rows (2026-07-04): la función ahora se salta el UPDATE si los
nombres calculados ya coinciden con los guardados. Se llama desde 8 hooks
distintos (setFicha, setCategorias, update_equipo, specs, ...) y en la mayoría
de los guardados el nombre no cambia; un UPDATE incondicional generaba dead
rows en `equipos` en cada guardado sin cambio real — mismo patrón y mismo
método de prueba que `test_categorias_assignment_db.py` (xmin como prueba
directa de "no se escribió nada").

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás *_db.py): se saltea
salvo `RESERVAS_DB_TEST=1` + `DATABASE_URL` a una base con 'test' en el nombre.
Ids altos (9_600_2xx) + limpieza antes/después. Usa `nombre_publico_override`
(gana sobre cualquier template) para controlar el nombre calculado sin
necesidad de armar categorías/specs.
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

EQ = 9_600_201


def _limpiar(conn):
    conn.execute("DELETE FROM equipos WHERE id = %s", (EQ,))


@pytest.fixture
def setup():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (%s,%s,%s)", (EQ, "eq-nombre-test", 1))
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


def _row(conn):
    r = conn.execute(
        "SELECT nombre_publico, nombre_publico_largo, xmin::text AS xmin FROM equipos WHERE id = %s",
        (EQ,),
    ).fetchone()
    return r["nombre_publico"], r["nombre_publico_largo"], r["xmin"]


def test_llamada_repetida_sin_cambio_de_nombre_no_escribe(setup):
    from database import get_db
    from services.nombre_service import actualizar_nombres_de

    conn = get_db()
    try:
        conn.execute(
            "UPDATE equipos SET nombre_publico_override = %s WHERE id = %s", ("Nombre A", EQ)
        )
        conn.commit()

        actualizar_nombres_de(conn, EQ)
        _, _, xmin_antes = _row(conn)

        # Nada cambió en el equipo (mismo override) ⇒ debe ser un no-op total.
        actualizar_nombres_de(conn, EQ)
        corto, largo, xmin_despues = _row(conn)

        assert corto == "Nombre A"
        assert xmin_despues == xmin_antes  # mismo xmin ⇒ no hubo UPDATE
    finally:
        conn.close()


def test_cambio_real_de_nombre_si_se_persiste(setup):
    from database import get_db
    from services.nombre_service import actualizar_nombres_de

    conn = get_db()
    try:
        conn.execute(
            "UPDATE equipos SET nombre_publico_override = %s WHERE id = %s", ("Nombre A", EQ)
        )
        conn.commit()
        actualizar_nombres_de(conn, EQ)

        # Cambiamos el override (esto YA bumpea xmin por sí solo) — lo que nos
        # importa es si actualizar_nombres_de escribe DE NUEVO después.
        conn.execute(
            "UPDATE equipos SET nombre_publico_override = %s WHERE id = %s", ("Nombre B", EQ)
        )
        conn.commit()
        _, _, xmin_tras_override = _row(conn)

        actualizar_nombres_de(conn, EQ)
        corto, _, xmin_despues = _row(conn)

        assert corto == "Nombre B"
        assert xmin_despues != xmin_tras_override  # el nombre calculado cambió ⇒ actualizar_nombres_de sí escribió
    finally:
        conn.close()
