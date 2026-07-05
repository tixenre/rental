"""Candado: `PATCH /api/cliente/me` NO bloquea los datos PERSONALES tras la
verificación de identidad, solo los que certifica RENAPER (#1209).

Los datos FISCALES (cuit/perfil_impuestos/razon_social/domicilio_fiscal/
email_facturacion) YA NO se editan por `cliente_update_me` (#1240 — cerraba
un fallback de entrada manual sin verificar contra AFIP): viven en los
endpoints de `cliente_perfiles_fiscales`
(`GET/POST /api/cliente/facturacion/perfiles`,
`PATCH .../perfiles/{id}/default`), bloqueantes contra el padrón real de
ARCA. `POST /api/cliente/facturacion/verificar-cuit` sigue existiendo como
delegado legacy del POST nuevo.

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
        conn.execute("DELETE FROM cliente_perfiles_fiscales WHERE cliente_id = %s", (CLIENTE_ID,))
        conn.execute("DELETE FROM clientes WHERE id = %s", (CLIENTE_ID,))
        conn.commit()
        conn.close()


def _patch(client, body):
    return client.patch("/api/cliente/me", json=body, headers={"Cookie": _COOKIE})


class TestFacturacionYaNoEditablePorCuentaMe:
    """#1240: los 5 campos fiscales dejaron de existir en `PerfilUpdate` — un
    PATCH que solo los mande no tiene NINGÚN campo real que aplicar, así que
    cae en "Sin cambios" (400). Antes de #1240 esto devolvía 200 y los
    persistía sin pasar por AFIP."""

    def test_perfil_impuestos_cuit_y_razon_social_ya_no_se_aplican(self, cliente_verificado_fixture):
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        r = _patch(client, {
            "perfil_impuestos": "responsable_inscripto",
            "cuit": "27230938607",
            "razon_social": "Estudio SRL",
        })
        assert r.status_code == 400, r.text
        assert "Sin cambios" in r.text

        me = client.get("/api/cliente/me", headers={"Cookie": _COOKIE})
        assert me.json()["perfil_impuestos"] == "consumidor_final"  # sin tocar
        assert me.json()["cuit"] is None  # sin tocar

    def test_domicilio_fiscal_y_email_facturacion_ya_no_se_aplican(self, cliente_verificado_fixture):
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        r = _patch(client, {
            "domicilio_fiscal": "Av. Siempre Viva 123",
            "email_facturacion": "facturas@estudio.com",
        })
        assert r.status_code == 400, r.text

    def test_apodo_y_telefono_mezclados_con_fiscales_solo_aplican_los_reales(
        self, cliente_verificado_fixture,
    ):
        """Si el body mezcla un campo real (`apodo`) con campos fiscales ya
        eliminados, el real SÍ se aplica — Pydantic simplemente ignora las
        claves que `PerfilUpdate` ya no declara."""
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        r = _patch(client, {"apodo": "Anita", "perfil_impuestos": "monotributo"})
        assert r.status_code == 200, r.text
        assert r.json()["apodo"] == "Anita"
        assert r.json()["perfil_impuestos"] == "consumidor_final"  # ignorado, sin tocar

    def test_nombre_apellido_direccion_siguen_bloqueados_verificado(self, cliente_verificado_fixture):
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        for campo, valor in (
            ("nombre", "Otro"), ("apellido", "Otro"), ("direccion", "Otra dirección"),
        ):
            r = _patch(client, {campo: valor})
            assert r.status_code == 403, f"{campo}: {r.text}"

    def test_telefono_y_apodo_no_se_bloquean_verificado(self, cliente_verificado_fixture):
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        r = _patch(client, {"telefono": "223 555-1234", "apodo": "Anita"})
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
        conn.execute(
            "DELETE FROM cliente_perfiles_fiscales WHERE cliente_id = %s", (CLIENTE_ID_DISPLAY,)
        )
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
    """`POST /api/cliente/facturacion/verificar-cuit` — ⏰ LEGACY, delegado fino
    de `POST /api/cliente/facturacion/perfiles` (#1240). El cliente solo
    tipea el CUIT; si ARCA lo confirma, condición IVA/razón social/domicilio
    quedan persistidos en `cliente_perfiles_fiscales` (+ sincronizados en
    `clientes` por ser el primer/default perfil), sin que el cliente los
    autocomplete a mano. Se mockea `resolver_persona` (haría una llamada SOAP
    real a AFIP) — el candado es sobre el route + la capa de servicio nueva,
    no sobre el cliente SOAP en sí (eso lo cubre test_facturacion_padron.py)."""

    _CUIT_VALIDO = "27230938607"  # mod-11 OK — ver test_cuit.py/anchor.py

    def _persona(self):
        from services.facturacion.padron import PersonaArca

        return PersonaArca(
            cuit=self._CUIT_VALIDO, razon_social="Estudio SRL", nombre="", apellido="",
            domicilio="Av. Corrientes 1234", condicion_iva="responsable_inscripto",
            estado_clave="ACTIVO",
        )

    def test_encontrado_persiste_cuit_y_correcciones(
        self, cliente_no_verificado_fixture, monkeypatch,
    ):
        from fastapi.testclient import TestClient

        monkeypatch.setattr(
            "services.facturacion.padron.resolver_persona",
            lambda cuit, conn: self._persona(),
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

        # El CUIT quedó persistido de verdad — como perfil default (primer perfil).
        me = client.get("/api/cliente/me", headers={"Cookie": _COOKIE_DISPLAY})
        assert me.json()["cuit"] == self._CUIT_VALIDO

    def test_no_encontrado_no_persiste_nada(self, cliente_no_verificado_fixture, monkeypatch):
        from fastapi.testclient import TestClient

        def _falla(cuit, conn):
            raise RuntimeError("AFIP no pudo confirmar el CUIT (motivo de prueba)")

        monkeypatch.setattr("services.facturacion.padron.resolver_persona", _falla)

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

        def _no_deberia_llamarse(cuit, conn):
            llamado["veces"] += 1
            raise AssertionError("no debería consultar ARCA con un CUIT mal formado")

        monkeypatch.setattr("services.facturacion.padron.resolver_persona", _no_deberia_llamarse)

        client = TestClient(main.app)
        r = client.post(
            "/api/cliente/facturacion/verificar-cuit",
            json={"cuit": "20304050607"},  # checksum mod-11 incorrecto
            headers={"Cookie": _COOKIE_DISPLAY},
        )
        assert r.status_code == 400, r.text
        assert llamado["veces"] == 0


class TestPerfilesFiscalesMultiples:
    """`GET/POST /api/cliente/facturacion/perfiles` +
    `PATCH .../perfiles/{id}/default` (#1240) — múltiples CUIT propios por
    cliente, cada uno nacido de una verificación real contra ARCA."""

    _CUIT_1 = "27230938607"  # mod-11 OK
    _CUIT_2 = "20301234563"  # mod-11 OK

    def _persona(self, cuit, razon_social="Empresa SA", condicion_iva="responsable_inscripto"):
        from services.facturacion.padron import PersonaArca

        return PersonaArca(
            cuit=cuit, razon_social=razon_social, nombre="", apellido="",
            domicilio="Calle 123", condicion_iva=condicion_iva, estado_clave="ACTIVO",
        )

    def test_crear_perfil_bloquea_si_afip_no_clasifica(
        self, cliente_no_verificado_fixture, monkeypatch,
    ):
        from fastapi.testclient import TestClient

        monkeypatch.setattr(
            "services.facturacion.padron.resolver_persona",
            lambda cuit, conn: self._persona(cuit, condicion_iva=""),
        )
        client = TestClient(main.app)
        r = client.post(
            "/api/cliente/facturacion/perfiles",
            json={"cuit": self._CUIT_1},
            headers={"Cookie": _COOKIE_DISPLAY},
        )
        assert r.status_code == 422, r.text

        lista = client.get(
            "/api/cliente/facturacion/perfiles", headers={"Cookie": _COOKIE_DISPLAY},
        ).json()
        assert lista == []

    def test_primer_perfil_es_default_y_sincroniza_clientes(
        self, cliente_no_verificado_fixture, monkeypatch,
    ):
        from fastapi.testclient import TestClient

        monkeypatch.setattr(
            "services.facturacion.padron.resolver_persona",
            lambda cuit, conn: self._persona(cuit),
        )
        client = TestClient(main.app)
        r = client.post(
            "/api/cliente/facturacion/perfiles",
            json={"cuit": self._CUIT_1, "etiqueta": "Personal"},
            headers={"Cookie": _COOKIE_DISPLAY},
        )
        assert r.status_code == 201, r.text
        assert r.json()["es_default"] is True
        assert r.json()["etiqueta"] == "Personal"

        me = client.get("/api/cliente/me", headers={"Cookie": _COOKIE_DISPLAY}).json()
        assert me["cuit"] == self._CUIT_1
        assert me["perfil_impuestos"] == "responsable_inscripto"

    def test_segundo_perfil_no_pisa_el_default(self, cliente_no_verificado_fixture, monkeypatch):
        from fastapi.testclient import TestClient

        monkeypatch.setattr(
            "services.facturacion.padron.resolver_persona",
            lambda cuit, conn: self._persona(cuit),
        )
        client = TestClient(main.app)
        client.post(
            "/api/cliente/facturacion/perfiles",
            json={"cuit": self._CUIT_1},
            headers={"Cookie": _COOKIE_DISPLAY},
        )
        r2 = client.post(
            "/api/cliente/facturacion/perfiles",
            json={"cuit": self._CUIT_2, "etiqueta": "Productora personal"},
            headers={"Cookie": _COOKIE_DISPLAY},
        )
        assert r2.status_code == 201, r2.text
        assert r2.json()["es_default"] is False

        lista = client.get(
            "/api/cliente/facturacion/perfiles", headers={"Cookie": _COOKIE_DISPLAY},
        ).json()
        assert len(lista) == 2
        defaults = [p for p in lista if p["es_default"]]
        assert len(defaults) == 1
        assert defaults[0]["cuit"] == self._CUIT_1

    def test_marcar_default_desmarca_el_anterior(self, cliente_no_verificado_fixture, monkeypatch):
        from fastapi.testclient import TestClient

        monkeypatch.setattr(
            "services.facturacion.padron.resolver_persona",
            lambda cuit, conn: self._persona(cuit),
        )
        client = TestClient(main.app)
        client.post(
            "/api/cliente/facturacion/perfiles",
            json={"cuit": self._CUIT_1},
            headers={"Cookie": _COOKIE_DISPLAY},
        )
        p2 = client.post(
            "/api/cliente/facturacion/perfiles",
            json={"cuit": self._CUIT_2},
            headers={"Cookie": _COOKIE_DISPLAY},
        ).json()

        r = client.patch(
            f"/api/cliente/facturacion/perfiles/{p2['id']}/default",
            headers={"Cookie": _COOKIE_DISPLAY},
        )
        assert r.status_code == 200, r.text

        lista = client.get(
            "/api/cliente/facturacion/perfiles", headers={"Cookie": _COOKIE_DISPLAY},
        ).json()
        defaults = [p for p in lista if p["es_default"]]
        assert len(defaults) == 1
        assert defaults[0]["cuit"] == self._CUIT_2

    def test_marcar_default_de_perfil_ajeno_404(self, cliente_no_verificado_fixture):
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        r = client.patch(
            "/api/cliente/facturacion/perfiles/999999/default",
            headers={"Cookie": _COOKIE_DISPLAY},
        )
        assert r.status_code == 404, r.text


class TestProductorasSoloLecturaDelCliente:
    """`GET /api/cliente/productoras` (#1240) — solo lectura, devuelve
    únicamente las productoras a las que el cliente autenticado está
    vinculado (las crea/edita/vincula el admin, `routes/productoras.py`)."""

    @pytest.fixture
    def dos_clientes_y_productoras(self):
        from database import get_db, init_db

        init_db()
        conn = get_db()
        otro_id = CLIENTE_ID_DISPLAY + 1
        try:
            conn.execute("DELETE FROM clientes WHERE id IN (%s, %s)", (CLIENTE_ID_DISPLAY, otro_id))
            conn.execute(
                """INSERT INTO clientes (id, nombre, apellido, email)
                   VALUES (%s, 'Ana Base', 'Gómez Base', 'display-db@test.com'),
                          (%s, 'Otro', 'Cliente', 'otro-cliente@test.com')""",
                (CLIENTE_ID_DISPLAY, otro_id),
            )
            conn.execute("DELETE FROM productoras WHERE cuit IN ('30500000001', '30500000002')")
            conn.execute(
                """INSERT INTO productoras (cuit, perfil_impuestos, razon_social)
                   VALUES ('30500000001', 'responsable_inscripto', 'Productora Vinculada SA'),
                          ('30500000002', 'responsable_inscripto', 'Productora Ajena SA')
                   RETURNING id"""
            )
            ids = [
                r["id"] for r in conn.execute(
                    "SELECT id FROM productoras WHERE cuit IN ('30500000001', '30500000002') ORDER BY cuit"
                ).fetchall()
            ]
            conn.execute(
                "INSERT INTO productora_miembros (productora_id, cliente_id) VALUES (%s, %s)",
                (ids[0], CLIENTE_ID_DISPLAY),
            )
            conn.execute(
                "INSERT INTO productora_miembros (productora_id, cliente_id) VALUES (%s, %s)",
                (ids[1], otro_id),
            )
            conn.commit()
            yield
        finally:
            conn.execute("DELETE FROM productoras WHERE cuit IN ('30500000001', '30500000002')")
            conn.execute("DELETE FROM clientes WHERE id IN (%s, %s)", (CLIENTE_ID_DISPLAY, otro_id))
            conn.commit()
            conn.close()

    def test_solo_devuelve_las_productoras_del_cliente_autenticado(
        self, dos_clientes_y_productoras,
    ):
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        r = client.get("/api/cliente/productoras", headers={"Cookie": _COOKIE_DISPLAY})
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body) == 1
        assert body[0]["razon_social"] == "Productora Vinculada SA"
