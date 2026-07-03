"""Escala de descuentos por jornadas contra Postgres REAL — lo que el test puro no cubre.

`obtener_descuento_jornadas` fetchea `descuentos_jornada.pct`, que es NUMERIC en la DB
(migración `g1a2b3c4d5e6`) → psycopg lo devuelve como `Decimal`. Ningún test hasta ahora
lo ejercitaba con un `Decimal` real (todo pasaba por `FakeConn`, que da floats/ints
directo) — y hay un fix histórico de `Decimal × float → TypeError` en la interpolación
sin regression-test contra DB real. Este archivo lo cierra, más el CRUD de
`descuentos/commands/jornadas.py`.

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás `*_db.py`): se saltea salvo
`RESERVAS_DB_TEST=1` + `DATABASE_URL` a una base con 'test' en el nombre. Usa valores de
`jornadas` altos (>= 9401) para no chocar con la escala real configurada.

    DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rambla_rental_test \
      RESERVAS_DB_TEST=1 SECRET_KEY=dev \
      python -m pytest tests/test_descuentos_jornada_db.py -v -m integration
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
        not _OPT_IN, reason="opt-in: setear RESERVAS_DB_TEST=1 + DATABASE_URL a una base de prueba"
    ),
    pytest.mark.skipif(
        _OPT_IN and not _looks_like_test_db(),
        reason=f"DATABASE_URL ({_DB_NAME!r}) no parece base de test — abortado por seguridad",
    ),
]

J0 = 9_401  # punto ancla bajo
J1 = 9_405  # punto ancla intermedio
J2 = 9_410  # punto ancla alto


@pytest.fixture
def escala(request):
    """Siembra 3 puntos ancla de prueba y los borra al terminar (los commands
    commitean de verdad, así que no alcanza con rollback)."""
    from database import get_db, init_db
    from descuentos.commands.jornadas import crear_descuento_jornada

    init_db()
    with get_db() as conn:
        with conn.transaction():
            conn.execute("DELETE FROM descuentos_jornada WHERE jornadas IN (%s, %s, %s)", (J0, J1, J2))
        creados = [
            crear_descuento_jornada(conn, jornadas=J0, pct=0.0),
            crear_descuento_jornada(conn, jornadas=J1, pct=5.0),
            crear_descuento_jornada(conn, jornadas=J2, pct=12.0),
        ]
    yield creados
    with get_db() as conn:
        with conn.transaction():
            conn.execute("DELETE FROM descuentos_jornada WHERE jornadas IN (%s, %s, %s)", (J0, J1, J2))


def test_obtener_descuento_jornadas_interpola_con_decimal_real(escala):
    """El fix histórico: `pct` llega como Decimal de Postgres, no debe romper
    con TypeError al interpolar (bug pre-fix: cotizar devolvía 500 → $0)."""
    from database import get_db
    from descuentos.queries.jornadas import obtener_descuento_jornadas

    with get_db() as conn:
        # Punto ancla exacto.
        assert obtener_descuento_jornadas(conn, J1) == 5.0
        # Interpola entre J1(5%) y J2(12%): a mitad de camino.
        medio = (J1 + J2) // 2
        pct = obtener_descuento_jornadas(conn, medio)
        assert 5.0 < pct < 12.0
        # Antes del primer punto y después del último: se clava en los extremos.
        assert obtener_descuento_jornadas(conn, J0 - 1) == 0.0
        assert obtener_descuento_jornadas(conn, J2 + 100) == 12.0


def test_crear_descuento_jornada_hace_upsert_por_jornadas(escala):
    from database import get_db
    from descuentos.commands.jornadas import crear_descuento_jornada

    with get_db() as conn:
        actualizado = crear_descuento_jornada(conn, jornadas=J1, pct=9.0)
        assert actualizado["jornadas"] == J1
        assert float(actualizado["pct"]) == 9.0

        fila = conn.execute(
            "SELECT COUNT(*) AS n FROM descuentos_jornada WHERE jornadas = %s", (J1,)
        ).fetchone()
        assert fila["n"] == 1  # upsert, no duplicó la fila


def test_crear_descuento_jornada_valida_rango():
    from database import get_db

    from descuentos.commands.jornadas import crear_descuento_jornada

    with get_db() as conn:
        with pytest.raises(ValueError, match="jornadas debe ser >= 1"):
            crear_descuento_jornada(conn, jornadas=0, pct=5.0)
        with pytest.raises(ValueError, match="pct debe estar entre 0 y 100"):
            crear_descuento_jornada(conn, jornadas=J0, pct=150.0)


def test_eliminar_descuento_jornada_borra_la_fila(escala):
    from database import get_db
    from descuentos.commands.jornadas import eliminar_descuento_jornada

    with get_db() as conn:
        eliminar_descuento_jornada(conn, escala[0]["id"])
        fila = conn.execute(
            "SELECT COUNT(*) AS n FROM descuentos_jornada WHERE jornadas = %s", (J0,)
        ).fetchone()
        assert fila["n"] == 0


def test_listar_descuentos_jornada_incluye_los_sembrados_ordenados(escala):
    from database import get_db
    from descuentos.queries.jornadas import listar_descuentos_jornada

    with get_db() as conn:
        todos = listar_descuentos_jornada(conn)
        propios = [r for r in todos if r["jornadas"] in (J0, J1, J2)]
        assert [r["jornadas"] for r in propios] == [J0, J1, J2]


@pytest.fixture(autouse=True)
def _sessions_active(monkeypatch):
    monkeypatch.setattr("auth.sessions_store.is_active", lambda jti: {"jti": jti})


def _admin_cookie():
    from auth.session import signer

    # ADMIN_EMAILS en tests = "admin@test.com" (default de conftest.py).
    return f"session={signer.dumps({'email': 'admin@test.com', 'role': 'admin', 'jti': 'jornadadb-adm'})}"


def test_endpoint_interpolar_devuelve_lo_mismo_que_el_backend(escala):
    """`GET /api/descuentos-jornada/interpolar` — la puerta que usa el preview
    de /admin/settings (antes reimplementaba la interpolación en el front,
    #1219). Confirma que el HTTP real coincide con `obtener_descuento_jornadas`
    para un punto ancla exacto Y para un valor interpolado."""
    import main
    from fastapi.testclient import TestClient
    from database import get_db
    from descuentos.queries.jornadas import obtener_descuento_jornadas

    medio = (J1 + J2) // 2
    with get_db() as conn:
        esperado_j1 = obtener_descuento_jornadas(conn, J1)
        esperado_medio = obtener_descuento_jornadas(conn, medio)

    with TestClient(main.app, raise_server_exceptions=True) as client:
        r = client.get(
            "/api/descuentos-jornada/interpolar",
            params={"jornadas": [J1, medio]},
            headers={"Cookie": _admin_cookie()},
        )
    assert r.status_code == 200, r.text
    data = {row["jornadas"]: row["pct"] for row in r.json()}
    assert data[J1] == esperado_j1
    assert data[medio] == esperado_medio


def test_endpoint_interpolar_vacio_es_422():
    import main
    from fastapi.testclient import TestClient

    with TestClient(main.app, raise_server_exceptions=True) as client:
        r = client.get(
            "/api/descuentos-jornada/interpolar", headers={"Cookie": _admin_cookie()}
        )
    assert r.status_code == 422  # sin `jornadas` — FastAPI/Pydantic lo rechaza antes del handler


def test_endpoint_interpolar_rechaza_anonimo():
    import main
    from fastapi.testclient import TestClient

    with TestClient(main.app, raise_server_exceptions=True) as client:
        r = client.get("/api/descuentos-jornada/interpolar", params={"jornadas": [1]})
    assert r.status_code == 401
