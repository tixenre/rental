"""Tests de los guards de autenticación.

Asegura que:
- require_admin rechaza si no hay sesión, si la sesión no es admin, etc.
- require_cliente rechaza si no hay sesión o si role != "cliente".

Es regresión del crítico de seguridad #55 (22 endpoints sin require_admin).
"""

import pytest
from fastapi import HTTPException

from admin_guard import is_admin_email, require_admin, ADMIN_EMAILS
from routes.cliente_portal import require_cliente


pytestmark = pytest.mark.unit


class FakeRequest:
    """Minimal request object para guards que solo lee cookies."""
    def __init__(self, cookies=None):
        self.cookies = cookies or {}


# ── is_admin_email ───────────────────────────────────────────────────────────

class TestIsAdminEmail:
    def test_email_en_allowlist_es_admin(self):
        # Tomamos un email del set actual y verificamos
        if ADMIN_EMAILS:
            admin = next(iter(ADMIN_EMAILS))
            assert is_admin_email(admin) is True

    def test_email_random_no_es_admin(self):
        assert is_admin_email("random@gmail.com") is False

    def test_email_vacio_no_es_admin(self):
        assert is_admin_email("") is False
        assert is_admin_email(None) is False

    def test_case_insensitive(self):
        if ADMIN_EMAILS:
            admin = next(iter(ADMIN_EMAILS))
            assert is_admin_email(admin.upper()) is True


# ── require_admin ────────────────────────────────────────────────────────────

class TestRequireAdmin:
    def test_sin_sesion_401(self, monkeypatch):
        monkeypatch.delenv("ADMIN_BYPASS_AUTH", raising=False)
        monkeypatch.setattr("admin_guard.get_session", lambda req: None)

        with pytest.raises(HTTPException) as exc:
            require_admin(FakeRequest())
        assert exc.value.status_code == 401

    def test_sesion_sin_email_admin_403(self, monkeypatch):
        monkeypatch.delenv("ADMIN_BYPASS_AUTH", raising=False)
        monkeypatch.setattr(
            "admin_guard.get_session",
            lambda req: {"email": "cliente.random@gmail.com", "role": "cliente"},
        )

        with pytest.raises(HTTPException) as exc:
            require_admin(FakeRequest())
        assert exc.value.status_code == 403

    def test_sesion_con_email_admin_pasa(self, monkeypatch):
        monkeypatch.delenv("ADMIN_BYPASS_AUTH", raising=False)
        if not ADMIN_EMAILS:
            pytest.skip("No hay ADMIN_EMAILS configurado")
        admin_email = next(iter(ADMIN_EMAILS))
        monkeypatch.setattr(
            "admin_guard.get_session",
            lambda req: {"email": admin_email, "role": "admin"},
        )

        result = require_admin(FakeRequest())
        assert result["email"] == admin_email

    def test_bypass_env_var_skip_auth(self, monkeypatch):
        # ADMIN_BYPASS_AUTH=1 → no chequea sesión (modo dev)
        monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
        monkeypatch.setenv("ADMIN_BYPASS_AUTH", "1")
        result = require_admin(FakeRequest())
        assert result["kind"] == "bypass"

    def test_bypass_ignorado_en_prod(self, monkeypatch):
        # #503: en Railway/prod el bypass se ignora aunque ADMIN_BYPASS_AUTH=1
        # esté seteada por error → no debe haber puerta abierta de cara al público.
        monkeypatch.setenv("ADMIN_BYPASS_AUTH", "1")
        monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
        monkeypatch.setattr("admin_guard.get_session", lambda req: None)
        with pytest.raises(HTTPException) as exc:
            require_admin(FakeRequest())
        assert exc.value.status_code == 401  # sin bypass → exige sesión

    def test_bypass_solo_acepta_truthy_explicitos(self, monkeypatch):
        # "0", "false", "" → NO bypass
        for val in ["0", "false", "no", ""]:
            monkeypatch.setenv("ADMIN_BYPASS_AUTH", val)
            monkeypatch.setattr("admin_guard.get_session", lambda req: None)
            with pytest.raises(HTTPException) as exc:
                require_admin(FakeRequest())
            assert exc.value.status_code == 401, f"ADMIN_BYPASS_AUTH={val!r} no debería ser bypass"


# ── require_cliente ──────────────────────────────────────────────────────────

