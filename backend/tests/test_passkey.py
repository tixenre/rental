"""Tests del login con passkey (WebAuthn/FIDO2).

Cubre las piezas puras del motor (`services/passkeys`) y la lógica de los
endpoints (`routes/auth_passkey`) sin DB ni cripto real: se mockea la
verificación de la lib (`webauthn`) y el `store`, así se prueba lo que es
nuestro — resolución de dueño, minteo de la MISMA cookie de sesión, rechazo de
replay, 403 de no-admin, binding del challenge y scoping anti-IDOR.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.session import signer
from auth import auth_passkey_router as router
from auth.passkey import ceremonies
from auth.passkey import config as cfg
from auth.passkey import store
from auth.ratelimit import _failures as _rl_failures

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _stub_sessions_store(monkeypatch):
    """El login con passkey mintea la sesión vía `_make_session_response` (registra
    fila server-side) y ahora pasa por el rate-limit por IP. Stubbeamos el store de
    sesiones (sin DB) y limpiamos el contador de rate-limit entre tests (estado
    global compartido con OAuth/staging)."""
    monkeypatch.setattr("auth.sessions_store.create_session", lambda **kw: "stub-jti")
    monkeypatch.setattr("auth.sessions_store.is_active",
                        lambda jti: {"jti": jti} if jti else None)
    _rl_failures.clear()


# ── Piezas puras ──────────────────────────────────────────────────────────────

class TestEsReplay:
    def test_sincronizada_cero_cero_no_es_replay(self):
        # Passkeys de iCloud/Google reportan sign_count 0 siempre.
        assert ceremonies.es_replay(0, 0) is False

    def test_contador_avanza_no_es_replay(self):
        assert ceremonies.es_replay(5, 6) is False

    def test_contador_igual_es_replay(self):
        assert ceremonies.es_replay(6, 6) is True

    def test_contador_retrocede_es_replay(self):
        assert ceremonies.es_replay(6, 5) is True


class TestUserHandle:
    def test_estable_por_dueno(self):
        assert ceremonies.user_handle_for("cliente", "42") == ceremonies.user_handle_for("cliente", "42")

    def test_distinto_por_tipo_y_clave(self):
        assert ceremonies.user_handle_for("cliente", "42") != ceremonies.user_handle_for("admin", "42")
        assert ceremonies.user_handle_for("cliente", "42") != ceremonies.user_handle_for("cliente", "43")

    def test_no_expone_la_clave_cruda(self):
        uh = ceremonies.user_handle_for("cliente", "cliente@ejemplo.com")
        assert "cliente@ejemplo.com" not in uh


class TestChallengeCookie:
    def test_roundtrip(self):
        tok = ceremonies.sign_challenge("chal-abc", ot="admin", ok="x@y.com")
        data = ceremonies.read_challenge(tok)
        assert data["challenge"] == "chal-abc"
        assert data["ot"] == "admin" and data["ok"] == "x@y.com"

    def test_tampered_devuelve_none(self):
        tok = ceremonies.sign_challenge("chal-abc")
        assert ceremonies.read_challenge(tok + "x") is None

    def test_vacio_devuelve_none(self):
        assert ceremonies.read_challenge("") is None


class TestRpId:
    def test_dev_local_es_localhost(self, monkeypatch):
        monkeypatch.delenv("WEBAUTHN_RP_ID", raising=False)
        monkeypatch.setattr(cfg.settings, "RAILWAY_ENVIRONMENT", None)
        assert cfg.rp_id() == "localhost"

    def test_railway_deriva_apex_de_site_url(self, monkeypatch):
        monkeypatch.delenv("WEBAUTHN_RP_ID", raising=False)
        monkeypatch.setattr(cfg.settings, "RAILWAY_ENVIRONMENT", "production")
        monkeypatch.setattr(cfg.settings, "SITE_URL", "https://www.ramblarental.com.ar")
        assert cfg.rp_id() == "ramblarental.com.ar"

    def test_override_explicito(self, monkeypatch):
        monkeypatch.setenv("WEBAUTHN_RP_ID", "custom.example.com")
        assert cfg.rp_id() == "custom.example.com"


# ── Endpoints (lógica, sin DB ni cripto real) ────────────────────────────────

def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _admin_session() -> str:
    # jti obligatorio (get_session exige sesión en la allowlist); el stub de
    # is_active la da por activa.
    return signer.dumps({"email": "admin@test.com", "name": "Admin", "jti": "test-admin"})


def _cliente_session(cliente_id: int = 42) -> str:
    return signer.dumps(
        {"email": "c@x.com", "name": "Cli", "role": "cliente", "cliente_id": cliente_id, "jti": "test-cli"}
    )


class TestLoginComplete:
    def _setup(self, monkeypatch, *, row, new_count):
        monkeypatch.setattr(store, "get_by_credential_id", lambda cid: row)
        monkeypatch.setattr(ceremonies, "verify_authentication", lambda **kw: new_count)
        monkeypatch.setattr(store, "update_sign_count", lambda *a, **k: None)

    def test_admin_mintea_misma_cookie(self, monkeypatch):
        self._setup(monkeypatch, row={
            "id": 1, "owner_type": "admin", "owner_email": "admin@test.com",
            "cliente_id": None, "public_key": "pk", "sign_count": 5,
        }, new_count=6)
        c = _client()
        c.cookies.set("wa_chal_auth", ceremonies.sign_challenge("chal"))
        r = c.post("/auth/passkey/login/complete", json={"credential": {"id": "credid"}})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert "session" in r.cookies  # minteó la sesión de admin

    def test_email_no_admin_403(self, monkeypatch):
        self._setup(monkeypatch, row={
            "id": 1, "owner_type": "admin", "owner_email": "exadmin@x.com",
            "cliente_id": None, "public_key": "pk", "sign_count": 5,
        }, new_count=6)
        c = _client()
        c.cookies.set("wa_chal_auth", ceremonies.sign_challenge("chal"))
        r = c.post("/auth/passkey/login/complete", json={"credential": {"id": "credid"}})
        assert r.status_code == 403

    def test_replay_rechazado_401(self, monkeypatch):
        # new_count == stored (5) y no es 0/0 → replay.
        self._setup(monkeypatch, row={
            "id": 1, "owner_type": "admin", "owner_email": "admin@test.com",
            "cliente_id": None, "public_key": "pk", "sign_count": 5,
        }, new_count=5)
        c = _client()
        c.cookies.set("wa_chal_auth", ceremonies.sign_challenge("chal"))
        r = c.post("/auth/passkey/login/complete", json={"credential": {"id": "credid"}})
        assert r.status_code == 401

    def test_credencial_desconocida_401(self, monkeypatch):
        monkeypatch.setattr(store, "get_by_credential_id", lambda cid: None)
        c = _client()
        c.cookies.set("wa_chal_auth", ceremonies.sign_challenge("chal"))
        r = c.post("/auth/passkey/login/complete", json={"credential": {"id": "nope"}})
        assert r.status_code == 401

    def test_sin_challenge_cookie_400(self):
        c = _client()
        r = c.post("/auth/passkey/login/complete", json={"credential": {"id": "credid"}})
        assert r.status_code == 400

    def test_cliente_mintea_sesion_con_role(self, monkeypatch):
        self._setup(monkeypatch, row={
            "id": 2, "owner_type": "cliente", "owner_email": "c@x.com",
            "cliente_id": 42, "public_key": "pk", "sign_count": 0,
        }, new_count=0)

        class _Ctx:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def execute(self, sql, params=()): return self
            def fetchone(self): return {"id": 42, "email": "c@x.com", "nombre": "Cli", "apellido": "Ente"}

        monkeypatch.setattr("auth.passkey.routes.get_db", lambda: _Ctx())
        c = _client()
        c.cookies.set("wa_chal_auth", ceremonies.sign_challenge("chal"))
        r = c.post("/auth/passkey/login/complete", json={"credential": {"id": "credid"}})
        assert r.status_code == 200
        assert "session" in r.cookies
        # La sesión minteada lleva role=cliente + cliente_id (la lee get_session).
        sess = signer.loads(r.cookies["session"])
        assert sess["role"] == "cliente" and sess["cliente_id"] == 42


class TestRateLimit:
    def test_demasiados_fallos_cortan_con_429(self, monkeypatch):
        # Cada intento falla (credencial desconocida → 401) y suma al contador por IP.
        # _RATE_MAX=10 → los primeros 10 fallan 401; el 11º lo corta el rate-limit (429).
        monkeypatch.setattr(store, "get_by_credential_id", lambda cid: None)
        c = _client()
        c.cookies.set("wa_chal_auth", ceremonies.sign_challenge("chal"))
        codes = [
            c.post("/auth/passkey/login/complete", json={"credential": {"id": "x"}}).status_code
            for _ in range(11)
        ]
        assert codes[:10] == [401] * 10
        assert codes[10] == 429


class TestRegisterGuards:
    def test_admin_begin_sin_sesion_401(self):
        assert _client().post("/auth/passkey/register/begin").status_code == 401

    def test_cliente_begin_sin_sesion_401(self):
        assert _client().post("/cliente/auth/passkey/register/begin").status_code == 401


class TestRegisterComplete:
    def test_admin_guarda_credencial(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(ceremonies, "verify_registration",
                            lambda **kw: {"credential_id": "cid", "public_key": "pk",
                                          "sign_count": 0, "aaguid": "aa"})
        monkeypatch.setattr(store, "insert_credential",
                            lambda **kw: captured.update(kw) or 7)
        c = _client()
        c.cookies.set("session", _admin_session())
        c.cookies.set("wa_chal_reg",
                      ceremonies.sign_challenge("chal", ot="admin", ok="admin@test.com", uh="uh"))
        r = c.post("/auth/passkey/register/complete",
                   json={"credential": {"id": "cid", "response": {"transports": ["internal"]}},
                         "device_name": "Mac"})
        assert r.status_code == 200
        assert captured["owner_type"] == "admin"
        assert captured["owner_email"] == "admin@test.com"
        assert captured["cliente_id"] is None
        assert captured["transports"] == "internal"
        assert captured["device_name"] == "Mac"

    def test_challenge_de_otro_dueno_rechazado_400(self, monkeypatch):
        # Cookie de challenge firmada para OTRO owner_key que la sesión actual.
        monkeypatch.setattr(ceremonies, "verify_registration", lambda **kw: {})
        c = _client()
        c.cookies.set("session", _admin_session())
        c.cookies.set("wa_chal_reg",
                      ceremonies.sign_challenge("chal", ot="admin", ok="otro@x.com", uh="uh"))
        r = c.post("/auth/passkey/register/complete", json={"credential": {"id": "cid"}})
        assert r.status_code == 400


class TestGestionIDOR:
    def test_cliente_delete_scopeado_a_su_id(self, monkeypatch):
        captured = {}

        def fake_delete(cred_pk, owner_type, *, owner_email=None, cliente_id=None):
            captured.update(cred_pk=cred_pk, owner_type=owner_type, cliente_id=cliente_id)
            return True

        monkeypatch.setattr(store, "delete_for_owner", fake_delete)
        c = _client()
        c.cookies.set("session", _cliente_session(cliente_id=42))
        r = c.delete("/cliente/auth/passkey/credentials/99")
        assert r.status_code == 200
        # El route pasa el cliente_id de la SESIÓN (42), no algo del cliente → anti-IDOR.
        assert captured == {"cred_pk": 99, "owner_type": "cliente", "cliente_id": 42}

    def test_cliente_delete_ajeno_404(self, monkeypatch):
        monkeypatch.setattr(store, "delete_for_owner", lambda *a, **k: False)
        c = _client()
        c.cookies.set("session", _cliente_session(cliente_id=42))
        assert c.delete("/cliente/auth/passkey/credentials/99").status_code == 404
