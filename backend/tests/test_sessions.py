"""Tests de la revocación de sesión server-side (allowlist `auth_sessions`).

Cubre las dos mitades sin DB ni cripto real (mockeando el store `sessions_store`):
  · `get_session` exige que la sesión esté viva en la allowlist (toda sesión válida
    lleva `jti`; una cookie sin jti se rechaza y ni siquiera consulta el store);
  · los endpoints de gestión (listar / revoke-all / revoke-one) van scopeados al
    dueño (anti-IDOR) y la sesión actual queda marcada / preservada.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import auth.session as session_mod
from auth import auth_sessions_router as router
from auth.session import signer

pytestmark = pytest.mark.unit


class _Req:
    """Request mínimo para `get_session`: solo cookies, sin `.state` (el memo se
    saltea solo). Replica el patrón de _FakeRequest de los otros tests de auth."""

    def __init__(self, cookies):
        self.cookies = cookies


# ── get_session: la revocación es condicional al `jti` ───────────────────────

class TestGetSessionRevocacion:
    def test_sin_jti_rechazado_sin_consultar_store(self, monkeypatch):
        # jti obligatorio: una cookie sin jti se rechaza y ni consulta el store
        # (corta antes). Las cookies viejas pre-deploy → re-login.
        llamados = {"n": 0}

        def _spy(jti):
            llamados["n"] += 1
            return None

        monkeypatch.setattr("auth.sessions_store.is_active", _spy)
        token = signer.dumps({"email": "a@b.com", "name": "A"})
        assert session_mod.get_session(_Req({"session": token})) is None
        assert llamados["n"] == 0  # cortó antes de tocar el store

    def test_jti_revocado_devuelve_none(self, monkeypatch):
        monkeypatch.setattr("auth.sessions_store.is_active", lambda jti: None)
        token = signer.dumps({"email": "a@b.com", "name": "A", "jti": "x"})
        assert session_mod.get_session(_Req({"session": token})) is None

    def test_jti_activo_devuelve_la_sesion(self, monkeypatch):
        monkeypatch.setattr("auth.sessions_store.is_active", lambda jti: {"jti": jti})
        token = signer.dumps({"email": "a@b.com", "name": "A", "jti": "x"})
        sess = session_mod.get_session(_Req({"session": token}))
        assert sess["email"] == "a@b.com" and sess["jti"] == "x"

    def test_firma_invalida_devuelve_none(self, monkeypatch):
        # Tampering: aunque haya jti, una firma rota nunca llega al store.
        monkeypatch.setattr("auth.sessions_store.is_active",
                            lambda jti: pytest.fail("no debió consultar el store"))
        token = signer.dumps({"email": "a@b.com", "name": "A", "jti": "x"})
        assert session_mod.get_session(_Req({"session": token + "tamper"})) is None


# ── Endpoints de gestión (lógica, sin DB) ────────────────────────────────────

def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _admin_cookie(jti: str = "cur-admin") -> str:
    return signer.dumps({"email": "admin@test.com", "name": "Admin", "jti": jti})


def _cliente_cookie(cliente_id: int = 42, jti: str = "cur-cli") -> str:
    return signer.dumps({"email": "c@x.com", "name": "Cli", "role": "cliente",
                         "cliente_id": cliente_id, "jti": jti})


class TestSessionsRoutes:
    @pytest.fixture(autouse=True)
    def _auth_ok(self, monkeypatch):
        # is_active activo → las cookies con jti pasan el guard de sesión. Cada test
        # mockea además la función del store que ejercita.
        monkeypatch.setattr("auth.sessions_store.is_active", lambda jti: {"jti": jti})

    def test_admin_list_marca_la_actual(self, monkeypatch):
        monkeypatch.setattr("auth.sessions_store.list_for_owner", lambda *a, **k: [
            {"jti": "cur-admin", "user_agent": "Mac", "created_at": None, "expires_at": None},
            {"jti": "otra", "user_agent": "iPhone", "created_at": None, "expires_at": None},
        ])
        c = _client()
        c.cookies.set("session", _admin_cookie("cur-admin"))
        r = c.get("/auth/sessions")
        assert r.status_code == 200
        body = r.json()
        assert body["current_jti"] == "cur-admin"
        marca = {s["jti"]: s["current"] for s in body["sessions"]}
        assert marca == {"cur-admin": True, "otra": False}

    def test_admin_revoke_all_preserva_la_actual(self, monkeypatch):
        captured = {}

        def _fake(owner_type, *, owner_email=None, cliente_id=None, except_jti=None):
            captured.update(owner_type=owner_type, owner_email=owner_email,
                            cliente_id=cliente_id, except_jti=except_jti)
            return 3

        monkeypatch.setattr("auth.sessions_store.revoke_all_for_owner", _fake)
        c = _client()
        c.cookies.set("session", _admin_cookie("cur-admin"))
        r = c.post("/auth/sessions/revoke-all")
        assert r.status_code == 200 and r.json()["revoked"] == 3
        # Pasa el jti de la sesión actual como except → no se auto-desloguea.
        assert captured["except_jti"] == "cur-admin"
        assert captured["owner_type"] == "admin"
        assert captured["owner_email"] == "admin@test.com"

    def test_admin_revoke_one_404_si_no_es_suya(self, monkeypatch):
        monkeypatch.setattr("auth.sessions_store.revoke_one_for_owner", lambda *a, **k: False)
        c = _client()
        c.cookies.set("session", _admin_cookie())
        assert c.delete("/auth/sessions/ajena").status_code == 404

    def test_cliente_revoke_one_scopeado_a_su_id(self, monkeypatch):
        captured = {}

        def _fake(jti, owner_type, *, owner_email=None, cliente_id=None):
            captured.update(jti=jti, owner_type=owner_type, cliente_id=cliente_id)
            return True

        monkeypatch.setattr("auth.sessions_store.revoke_one_for_owner", _fake)
        c = _client()
        c.cookies.set("session", _cliente_cookie(cliente_id=42))
        r = c.delete("/cliente/auth/sessions/otra-jti")
        assert r.status_code == 200
        # El route pasa el cliente_id de la SESIÓN (42), no algo del path → anti-IDOR.
        assert captured == {"jti": "otra-jti", "owner_type": "cliente", "cliente_id": 42}

    def test_cliente_revoke_all_pasa_su_id_y_except(self, monkeypatch):
        captured = {}

        def _fake(owner_type, *, owner_email=None, cliente_id=None, except_jti=None):
            captured.update(owner_type=owner_type, cliente_id=cliente_id, except_jti=except_jti)
            return 1

        monkeypatch.setattr("auth.sessions_store.revoke_all_for_owner", _fake)
        c = _client()
        c.cookies.set("session", _cliente_cookie(cliente_id=42, jti="cur-cli"))
        r = c.post("/cliente/auth/sessions/revoke-all")
        assert r.status_code == 200
        assert captured == {"owner_type": "cliente", "cliente_id": 42, "except_jti": "cur-cli"}

    def test_anonimo_rechazado(self):
        # Sin cookie → los guards cortan (401). Defensa del endpoint de gestión.
        c = _client()
        assert c.get("/auth/sessions").status_code in (401, 403)
        assert c.get("/cliente/auth/sessions").status_code in (401, 403)
