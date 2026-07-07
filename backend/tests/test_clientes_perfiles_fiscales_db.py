"""`GET /clientes/{id}/perfiles-fiscales` (#1240) — solo lectura, para la
ficha admin: perfiles fiscales personales + productoras vinculadas del
cliente. Contra Postgres real (opt-in, mismo gating que los demás `*_db.py`).
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

CLIENTE_ID = 9_370_001
CUIT_PRODUCTORA = "30500003330"


def _client() -> TestClient:
    from routes.clientes import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


@pytest.fixture
def admin_cookie(monkeypatch):
    from auth.session import signer

    monkeypatch.setattr("auth.queries.sessions.is_active", lambda jti: {"jti": jti})
    payload = {"email": "admin@test.com", "role": "admin", "jti": "clientes-perfiles-db"}
    return {"session": signer.dumps(payload)}


@pytest.fixture
def datos():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        conn.execute("DELETE FROM clientes WHERE id = %s", (CLIENTE_ID,))
        conn.execute(
            "INSERT INTO clientes (id, nombre, apellido, email) VALUES (%s, 'Ana', 'Gómez', 'perfiles-fiscales-db@test.com')",
            (CLIENTE_ID,),
        )
        conn.execute(
            """INSERT INTO cliente_perfiles_fiscales
                   (cliente_id, cuit, perfil_impuestos, razon_social, es_default)
               VALUES (%s, '20111111112', 'monotributo', 'Perfil Personal', TRUE)""",
            (CLIENTE_ID,),
        )
        conn.execute("DELETE FROM productoras WHERE cuit = %s", (CUIT_PRODUCTORA,))
        productora_id = conn.insert_returning(
            "INSERT INTO productoras (cuit, perfil_impuestos, razon_social) "
            "VALUES (%s, 'responsable_inscripto', 'Productora Vinculada')",
            (CUIT_PRODUCTORA,),
        )
        conn.execute(
            "INSERT INTO productora_miembros (productora_id, cliente_id) VALUES (%s, %s)",
            (productora_id, CLIENTE_ID),
        )
        conn.commit()
        yield
    finally:
        conn.execute("DELETE FROM productora_miembros WHERE cliente_id = %s", (CLIENTE_ID,))
        conn.execute("DELETE FROM productoras WHERE cuit = %s", (CUIT_PRODUCTORA,))
        conn.execute("DELETE FROM cliente_perfiles_fiscales WHERE cliente_id = %s", (CLIENTE_ID,))
        conn.execute("DELETE FROM clientes WHERE id = %s", (CLIENTE_ID,))
        conn.commit()
        conn.close()


def test_devuelve_perfiles_y_productoras_del_cliente(datos, admin_cookie):
    client = _client()
    r = client.get(f"/api/clientes/{CLIENTE_ID}/perfiles-fiscales", cookies=admin_cookie)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["perfiles"]) == 1
    assert body["perfiles"][0]["razon_social"] == "Perfil Personal"
    assert len(body["productoras"]) == 1
    assert body["productoras"][0]["razon_social"] == "Productora Vinculada"


def test_cliente_inexistente_404(admin_cookie):
    client = _client()
    r = client.get("/api/clientes/999999/perfiles-fiscales", cookies=admin_cookie)
    assert r.status_code == 404, r.text


def test_productora_borrador_visible_en_ficha_admin_pero_no_facturable(datos, admin_cookie):
    """#1251 Fase 3: la ficha admin (`resumen_fiscal`, sin `solo_facturables`)
    ve TODAS las productoras, borrador incluido; `solo_facturables=True`
    (el que consume el checkout) las excluye — probado directo contra la
    query, no vía HTTP, porque el endpoint del portal exige sesión cliente."""
    from clientes.queries.fiscal import productoras_vinculadas
    from database import get_db

    with get_db() as conn:
        conn.execute(
            "INSERT INTO productoras (nombre) VALUES ('Borrador de Ana')",
        )
        borrador_id = conn.execute(
            "SELECT id FROM productoras WHERE nombre = 'Borrador de Ana'"
        ).fetchone()["id"]
        conn.execute(
            "INSERT INTO productora_miembros (productora_id, cliente_id) VALUES (%s, %s)",
            (borrador_id, CLIENTE_ID),
        )
        conn.commit()
        try:
            todas = productoras_vinculadas(conn, CLIENTE_ID)
            assert any(p["id"] == borrador_id for p in todas)

            facturables = productoras_vinculadas(conn, CLIENTE_ID, solo_facturables=True)
            assert all(p["id"] != borrador_id for p in facturables)
            assert any(p["razon_social"] == "Productora Vinculada" for p in facturables)
        finally:
            conn.execute("DELETE FROM productora_miembros WHERE productora_id = %s", (borrador_id,))
            conn.execute("DELETE FROM productoras WHERE id = %s", (borrador_id,))
            conn.commit()
