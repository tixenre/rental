"""`routes.alquileres.pedidos.list_pedidos` — búsqueda por nombre contra Postgres
REAL. Candado del bug 2026-07-XX: la búsqueda usaba `LIKE` crudo (case-SENSITIVE
en Postgres), así que buscar "tinc" NO encontraba al cliente "Tincho". El fix la
pasa por el motor único `backend/busqueda` (f_unaccent + lower + fuzzy), que
necesita las extensiones `pg_trgm`/`unaccent` → sólo se puede probar de verdad
contra una base real, no con mocks.

Cubre las 3 cosas que el `LIKE` viejo NO hacía y el motor sí:
  1. case-insensitive ("tinc" encuentra "Tincho")
  2. sin acentos ("tinchoqz" encuentra "Tinchöqz")
  3. nombre EN VIVO del cliente (snapshot vacío) incluyendo el campo RENAPER
     (`nombre_renaper`), que es lo que de hecho se MUESTRA en la lista.

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás *_db.py). Ids altos +
limpieza antes/después. Llama a la función de la ruta directo (no HTTP) con
`ADMIN_BYPASS_AUTH=1` — mismo patrón que `test_kit_componentes_write_db.py`.
"""
import os
from urllib.parse import urlparse

import pytest
from starlette.requests import Request

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

# Ids altos, marcadores únicos → no colisionan con datos reales del clon.
CLI_BASE, CLI_RENAPER = 9_700_001, 9_700_002
PED_BASE, PED_RENAPER = 9_700_101, 9_700_102


def _fake_request() -> Request:
    """Request real (no stub) — list_pedidos hace require_admin(request); con
    ADMIN_BYPASS_AUTH=1 no lo inspecciona, alcanza el scope ASGI mínimo."""
    return Request(
        {"type": "http", "method": "GET", "path": "/api/alquileres", "headers": [], "client": ("127.0.0.1", 0)}
    )


def _limpiar(conn):
    conn.execute("DELETE FROM alquileres WHERE id IN (%s,%s)" % (PED_BASE, PED_RENAPER))
    conn.execute("DELETE FROM clientes   WHERE id IN (%s,%s)" % (CLI_BASE, CLI_RENAPER))


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("ADMIN_BYPASS_AUTH", "1")
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        # Cliente con nombre base "Tincho" (T mayúscula + ö con acento en el marcador).
        conn.execute(
            "INSERT INTO clientes (id, nombre, apellido) VALUES (%s,%s,%s)",
            (CLI_BASE, "Tinchöqz", "Zzcliente"),
        )
        # Cliente verificado: el nombre que se MUESTRA sale de RENAPER, no del base.
        conn.execute(
            "INSERT INTO clientes (id, nombre, apellido, nombre_renaper, apellido_renaper) "
            "VALUES (%s,%s,%s,%s,%s)",
            (CLI_RENAPER, "Basexq", "Nobody", "Renaperqz", "Legalqz"),
        )
        # Pedidos con snapshot `cliente_nombre` VACÍO → fuerza el camino "nombre en
        # vivo del cliente" (exactamente donde el LIKE case-sensitive fallaba).
        conn.execute(
            "INSERT INTO alquileres (id, cliente_id, cliente_nombre, estado) VALUES (%s,%s,%s,%s)",
            (PED_BASE, CLI_BASE, "", "borrador"),
        )
        conn.execute(
            "INSERT INTO alquileres (id, cliente_id, cliente_nombre, estado) VALUES (%s,%s,%s,%s)",
            (PED_RENAPER, CLI_RENAPER, "", "borrador"),
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


def _ids(resultado) -> set[int]:
    return {p["id"] for p in resultado["items"]}


def _buscar(q: str) -> set[int]:
    from routes.alquileres.pedidos import list_pedidos

    # Llamada directa (no HTTP): hay que pasar TODOS los params — si no, los
    # `Query(...)` default de FastAPI quedan sin resolver (un `Query` objeto es
    # truthy y rompería `if estado:` / `page - 1`).
    return _ids(
        list_pedidos(
            _fake_request(),
            estado=None,
            fuente=None,
            q=q,
            con_saldo=None,
            page=1,
            per_page=500,
            sort_by=None,
            sort_dir="desc",
        )
    )


def test_busqueda_por_nombre_es_case_insensitive(setup):
    # El bug: "tinc" en minúscula NO encontraba a "Tincho" (LIKE case-sensitive).
    assert PED_BASE in _buscar("tinc")
    assert PED_BASE in _buscar("TINCHOQZ")
    assert PED_BASE in _buscar("Tincho")


def test_busqueda_por_nombre_ignora_acentos(setup):
    # "tinchoqz" (sin acento) encuentra "Tinchöqz".
    assert PED_BASE in _buscar("tinchoqz")


def test_busqueda_matchea_nombre_renaper_en_vivo(setup):
    # El nombre mostrado sale de RENAPER; buscarlo tiene que encontrar el pedido.
    assert PED_RENAPER in _buscar("renaperqz")


def test_busqueda_sin_match_no_devuelve_los_sembrados(setup):
    encontrados = _buscar("zzznohitqz")
    assert PED_BASE not in encontrados and PED_RENAPER not in encontrados


def test_busqueda_por_numero_de_pedido_sigue_andando(setup):
    # El número es un id, se matchea por substring exacto (no fuzzy). Le asignamos
    # un numero_pedido y lo buscamos por su dígito.
    from database import get_db

    conn = get_db()
    try:
        conn.execute("UPDATE alquileres SET numero_pedido=%s WHERE id=%s", (970101, PED_BASE))
        conn.commit()
    finally:
        conn.close()
    assert PED_BASE in _buscar("970101")
