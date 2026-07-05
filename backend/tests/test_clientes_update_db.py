"""PATCH /clientes/{id} contra Postgres real — candado del bug de placeholders `?`.

`update_cliente` armaba el `SET` con placeholders `?` (herencia sqlite3) en vez de
`%s` nativo de psycopg — el driver real nunca los traduce, así que CUALQUIER edición
de un cliente (nombre, descuento, lo que sea) fallaba en producción. El unit test con
`FakeConn` no lo hubiera cazado (un fake acepta cualquier placeholder); hace falta un
driver real para que reviente. Encontrado auditando el camino de
`propagar_descuento_a_presupuestos` (2026-07-03), sin relación al módulo de descuentos.

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás `*_db.py`): se saltea salvo
`RESERVAS_DB_TEST=1` + `DATABASE_URL` a una base con 'test' en el nombre.
"""
import os
from urllib.parse import urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

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


def _client() -> TestClient:
    from routes.clientes import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


@pytest.fixture
def admin_cookie(monkeypatch):
    """Sesión admin válida sin tocar `auth_sessions` (jti obligatorio, ver
    test_routes_admin_guard_db.py — mismo truco)."""
    from auth.session import signer

    monkeypatch.setattr("auth.queries.sessions.is_active", lambda jti: {"jti": jti})
    payload = {"email": "admin@test.com", "role": "admin", "jti": "clientes-update-db"}
    return {"session": signer.dumps(payload)}


def test_update_cliente_persiste_con_placeholders_reales(admin_cookie):
    """El bug real: `descuento` (el campo que dispara `propagar_descuento_a_presupuestos`)
    y `notas` juntos en el mismo PATCH — antes de %s esto tiraba 500."""
    from database import get_db, init_db

    init_db()
    c = _client()
    created_id = None
    try:
        with get_db() as conn:
            with conn.transaction():
                created_id = conn.insert_returning(
                    "INSERT INTO clientes (nombre, apellido, email, descuento) "
                    "VALUES (%s, %s, %s, %s)",
                    ("Test", "PlaceholderBug", "test-placeholder-bug@example.com", 0),
                )

        r = c.patch(
            f"/api/clientes/{created_id}",
            json={"descuento": 12.5, "notas": "actualizado por test"},
            cookies=admin_cookie,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["descuento"] == 12.5
        assert body["notas"] == "actualizado por test"

        with get_db() as conn:
            row = conn.execute(
                "SELECT descuento, notas FROM clientes WHERE id=%s", (created_id,)
            ).fetchone()
            assert float(row["descuento"]) == 12.5
            assert row["notas"] == "actualizado por test"
    finally:
        if created_id is not None:
            with get_db() as conn:
                with conn.transaction():
                    conn.execute("DELETE FROM clientes WHERE id=%s", (created_id,))
