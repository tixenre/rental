"""`services.categorias.commands.assignment.asignar_categorias` contra Postgres
REAL — verifica el fix de dead rows (2026-07-04): la función ahora diffea
contra el estado actual de `equipo_categorias` en vez de hacer un
DELETE+INSERT incondicional. El form de equipo llama esto en cada save, aunque
no se haya tocado la sección de categorías — sin el diff, cada guardado
generaba dead rows en `equipo_categorias` (y un UPDATE de más en `equipos` vía
`actualizar_nombres_de`) incluso cuando el set de categorías no cambiaba.

Se prueba con la columna de sistema `xmin` (versión física de la fila en
Postgres MVCC): una fila NO tocada conserva su `xmin`; una fila reescrita
(UPDATE/DELETE+INSERT) cambia de `xmin`. Es la forma directa de probar "no se
escribió nada" sin depender de contar dead rows (que requiere autovacuum/stats
asincrónicos).

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás *_db.py): se saltea
salvo `RESERVAS_DB_TEST=1` + `DATABASE_URL` a una base con 'test' en el nombre.
Ids altos (9_600_xxx) + limpieza antes/después.
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

C1, C2 = 9_600_001, 9_600_002  # categorías raíz, sin parent (ancestor expansion trivial)
EQ = 9_600_101


def _limpiar(conn):
    conn.execute("DELETE FROM equipo_categorias WHERE equipo_id = %s", (EQ,))
    conn.execute("DELETE FROM equipos WHERE id = %s", (EQ,))
    conn.execute("DELETE FROM categorias WHERE id IN (%s,%s)" % (C1, C2))


@pytest.fixture
def setup():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute(
            "INSERT INTO categorias (id, nombre, prioridad, parent_id) VALUES "
            "(%s,%s,%s,%s),(%s,%s,%s,%s)",
            (C1, "ZZ-Cat1-test", 10, None, C2, "ZZ-Cat2-test", 20, None),
        )
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (%s,%s,%s)", (EQ, "eq-assign-test", 1))
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


def _filas_equipo_categorias(conn):
    rows = conn.execute(
        "SELECT categoria_id, orden, xmin::text AS xmin FROM equipo_categorias "
        "WHERE equipo_id = %s ORDER BY categoria_id",
        (EQ,),
    ).fetchall()
    return {r["categoria_id"]: (r["orden"], r["xmin"]) for r in rows}


def _xmin_equipo(conn):
    row = conn.execute("SELECT xmin::text AS xmin FROM equipos WHERE id = %s", (EQ,)).fetchone()
    return row["xmin"]


def test_llamada_repetida_con_mismo_set_no_escribe_nada(setup):
    from database import get_db
    from services.categorias.commands.assignment import asignar_categorias

    conn = get_db()
    try:
        asignar_categorias(conn, EQ, [C1, C2])
        conn.commit()
        antes = _filas_equipo_categorias(conn)
        xmin_eq_antes = _xmin_equipo(conn)
        assert set(antes) == {C1, C2}

        # Mismo set, mismo orden: debe ser un no-op total (ni DELETE, ni
        # INSERT/UPDATE, ni el side-effect de actualizar_nombres_de).
        asignar_categorias(conn, EQ, [C1, C2])
        conn.commit()
        despues = _filas_equipo_categorias(conn)

        assert despues == antes  # mismo xmin por fila ⇒ ninguna fila fue tocada
        assert _xmin_equipo(conn) == xmin_eq_antes  # tampoco se re-escribió equipos.nombre_publico
    finally:
        conn.close()


def test_quitar_una_categoria_no_toca_la_que_no_cambio(setup):
    from database import get_db
    from services.categorias.commands.assignment import asignar_categorias

    conn = get_db()
    try:
        asignar_categorias(conn, EQ, [C1, C2])
        conn.commit()
        antes = _filas_equipo_categorias(conn)

        # Sacamos C2; C1 queda con el mismo orden (0) ⇒ su fila no debería tocarse.
        asignar_categorias(conn, EQ, [C1])
        conn.commit()
        despues = _filas_equipo_categorias(conn)

        assert set(despues) == {C1}
        assert despues[C1] == antes[C1]  # mismo xmin: la fila de C1 no se reescribió
    finally:
        conn.close()


def test_reordenar_si_escribe_las_filas_afectadas(setup):
    from database import get_db
    from services.categorias.commands.assignment import asignar_categorias

    conn = get_db()
    try:
        asignar_categorias(conn, EQ, [C1, C2])
        conn.commit()

        # Invertimos el orden: ambas filas cambian de `orden` ⇒ ambas se escriben.
        asignar_categorias(conn, EQ, [C2, C1])
        conn.commit()
        despues = _filas_equipo_categorias(conn)

        assert despues[C1][0] == 1
        assert despues[C2][0] == 0
    finally:
        conn.close()
