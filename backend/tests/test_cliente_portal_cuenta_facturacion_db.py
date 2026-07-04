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

Y candado de la vista RESUELTA (`nombre_legal`/`direccion_legal`/
`email_comunicacion`/`telefono_contacto`) que `GET /api/cliente/me` suma para
que el checkout (y cualquier otro consumidor) muestre "quién es" sin
reimplementar la regla RENAPER-si-verificado ni la de contacto canónico —
son la misma fuente que ya usan contrato/remito (`identity/__init__.py`,
`identity/contacts.py`), no una tercera copia en el front.

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


class TestPerfilImpuestosExigeCuit:
    """Regresión de bug real en producción: un cliente guardó `perfil_impuestos='monotributo'`
    desde el <select> del portal SIN pasar nunca por "Verificar" contra ARCA — Responsable
    Inscripto/Monotributo/Exento no existen sin CUIT en Argentina. La factura emitida después
    salió con el perfil guardado pero sin domicilio, sin confirmar. `cliente_update_me` ahora
    exige un CUIT con formato válido (11 dígitos) para cualquier perfil que no sea
    'consumidor_final' — el CUIT puede venir del mismo request o ya estar guardado."""

    def test_monotributo_sin_cuit_en_ningun_lado_se_rechaza(self, cliente_verificado_fixture):
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        r = _patch(client, {"perfil_impuestos": "monotributo"})
        assert r.status_code == 400, r.text

    def test_monotributo_con_cuit_en_el_mismo_request_se_acepta(self, cliente_verificado_fixture):
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        r = _patch(client, {"perfil_impuestos": "monotributo", "cuit": "27230938607"})
        assert r.status_code == 200, r.text
        assert r.json()["perfil_impuestos"] == "monotributo"

    def test_exento_con_cuit_ya_guardado_previamente_se_acepta(self, cliente_verificado_fixture):
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        r1 = _patch(client, {"cuit": "27230938607"})
        assert r1.status_code == 200, r1.text

        r2 = _patch(client, {"perfil_impuestos": "exento"})
        assert r2.status_code == 200, r2.text
        assert r2.json()["perfil_impuestos"] == "exento"

    def test_consumidor_final_no_exige_cuit(self, cliente_verificado_fixture):
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        r = _patch(client, {"perfil_impuestos": "consumidor_final"})
        assert r.status_code == 200, r.text


CLIENTE_ID_DISPLAY = 9_330_002
_COOKIE_DISPLAY = f"session={signer.dumps({'email': 'display-db@test.com', 'role': 'cliente', 'cliente_id': CLIENTE_ID_DISPLAY, 'jti': 'display-cli'})}"