class TestRequireCliente:
    def test_sin_sesion_401(self, monkeypatch):
        monkeypatch.setattr("routes.cliente_portal.get_session", lambda req: None)

        with pytest.raises(HTTPException) as exc:
            require_cliente(FakeRequest())
        assert exc.value.status_code == 401

    def test_sesion_de_admin_no_es_cliente(self, monkeypatch):
        # Regresión del bug #31/#55: sesiones de admin NO deben ser tratadas
        # como cliente. role debe ser exactamente "cliente".
        monkeypatch.setattr(
            "routes.cliente_portal.get_session",
            lambda req: {"email": "admin@rambla.com", "role": "admin"},
        )

        with pytest.raises(HTTPException) as exc:
            require_cliente(FakeRequest())
        assert exc.value.status_code == 401

    def test_sesion_sin_role_rechaza(self, monkeypatch):
        # Sesión vieja sin role definido → tratar como no-cliente
        monkeypatch.setattr(
            "routes.cliente_portal.get_session",
            lambda req: {"email": "x@y.com"},
        )

        with pytest.raises(HTTPException) as exc:
            require_cliente(FakeRequest())
        assert exc.value.status_code == 401

    def test_sesion_cliente_valida_pasa(self, monkeypatch):
        monkeypatch.setattr(
            "routes.cliente_portal.get_session",
            lambda req: {"email": "cliente@gmail.com", "role": "cliente", "cliente_id": 42},
        )

        result = require_cliente(FakeRequest())
        assert result["email"] == "cliente@gmail.com"
        assert result["cliente_id"] == 42


# ── _safe_next_path (open-redirect guard del OAuth flow) ──────────────────────


class TestSafeNextPath:
    """Valida que solo aceptamos paths internos, no open-redirect.

    Cubre la cookie `oauth_next_cliente` que setea /cliente/auth/google con
    `?next=` y que el callback usa para redirigir post-login.
    """

    def _safe(self, raw):
        from routes.auth import _safe_next_path
        return _safe_next_path(raw)

    def test_none_y_vacio_devuelven_none(self):
        assert self._safe(None) is None
        assert self._safe("") is None
        assert self._safe("   ") is None

    def test_path_simple_es_aceptado(self):
        assert self._safe("/estudio") == "/estudio"
        assert self._safe("/cliente/portal") == "/cliente/portal"

    def test_path_con_query_es_aceptado(self):
        assert self._safe("/estudio?d=2026-06-01&h=10:00") == "/estudio?d=2026-06-01&h=10:00"

    def test_protocol_relative_rechaza(self):
        # `//evil.com/x` se interpreta como `https://evil.com/x` → open redirect
        assert self._safe("//evil.com/path") is None
        # Backslash al inicio: algunos navegadores lo tratan como `//` (open redirect).
        assert self._safe("/\\evil.com/path") is None

    def test_url_absoluta_rechaza(self):
        assert self._safe("https://evil.com/path") is None
        assert self._safe("http://evil.com/path") is None

    def test_path_sin_slash_inicial_rechaza(self):
        assert self._safe("estudio") is None
        assert self._safe("../estudio") is None

    def test_longitud_excesiva_rechaza(self):
        assert self._safe("/" + ("a" * 3000)) is None


# ── dev_bypass_enabled + /auth/dev-login (#503) ───────────────────────────────


class TestDevBypassEnabled:
    """El bypass de dev NUNCA debe estar activo en producción (Railway)."""

    def test_activo_en_dev(self, monkeypatch):
        from routes.auth import dev_bypass_enabled

        monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
        for v in ("1", "true", "TRUE", "yes"):
            monkeypatch.setenv("ADMIN_BYPASS_AUTH", v)
            assert dev_bypass_enabled() is True, v

    def test_prod_gana_sobre_bypass(self, monkeypatch):
        from routes.auth import dev_bypass_enabled

        monkeypatch.setenv("ADMIN_BYPASS_AUTH", "1")
        monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
        assert dev_bypass_enabled() is False

    def test_sin_bypass(self, monkeypatch):
        from routes.auth import dev_bypass_enabled

        monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
        for v in ("", "0", "no", "false"):
            monkeypatch.setenv("ADMIN_BYPASS_AUTH", v)
            assert dev_bypass_enabled() is False, v

    def test_dev_login_403_en_prod(self, monkeypatch):
        from fastapi import HTTPException
        from routes.auth import auth_dev_login

        monkeypatch.setenv("ADMIN_BYPASS_AUTH", "1")
        monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
        with pytest.raises(HTTPException) as exc:
            auth_dev_login()
        assert exc.value.status_code == 403
