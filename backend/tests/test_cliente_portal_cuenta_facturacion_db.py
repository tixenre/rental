"""Candado: `PATCH /api/cliente/me` NO bloquea los datos FISCALES tras la
verificación de identidad, solo los que certifica RENAPER (#1209 — bug
encontrado al usar `FacturacionModal` desde el checkout: un cliente
verificado no podía cambiar su perfil_impuestos/CUIT, aunque el propio hint
del form dice "puede diferir del CUIL verificado de tu identidad").

Solo `nombre`/`apellido`/`direccion` quedan bloqueados post-verificación —
`perfil_impuestos`/`cuit`/`razon_social`/`domicilio_fiscal`/`email_facturacion`
tienen que poder actualizarse siempre.

También candado del checksum de CUIT/CUIL (mod-11, `identity.anchor.cuil_valido`)
que se sumó al mismo endpoint — un CUIT mal formado se rechaza con 400.

Contra Postgres real: `cliente_verificado` hace un SELECT directo a
`clientes.dni_validado_at`. OPT-IN y SEGURO POR DEFECTO (mismo gating que
los demás *_db.py): se saltea salvo RESERVAS_DB_TEST=1 + DATABASE_URL con
'test' en el nombre.
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

import main  # noqa: E402
from auth.session import signer  # noqa: E402

CLIENTE_ID = 9_330_001

_COOKIE = f"session={signer.dumps({'email': 'facturacion-db@test.com', 'role': 'cliente', 'cliente_id': CLIENTE_ID, 'jti': 'facturacion-cli'})}"


@pytest.fixture(autouse=True)
def _sessions_active(monkeypatch):
    monkeypatch.setattr("auth.sessions_store.is_active", lambda jti: {"jti": jti})


@pytest.fixture
def cliente_verificado_fixture():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        conn.execute("DELETE FROM clientes WHERE id = %s", (CLIENTE_ID,))
        conn.execute(
            """INSERT INTO clientes
               (id, nombre, apellido, email, perfil_impuestos, cuit,
                dni_validado_at, nombre_renaper, apellido_renaper)
               VALUES (%s, %s, %s, %s, %s, %s, now(), %s, %s)""",
            (CLIENTE_ID, "Ana", "Gómez", "facturacion-db@test.com",
             "consumidor_final", None, "Ana", "Gómez"),
        )
        conn.commit()
        yield conn
    finally:
        conn.execute("DELETE FROM clientes WHERE id = %s", (CLIENTE_ID,))
        conn.commit()
        conn.close()


def _patch(client, body):
    return client.patch("/api/cliente/me", json=body, headers={"Cookie": _COOKIE})


class TestFacturacionEditablePostVerificacion:
    def test_perfil_impuestos_y_cuit_se_pueden_cambiar_verificado(self, cliente_verificado_fixture):
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        r = _patch(client, {
            "perfil_impuestos": "responsable_inscripto",
            "cuit": "27230938607",  # CUIT válido (mod-11) — ver test_cuit_invalido_rechazado abajo
            "razon_social": "Estudio SRL",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["perfil_impuestos"] == "responsable_inscripto"
        assert body["cuit"] == "27230938607"
        assert body["razon_social"] == "Estudio SRL"

    def test_domicilio_fiscal_y_email_facturacion_se_pueden_cambiar_verificado(
        self, cliente_verificado_fixture,
    ):
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        r = _patch(client, {
            "domicilio_fiscal": "Av. Siempre Viva 123",
            "email_facturacion": "facturas@estudio.com",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["domicilio_fiscal"] == "Av. Siempre Viva 123"
        assert body["email_facturacion"] == "facturas@estudio.com"

    def test_nombre_apellido_direccion_siguen_bloqueados_verificado(self, cliente_verificado_fixture):
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        for campo, valor in (
            ("nombre", "Otro"), ("apellido", "Otro"), ("direccion", "Otra dirección"),
        ):
            r = _patch(client, {campo: valor})
            assert r.status_code == 403, f"{campo}: {r.text}"

    def test_cuit_invalido_rechazado(self, cliente_verificado_fixture):
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        r = _patch(client, {"cuit": "20304050607"})  # checksum mod-11 incorrecto
        assert r.status_code == 400, r.text

    def test_cuit_vacio_limpia_el_campo(self, cliente_verificado_fixture):
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        r = _patch(client, {"cuit": ""})
        assert r.status_code == 200, r.text
        assert r.json()["cuit"] is None
