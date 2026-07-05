"""Tests de los callbacks OAuth de Google (`/auth/callback`, `/cliente/auth/callback`)
— la puerta de entrada real del login (admin y cliente). Sin esto, cero cobertura
directa: antes solo estaba testeado el helper puro `_safe_next_path`
(`test_auth_guards.py`), no la validación de state (CSRF), el rate-limit-on-failure,
ni el manejo de errores de Google. authlib mockeado (`OAuth2Client`); nada de red
real ni DB real (sesión mockeada, mismo patrón que `test_staging_login.py`).

Llama a los handlers DIRECTO (no vía HTTP/TestClient) con un Request mínimo —
son funciones planas debajo del decorator, mismo patrón que `test_staging_login.py`.
"""
import pytest
from fastapi import HTTPException

import auth.google as g

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _stub_sessions(monkeypatch):
    """Minteo de sesión sin DB (allowlist server-side stubbeada) — mismo patrón
    que `test_staging_login.py`."""
    monkeypatch.setattr("auth.commands.sessions.create_session", lambda **kw: "stub-jti")
    monkeypatch.setattr("auth.queries.sessions.is_active",
                        lambda jti: {"jti": jti} if jti else None)


@pytest.fixture(autouse=True)
def _google_configurado(monkeypatch):
    monkeypatch.setattr(g, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(g, "GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(g, "FRONTEND_BASE", "http://front.local")
    monkeypatch.setattr(g, "ALLOWED_EMAILS", set())  # sin allowlist salvo que el test la setee
    from auth.ratelimit import _failures
    _failures.clear()
    yield
    _failures.clear()


class _FakeHeaders:
    def get(self, _key, default=""):
        return default


class _FakeClient:
    def __init__(self, host="203.0.113.7"):
        self.host = host


class _FakeRequest:
    """Mínimo para `get_client_ip` (headers + client), `signer`/cookies y
    `request.query_params.get(...)` — igual que `_FakeRequest` de
    `test_staging_login.py`, + query_params."""

    def __init__(self, query=None, cookies=None, host="203.0.113.7"):
        self.headers = _FakeHeaders()
        self.client = _FakeClient(host)
        self.cookies = cookies or {}
        self.query_params = query or {}


class _FakeResp:
    def __init__(self, data, ok=True):
        self._data = data
        self._ok = ok

    def raise_for_status(self):
        if not self._ok:
            raise RuntimeError("userinfo http error")

    def json(self):
        return self._data


class _FakeOAuth2Client:
    """Reemplaza `authlib.integrations.httpx_client.OAuth2Client`: nada de red
    real. Estado de clase (reseteado por test) para controlar fallos."""

    fail_token = False
    fail_userinfo = False
    userinfo = {"email": "persona@x.com", "name": "Persona X", "sub": "sub-real-123"}

    def __init__(self, *a, **kw):
        pass

    def fetch_token(self, *a, **kw):
        if self.fail_token:
            raise RuntimeError("token exchange failed")

    def get(self, *a, **kw):
        if self.fail_userinfo:
            return _FakeResp({}, ok=False)
        return _FakeResp(self.userinfo)


@pytest.fixture(autouse=True)
def _reset_fake_client():
    _FakeOAuth2Client.fail_token = False
    _FakeOAuth2Client.fail_userinfo = False
    _FakeOAuth2Client.userinfo = {"email": "persona@x.com", "name": "Persona X", "sub": "sub-real-123"}
    yield


def _valid_state(**extra) -> str:
    return g.signer.dumps({"nonce": "abc123", **extra})


# ── /auth/callback (admin) ────────────────────────────────────────────────────

class TestAdminCallbackErroresTempranos:
    def test_error_param_redirige_con_ese_error(self):
        req = _FakeRequest(query={"error": "access_denied"})
        r = g.auth_callback(req)
        assert r.status_code == 303 and "error=access_denied" in r.headers["location"]

    def test_sin_code_redirige_no_code(self):
        req = _FakeRequest(query={})
        r = g.auth_callback(req)
        assert r.status_code == 303 and "error=no_code" in r.headers["location"]


class TestAdminCallbackStateCSRF:
    def test_sin_cookie_y_sin_state_rechaza(self):
        req = _FakeRequest(query={"code": "abc"})
        r = g.auth_callback(req)
        assert r.status_code == 303 and "error=state_mismatch" in r.headers["location"]

    def test_state_forjado_sin_firma_rechaza(self):
        req = _FakeRequest(query={"code": "abc", "state": "basura-no-firmada"})
        r = g.auth_callback(req)
        assert r.status_code == 303 and "error=state_mismatch" in r.headers["location"]

    def test_cookie_no_coincide_con_state_y_firma_invalida_rechaza(self):
        # Cookie presente pero de otro state, y el `state` del query no es una firma
        # válida tampoco → ninguna de las 2 vías (cookie / firma) lo salva.
        req = _FakeRequest(
            query={"code": "abc", "state": "otro-valor"},
            cookies={"oauth_state": _valid_state()},
        )
        r = g.auth_callback(req)
        assert r.status_code == 303 and "error=state_mismatch" in r.headers["location"]

    def test_state_matchea_por_cookie(self, monkeypatch):
        monkeypatch.setattr(g, "OAuth2Client", _FakeOAuth2Client)
        state = _valid_state()
        req = _FakeRequest(query={"code": "abc", "state": state}, cookies={"oauth_state": state})
        r = g.auth_callback(req)
        assert r.status_code == 200  # _make_session_response: HTML+JS redirect
        assert "set-cookie" in {k.lower() for k in r.headers.keys()}

    def test_state_matchea_por_firma_sin_cookie(self, monkeypatch):
        # Browsers con ITP/ad-blockers que bloquean la cookie oauth_state: la firma alcanza.
        monkeypatch.setattr(g, "OAuth2Client", _FakeOAuth2Client)
        state = _valid_state()
        req = _FakeRequest(query={"code": "abc", "state": state})  # sin cookie
        r = g.auth_callback(req)
        assert r.status_code == 200


class TestAdminCallbackErroresDeGoogle:
    def test_token_exchange_error_redirige_y_cuenta_fallo(self, monkeypatch):
        monkeypatch.setattr(g, "OAuth2Client", _FakeOAuth2Client)
        _FakeOAuth2Client.fail_token = True
        state = _valid_state()
        req = _FakeRequest(query={"code": "abc", "state": state}, cookies={"oauth_state": state})
        r = g.auth_callback(req)
        assert r.status_code == 303 and "error=token_error" in r.headers["location"]

    def test_userinfo_error_redirige(self, monkeypatch):
        monkeypatch.setattr(g, "OAuth2Client", _FakeOAuth2Client)
        _FakeOAuth2Client.fail_userinfo = True
        state = _valid_state()
        req = _FakeRequest(query={"code": "abc", "state": state}, cookies={"oauth_state": state})
        r = g.auth_callback(req)
        assert r.status_code == 303 and "error=userinfo_error" in r.headers["location"]

    def test_sin_email_en_userinfo_redirige(self, monkeypatch):
        monkeypatch.setattr(g, "OAuth2Client", _FakeOAuth2Client)
        _FakeOAuth2Client.userinfo = {"name": "sin mail"}
        state = _valid_state()
        req = _FakeRequest(query={"code": "abc", "state": state}, cookies={"oauth_state": state})
        r = g.auth_callback(req)
        assert r.status_code == 303 and "error=no_email" in r.headers["location"]

    def test_email_fuera_de_allowlist_rechaza(self, monkeypatch):
        monkeypatch.setattr(g, "OAuth2Client", _FakeOAuth2Client)
        monkeypatch.setattr(g, "ALLOWED_EMAILS", {"otro@x.com"})
        state = _valid_state()
        req = _FakeRequest(query={"code": "abc", "state": state}, cookies={"oauth_state": state})
        r = g.auth_callback(req)
        assert r.status_code == 303 and "error=not_allowed" in r.headers["location"]

    def test_email_en_allowlist_pasa(self, monkeypatch):
        monkeypatch.setattr(g, "OAuth2Client", _FakeOAuth2Client)
        monkeypatch.setattr(g, "ALLOWED_EMAILS", {"persona@x.com"})
        state = _valid_state()
        req = _FakeRequest(query={"code": "abc", "state": state}, cookies={"oauth_state": state})
        r = g.auth_callback(req)
        assert r.status_code == 200


class TestAdminCallbackHappyPathYRateLimit:
    def test_happy_path_mintea_sesion_y_borra_cookie_de_state(self, monkeypatch):
        monkeypatch.setattr(g, "OAuth2Client", _FakeOAuth2Client)
        state = _valid_state()
        req = _FakeRequest(query={"code": "abc", "state": state}, cookies={"oauth_state": state})
        r = g.auth_callback(req)
        assert r.status_code == 200
        cookies = r.headers.getlist("set-cookie")
        assert any(c.startswith("session=") for c in cookies)
        borrado = next((c for c in cookies if c.startswith("oauth_state=")), "")
        assert "Max-Age=0" in borrado  # delete_cookie

    def test_fallas_repetidas_de_state_cortan_con_429(self):
        req = _FakeRequest(query={"code": "abc", "state": "basura"})
        for _ in range(10):
            r = g.auth_callback(req)
            assert r.status_code == 303
        with pytest.raises(HTTPException) as ei:
            g.auth_callback(req)
        assert ei.value.status_code == 429


class TestAdminCallback2doFactor:
    """2º factor obligatorio (criterio del dueño): si la cuenta YA tiene una
    passkey enrolada, Google solo no alcanza — no se mintea sesión, se manda a
    confirmar con la passkey. Sin passkey todavía, Google sigue alcanzando hoy
    (el enrolamiento on-the-fly lo fuerza el frontend, `EnrolarPasskeyGate`)."""

    def test_sin_passkey_mintea_sesion_como_hoy(self, monkeypatch):
        monkeypatch.setattr(g, "OAuth2Client", _FakeOAuth2Client)
        monkeypatch.setattr("auth.passkey.queries.list_for_owner", lambda *a, **k: [])
        state = _valid_state()
        req = _FakeRequest(query={"code": "abc", "state": state}, cookies={"oauth_state": state})
        r = g.auth_callback(req)
        assert r.status_code == 200
        assert any(c.startswith("session=") for c in r.headers.getlist("set-cookie"))

    def test_con_passkey_no_mintea_sesion_y_manda_a_confirmar(self, monkeypatch):
        monkeypatch.setattr(g, "OAuth2Client", _FakeOAuth2Client)
        monkeypatch.setattr(
            "auth.passkey.queries.list_for_owner",
            lambda *a, **k: [{"id": 1, "device_name": "iPhone"}],
        )
        state = _valid_state()
        req = _FakeRequest(query={"code": "abc", "state": state}, cookies={"oauth_state": state})
        r = g.auth_callback(req)
        assert r.status_code == 303
        assert "/admin/login?paso=passkey" in r.headers["location"]
        # No hay cookie de sesión — el login discoverable de passkey es quien la mintea de verdad.
        assert not any(c.startswith("session=") for c in r.headers.getlist("set-cookie"))


# ── /cliente/auth/callback ────────────────────────────────────────────────────

class TestClienteCallback:
    def test_state_mismatch_redirige(self):
        req = _FakeRequest(query={"code": "abc", "state": "basura"})
        r = g.cliente_auth_callback(req)
        assert r.status_code == 303 and "error=state_mismatch" in r.headers["location"]

    def test_cliente_desconocido_redirige_a_registro_con_token(self, monkeypatch):
        monkeypatch.setattr(g, "OAuth2Client", _FakeOAuth2Client)
        monkeypatch.setattr("auth.commands.identities.find_or_backfill_google", lambda sub, email: None)
        state = _valid_state()
        req = _FakeRequest(
            query={"code": "abc", "state": state}, cookies={"oauth_state_cliente": state}
        )
        r = g.cliente_auth_callback(req)
        assert r.status_code == 303
        assert "/cliente/registro?t=" in r.headers["location"]

    def test_cliente_conocido_mintea_sesion_y_va_al_portal(self, monkeypatch):
        monkeypatch.setattr(g, "OAuth2Client", _FakeOAuth2Client)
        monkeypatch.setattr("auth.commands.identities.find_or_backfill_google", lambda sub, email: 42)
        state = _valid_state()
        req = _FakeRequest(
            query={"code": "abc", "state": state}, cookies={"oauth_state_cliente": state}
        )
        r = g.cliente_auth_callback(req)
        assert r.status_code == 200
        assert "set-cookie" in {k.lower() for k in r.headers.keys()}

    def test_cliente_conocido_con_next_valido_vuelve_ahi(self, monkeypatch):
        monkeypatch.setattr(g, "OAuth2Client", _FakeOAuth2Client)
        monkeypatch.setattr("auth.commands.identities.find_or_backfill_google", lambda sub, email: 42)
        state = _valid_state()
        req = _FakeRequest(
            query={"code": "abc", "state": state},
            cookies={"oauth_state_cliente": state, "oauth_next_cliente": "/estudio"},
        )
        r = g.cliente_auth_callback(req)
        assert r.status_code == 200
        # El redirect JS embebido en el HTML apunta al `next` guardado.
        assert "/estudio" in r.body.decode()

    def test_link_mode_delega_en_completar_link(self, monkeypatch):
        # link_cliente_id en el state → NO es login, es vincular una passkey/Google
        # a la cuenta ya logueada (dispatch a `_completar_link_google`).
        monkeypatch.setattr(g, "OAuth2Client", _FakeOAuth2Client)
        calls = {}
        monkeypatch.setattr(
            g, "_completar_link_google",
            lambda req, link_cid, sub, email: calls.update(link_cid=link_cid, sub=sub, email=email)
            or "DISPATCHED",
        )
        state = _valid_state(link_cliente_id=7)
        req = _FakeRequest(
            query={"code": "abc", "state": state}, cookies={"oauth_state_cliente": state}
        )
        out = g.cliente_auth_callback(req)
        assert out == "DISPATCHED"
        assert calls == {"link_cid": 7, "sub": "sub-real-123", "email": "persona@x.com"}