@pytest.fixture
def cliente_no_verificado_fixture():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        conn.execute("DELETE FROM clientes WHERE id = %s", (CLIENTE_ID_DISPLAY,))
        conn.execute(
            """INSERT INTO clientes (id, nombre, apellido, email, telefono, direccion)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (CLIENTE_ID_DISPLAY, "Ana Base", "Gómez Base", "display-db@test.com",
             "1111-0000", "Calle Base 1"),
        )
        conn.commit()
        yield conn
    finally:
        conn.execute("DELETE FROM clientes WHERE id = %s", (CLIENTE_ID_DISPLAY,))
        conn.commit()
        conn.close()


@pytest.fixture
def cliente_verificado_datos_distintos_fixture():
    """Base != RENAPER (para que la preferencia sea observable) + un teléfono
    verificado por Didit distinto al autodeclarado."""
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        conn.execute("DELETE FROM clientes WHERE id = %s", (CLIENTE_ID_DISPLAY,))
        conn.execute(
            """INSERT INTO clientes
               (id, nombre, apellido, email, telefono, direccion,
                dni_validado_at, nombre_renaper, apellido_renaper, direccion_renaper)
               VALUES (%s, %s, %s, %s, %s, %s, now(), %s, %s, %s)""",
            (CLIENTE_ID_DISPLAY, "Ana Base", "Gómez Base", "display-db@test.com",
             "1111-0000", "Calle Base 1",
             "Ana Legal", "Gómez Legal", "Calle Legal 99"),
        )
        conn.execute(
            """INSERT INTO verified_contacts (cliente_id, kind, value, source, verified_at)
               VALUES (%s, 'phone', '+5492235559999', 'didit', now())""",
            (CLIENTE_ID_DISPLAY,),
        )
        conn.commit()
        yield conn
    finally:
        conn.execute("DELETE FROM clientes WHERE id = %s", (CLIENTE_ID_DISPLAY,))
        conn.commit()
        conn.close()


class TestVistaResueltaParaDisplay:
    def test_no_verificado_cae_al_dato_base(self, cliente_no_verificado_fixture):
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        r = client.get("/api/cliente/me", headers={"Cookie": _COOKIE_DISPLAY})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["nombre_legal"] == "Ana Base Gómez Base"
        assert body["direccion_legal"] == "Calle Base 1"
        assert body["telefono_contacto"] == "1111-0000"
        assert body["email_comunicacion"] == "display-db@test.com"

    def test_verificado_prefiere_renaper_y_contacto_verificado(
        self, cliente_verificado_datos_distintos_fixture,
    ):
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        r = client.get("/api/cliente/me", headers={"Cookie": _COOKIE_DISPLAY})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["nombre_legal"] == "Ana Legal Gómez Legal"
        assert body["direccion_legal"] == "Calle Legal 99"
        # El teléfono verificado por Didit gana al autodeclarado.
        assert body["telefono_contacto"] == "+5492235559999"
        # El mail de Google (base, disponible desde el alta) sigue siendo el preferido.
        assert body["email_comunicacion"] == "display-db@test.com"


class TestVerificarCuitContraArca:
    """`POST /api/cliente/facturacion/verificar-cuit` — el cliente solo tipea
    el CUIT; si ARCA lo confirma, condición IVA/razón social/domicilio (+ el
    propio CUIT) quedan persistidos al toque, sin que el cliente los
    autocomplete a mano. Se mockea `verificar_y_actualizar_receptor` (haría
    una llamada SOAP real a AFIP) — el candado es sobre el route, no sobre el
    cliente SOAP en sí (eso lo cubre test_facturacion_padron.py)."""

    _CUIT_VALIDO = "27230938607"  # mod-11 OK — ver test_cuit.py/anchor.py

    def test_encontrado_persiste_cuit_y_correcciones(
        self, cliente_no_verificado_fixture, monkeypatch,
    ):
        from fastapi.testclient import TestClient
        from services.facturacion.padron import PersonaArca

        persona = PersonaArca(
            cuit=self._CUIT_VALIDO, razon_social="Estudio SRL", nombre="", apellido="",
            domicilio="Av. Corrientes 1234", condicion_iva="responsable_inscripto",
            estado_clave="ACTIVO",
        )
        monkeypatch.setattr(
            "services.facturacion.padron.verificar_y_actualizar_receptor",
            lambda cuit, cliente_id, conn: persona,
        )

        client = TestClient(main.app)
        r = client.post(
            "/api/cliente/facturacion/verificar-cuit",
            json={"cuit": self._CUIT_VALIDO},
            headers={"Cookie": _COOKIE_DISPLAY},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body == {
            "encontrado": True,
            "cuit": self._CUIT_VALIDO,
            "perfil_impuestos": "responsable_inscripto",
            "razon_social": "Estudio SRL",
            "domicilio_fiscal": "Av. Corrientes 1234",
        }

        # El CUIT quedó persistido de verdad (lo escribe el route, no el mock).
        me = client.get("/api/cliente/me", headers={"Cookie": _COOKIE_DISPLAY})
        assert me.json()["cuit"] == self._CUIT_VALIDO

    def test_no_encontrado_no_persiste_nada(self, cliente_no_verificado_fixture, monkeypatch):
        from fastapi.testclient import TestClient

        def _falla(cuit, cliente_id, conn):
            raise RuntimeError("AFIP no pudo confirmar el CUIT (motivo de prueba)")

        monkeypatch.setattr(
            "services.facturacion.padron.verificar_y_actualizar_receptor", _falla,
        )

        client = TestClient(main.app)
        r = client.post(
            "/api/cliente/facturacion/verificar-cuit",
            json={"cuit": self._CUIT_VALIDO},
            headers={"Cookie": _COOKIE_DISPLAY},
        )
        assert r.status_code == 200, r.text  # best-effort: nunca un error HTTP
        body = r.json()
        assert body["encontrado"] is False
        assert "motivo de prueba" in body["motivo"]

        me = client.get("/api/cliente/me", headers={"Cookie": _COOKIE_DISPLAY})
        assert me.json()["cuit"] is None  # nada se tocó

    def test_cuit_con_formato_invalido_rechazado_sin_llamar_a_arca(
        self, cliente_no_verificado_fixture, monkeypatch,
    ):
        from fastapi.testclient import TestClient

        llamado = {"veces": 0}

        def _no_deberia_llamarse(cuit, cliente_id, conn):
            llamado["veces"] += 1
            raise AssertionError("no debería consultar ARCA con un CUIT mal formado")

        monkeypatch.setattr(
            "services.facturacion.padron.verificar_y_actualizar_receptor", _no_deberia_llamarse,
        )

        client = TestClient(main.app)
        r = client.post(
            "/api/cliente/facturacion/verificar-cuit",
            json={"cuit": "20304050607"},  # checksum mod-11 incorrecto
            headers={"Cookie": _COOKIE_DISPLAY},
        )
        assert r.status_code == 400, r.text
        assert llamado["veces"] == 0
