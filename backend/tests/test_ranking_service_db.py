"""#862 — `services.ranking_service` contra Postgres real.

El ranking del catálogo (`recalcular_ranking_todos`) calcula
`popularidad_score` normalizado por categoría desde el historial de pedidos +
ingreso. Este test arma un universo chico (dos equipos en la misma categoría
raíz, uno con pedidos y otro sin) y verifica:
  1. El equipo con pedidos queda en score 100 (max en pedidos Y en ingreso →
     50 + 50); el equipo sin pedidos, 0.
  2. `dry_run=True` NO muta la base (reporta cambios pero no escribe).

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás *_db.py): se saltea
salvo `RESERVAS_DB_TEST=1` + `DATABASE_URL` a una base con 'test' en el nombre.
Trabaja sobre ids altos (>= 9_500_000) y limpia al terminar.
"""
import os
from datetime import date, timedelta
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

CAT = 9_500_001
A, B = 9_500_011, 9_500_012  # A con pedidos, B sin
PED = 9_500_101
FD = (date.today() - timedelta(days=10)).isoformat()
FH = (date.today() - timedelta(days=8)).isoformat()  # 2 días → GREATEST(1, 2) = 2


def _limpiar(conn):
    conn.execute("DELETE FROM alquiler_items WHERE pedido_id = %s", (PED,))
    conn.execute("DELETE FROM alquileres WHERE id = %s", (PED,))
    conn.execute("DELETE FROM equipo_categorias WHERE equipo_id IN (%s,%s)" % (A, B))
    conn.execute("DELETE FROM equipos WHERE id IN (%s,%s)" % (A, B))
    conn.execute("DELETE FROM categorias WHERE id = %s", (CAT,))


@pytest.fixture
def universo():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute("INSERT INTO categorias (id, nombre) VALUES (?,?)", (CAT, "Cat Ranking Test"))
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (?,?,?)", (A, "Equipo A rank", 1))
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (?,?,?)", (B, "Equipo B rank", 1))
        conn.execute("INSERT INTO equipo_categorias (equipo_id, categoria_id) VALUES (?,?)", (A, CAT))
        conn.execute("INSERT INTO equipo_categorias (equipo_id, categoria_id) VALUES (?,?)", (B, CAT))
        # Pedido confirmado para A: 1 × 1000 × 2 días = 2000 de ingreso, 1 pedido.
        conn.execute(
            "INSERT INTO alquileres (id, cliente_nombre, estado, fecha_desde, fecha_hasta) VALUES (?,?,?,?,?)",
            (PED, "Cliente rank", "confirmado", FD, FH),
        )
        conn.execute(
            "INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad, precio_jornada) VALUES (?,?,?,?)",
            (PED, A, 1, 1000),
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


def _score(conn, eid):
    return conn.execute(
        "SELECT popularidad_score, cant_pedidos, ingreso_total_ars FROM equipos WHERE id = ?",
        (eid,),
    ).fetchone()


def test_recalcular_asigna_score_por_categoria(universo):
    from database import get_db
    from services.ranking_service import recalcular_ranking_todos

    conn = get_db()
    try:
        rep = recalcular_ranking_todos(conn, ventana_dias=180)
        assert rep["dry_run"] is False
        ra = _score(conn, A)
        rb = _score(conn, B)
        # A es el max de su categoría en pedidos e ingreso → 50 + 50 = 100.
        assert ra["popularidad_score"] == 100, dict(ra)
        assert ra["cant_pedidos"] == 1
        assert ra["ingreso_total_ars"] == 2000
        # B sin pedidos → 0.
        assert rb["popularidad_score"] == 0, dict(rb)
    finally:
        conn.close()


def test_dry_run_no_muta(universo):
    from database import get_db
    from services.ranking_service import recalcular_ranking_todos

    conn = get_db()
    try:
        rep = recalcular_ranking_todos(conn, dry_run=True, ventana_dias=180)
        assert rep["dry_run"] is True
        assert rep["cambios"], "dry_run igual debe REPORTAR los cambios que haría"
        conn.rollback()
        # La base sigue en su estado inicial (score 0 por default).
        assert _score(conn, A)["popularidad_score"] == 0
    finally:
        conn.close()
