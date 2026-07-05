"""routes/productoras.py contra Postgres real (#1240) — CRUD admin + membership.

El admin es el único que crea/edita/vincula una productora (entidad fiscal
compartida entre cuentas de cliente, sin login propio). Toda alta/edición
verifica el CUIT contra el padrón real de ARCA (bloqueante) — se mockea
`resolver_persona` (haría una llamada SOAP real).

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás `*_db.py`): se saltea
salvo RESERVAS_DB_TEST=1 + DATABASE_URL con 'test' en el nombre.
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

_CUIT_1 = "30500002227"  # mod-11 OK
_CUIT_2 = "30500002235"  # mod-11 OK
_CLIENTE_ID = 9_340_001


def _client() -> TestClient:
    from routes.productoras import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


@pytest.fixture
def admin_cookie(monkeypatch):
    from auth.session import signer

    monkeypatch.setattr("auth.sessions_store.is_active", lambda jti: {"jti": jti})
    payload = {"email": "admin@test.com", "role": "admin", "jti": "productoras-db"}
    return {"session": signer.dumps(payload)}


@pytest.fixture(autouse=True)
def _limpiar():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        conn.execute("DELETE FROM clientes WHERE id = %s", (_CLIENTE_ID,))
        conn.execute(
            "INSERT INTO clientes (id, nombre, apellido, email) VALUES (%s, 'Ana', 'Gómez', 'productoras-db@test.com')",
            (_CLIENTE_ID,),
        )
        conn.execute("DELETE FROM productoras WHERE cuit IN (%s, %s)", (_CUIT_1, _CUIT_2))
        conn.commit()
        yield conn
    finally:
        conn.execute("DELETE FROM productoras WHERE cuit IN (%s, %s)", (_CUIT_1, _CUIT_2))
        conn.execute("DELETE FROM clientes WHERE id = %s", (_CLIENTE_ID,))
        conn.commit()
        conn.close()


def _persona(cuit, razon_social="Productora SA", condicion_iva="responsable_inscripto"):
    from services.facturacion.padron import PersonaArca

    return PersonaArca(
        cuit=cuit, razon_social=razon_social, nombre="", apellido="",
        domicilio="Calle 456", condicion_iva=condicion_iva, estado_clave="ACTIVO",
    )


def test_crear_productora_bloquea_si_afip_no_confirma(admin_cookie, monkeypatch):
    monkeypatch.setattr(
        "services.facturacion.padron.resolver_persona",
        lambda cuit, conn: _persona(cuit, condicion_iva=""),
    )
    client = _client()
    r = client.post("/api/admin/productoras", json={"cuit": _CUIT_1}, cookies=admin_cookie)
    assert r.status_code == 422, r.text

    lista = client.get("/api/admin/productoras", cookies=admin_cookie).json()
    assert all(p["cuit"] != _CUIT_1 for p in lista)


def test_crear_productora_ok_y_listar(admin_cookie, monkeypatch):
    monkeypatch.setattr(
        "services.facturacion.padron.resolver_persona",
        lambda cuit, conn: _persona(cuit),
    )
    client = _client()
    r = client.post(
        "/api/admin/productoras", json={"cuit": _CUIT_1, "notas": "Ref: rodaje X"},
        cookies=admin_cookie,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["razon_social"] == "Productora SA"
    assert body["notas"] == "Ref: rodaje X"

    lista = client.get("/api/admin/productoras", cookies=admin_cookie).json()
    assert any(p["cuit"] == _CUIT_1 for p in lista)

    filtrada = client.get("/api/admin/productoras?q=Productora", cookies=admin_cookie).json()
    assert any(p["cuit"] == _CUIT_1 for p in filtrada)
    sin_match = client.get("/api/admin/productoras?q=Zzzznomatch", cookies=admin_cookie).json()
    assert all(p["cuit"] != _CUIT_1 for p in sin_match)


def test_agregar_y_quitar_miembro(admin_cookie, monkeypatch):
    monkeypatch.setattr(
        "services.facturacion.padron.resolver_persona",
        lambda cuit, conn: _persona(cuit),
    )
    client = _client()
    productora_id = client.post(
        "/api/admin/productoras", json={"cuit": _CUIT_2}, cookies=admin_cookie,
    ).json()["id"]

    r = client.post(
        f"/api/admin/productoras/{productora_id}/miembros",
        json={"cliente_id": _CLIENTE_ID},
        cookies=admin_cookie,
    )
    assert r.status_code == 201, r.text

    # Idempotente: agregarlo de nuevo no falla ni duplica.
    r2 = client.post(
        f"/api/admin/productoras/{productora_id}/miembros",
        json={"cliente_id": _CLIENTE_ID},
        cookies=admin_cookie,
    )
    assert r2.status_code == 201, r2.text

    detalle = client.get(f"/api/admin/productoras/{productora_id}", cookies=admin_cookie).json()
    assert len(detalle["miembros"]) == 1
    assert detalle["miembros"][0]["id"] == _CLIENTE_ID

    r3 = client.delete(
        f"/api/admin/productoras/{productora_id}/miembros/{_CLIENTE_ID}",
        cookies=admin_cookie,
    )
    assert r3.status_code == 204, r3.text

    detalle2 = client.get(f"/api/admin/productoras/{productora_id}", cookies=admin_cookie).json()
    assert detalle2["miembros"] == []


def test_agregar_miembro_a_productora_inexistente_404(admin_cookie):
    client = _client()
    r = client.post(
        "/api/admin/productoras/999999/miembros",
        json={"cliente_id": _CLIENTE_ID},
        cookies=admin_cookie,
    )
    assert r.status_code == 404, r.text


def test_reverificar_productora_refresca_datos(admin_cookie, monkeypatch):
    client = _client()
    monkeypatch.setattr(
        "services.facturacion.padron.resolver_persona",
        lambda cuit, conn: _persona(cuit, razon_social="Nombre Viejo SA"),
    )
    productora_id = client.post(
        "/api/admin/productoras", json={"cuit": _CUIT_1}, cookies=admin_cookie,
    ).json()["id"]

    monkeypatch.setattr(
        "services.facturacion.padron.resolver_persona",
        lambda cuit, conn: _persona(cuit, razon_social="Nombre Real SA"),
    )
    r = client.patch(
        f"/api/admin/productoras/{productora_id}", json={"reverificar": True}, cookies=admin_cookie,
    )
    assert r.status_code == 200, r.text
    assert r.json()["razon_social"] == "Nombre Real SA"
