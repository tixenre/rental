"""DELETE /clientes/{id} contra Postgres real — candado del soft delete (#1251 Fase 2).

`commands.cliente.eliminar` dejó de hacer `DELETE FROM clientes` — ahora marca
`eliminado_at`. Este test clava el contrato: la fila sobrevive, la LISTA la
oculta por default, pero el fetch por id sigue funcionando (un pedido viejo
puede seguir apuntando a un cliente borrado).

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás `*_db.py`): se saltea
salvo `RESERVAS_DB_TEST=1` + `DATABASE_URL` a una base con 'test' en el nombre.
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
    payload = {"email": "admin@test.com", "role": "admin", "jti": "clientes-soft-delete-db"}
    return {"session": signer.dumps(payload)}


def test_eliminar_es_soft_delete_no_borra_la_fila(admin_cookie):
    from database import get_db, init_db

    init_db()
    c = _client()
    created_id = None
    try:
        with get_db() as conn:
            with conn.transaction():
                created_id = conn.insert_returning(
                    "INSERT INTO clientes (nombre, apellido, email) VALUES (%s, %s, %s)",
                    ("Test", "SoftDelete", "test-soft-delete@example.com"),
                )

        r = c.delete(f"/api/clientes/{created_id}", cookies=admin_cookie)
        assert r.status_code == 204, r.text

        # La fila sobrevive con eliminado_at seteado — no un DELETE físico.
        with get_db() as conn:
            row = conn.execute(
                "SELECT eliminado_at FROM clientes WHERE id=%s", (created_id,)
            ).fetchone()
            assert row is not None, "el DELETE borró la fila — tiene que ser soft delete"
            assert row["eliminado_at"] is not None

        # La lista lo oculta por default.
        r = c.get("/api/clientes", params={"q": "SoftDelete", "per_page": 50}, cookies=admin_cookie)
        assert r.status_code == 200
        assert created_id not in {item["id"] for item in r.json()["items"]}

        # El fetch por id lo sigue devolviendo (un pedido viejo puede apuntar acá).
        r = c.get(f"/api/clientes/{created_id}", cookies=admin_cookie)
        assert r.status_code == 200, r.text
        assert r.json()["id"] == created_id
    finally:
        if created_id is not None:
            with get_db() as conn:
                with conn.transaction():
                    conn.execute("DELETE FROM clientes WHERE id=%s", (created_id,))
