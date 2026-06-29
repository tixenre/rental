"""Tests de los guards de autenticación.

Asegura que:
- require_admin rechaza si no hay sesión, si la sesión no es admin, etc.
- require_cliente rechaza si no hay sesión o si role != "cliente".

Es regresión del crítico de seguridad #55 (22 endpoints sin require_admin).
"""

import pytest
from fastapi import HTTPException

from auth.guards import is_admin_email, require_admin, ADMIN_EMAILS
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
        monkeypatch.setattr("auth.guards.get_session", lambda req: None)

        with pytest.raises(HTTPException) as exc:
            require_admin(FakeRequest())
        assert exc.value.status_code == 401

    def test_sesion_sin_email_admin_403(self, monkeypatch):
        monkeypatch.delenv("ADMIN_BYPASS_AUTH", raising=False)
        monkeypatch.setattr(
            "auth.guards.get_session",
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
            "auth.guards.get_session",
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
        monkeypatch.setattr("auth.guards.get_session", lambda req: None)
        with pytest.raises(HTTPException) as exc:
            require_admin(FakeRequest())
        assert exc.value.status_code == 401  # sin bypass → exige sesión

    def test_bypass_solo_acepta_truthy_explicitos(self, monkeypatch):
        # "0", "false", "" → NO bypass
        for val in ["0", "false", "no", ""]:
            monkeypatch.setenv("ADMIN_BYPASS_AUTH", val)
            monkeypatch.setattr("auth.guards.get_session", lambda req: None)
            with pytest.raises(HTTPException) as exc:
                require_admin(FakeRequest())
            assert exc.value.status_code == 401, f"ADMIN_BYPASS_AUTH={val!r} no debería ser bypass"


# ── require_cliente ──────────────────────────────────────────────────────────

class TestRequireCliente:
    def test_sin_sesion_401(self, monkeypatch):
        monkeypatch.setattr("auth.guards.get_session", lambda req: None)

        with pytest.raises(HTTPException) as exc:
            require_cliente(FakeRequest())
        assert exc.value.status_code == 401

    def test_sesion_de_admin_no_es_cliente(self, monkeypatch):
        # Regresión del bug #31/#55: sesiones de admin NO deben ser tratadas
        # como cliente. role debe ser exactamente "cliente".
        monkeypatch.setattr(
            "auth.guards.get_session",
            lambda req: {"email": "admin@rambla.com", "role": "admin"},
        )

        with pytest.raises(HTTPException) as exc:
            require_cliente(FakeRequest())
        assert exc.value.status_code == 401

    def test_sesion_sin_role_rechaza(self, monkeypatch):
        # Sesión vieja sin role definido → tratar como no-cliente
        monkeypatch.setattr(
            "auth.guards.get_session",
            lambda req: {"email": "x@y.com"},
        )

        with pytest.raises(HTTPException) as exc:
            require_cliente(FakeRequest())
        assert exc.value.status_code == 401

    def test_sesion_cliente_valida_pasa(self, monkeypatch):
        monkeypatch.setattr(
            "auth.guards.get_session",
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
        from auth.google import _safe_next_path
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

    def test_xss_payload_rechaza(self):
        # El valor se embebe en <script>…replace("{next}")…</script>; un next con
        # `<`/`>`/comillas/backslash podría romper ese contexto y ejecutar JS.
        assert self._safe("/x</script><img src=x onerror=alert(1)>") is None
        assert self._safe('/x"><script>alert(1)</script>') is None
        assert self._safe("/x';alert(1);//") is None
        assert self._safe("/ok\nlinea") is None  # whitespace/control
        # No rompemos lo legítimo: path interno normal con query sigue pasando.
        assert self._safe("/estudio?d=2026-06-01&h=10:00") == "/estudio?d=2026-06-01&h=10:00"


# ── dev_bypass_enabled + /auth/dev-login (#503) ───────────────────────────────


class TestDevBypassEnabled:
    """El bypass de dev NUNCA debe estar activo en producción (Railway)."""

    def test_activo_en_dev(self, monkeypatch):
        from auth.session import dev_bypass_enabled

        monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
        for v in ("1", "true", "TRUE", "yes"):
            monkeypatch.setenv("ADMIN_BYPASS_AUTH", v)
            assert dev_bypass_enabled() is True, v

    def test_prod_gana_sobre_bypass(self, monkeypatch):
        from auth.session import dev_bypass_enabled

        monkeypatch.setenv("ADMIN_BYPASS_AUTH", "1")
        monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
        assert dev_bypass_enabled() is False

    def test_sin_bypass(self, monkeypatch):
        from auth.session import dev_bypass_enabled

        monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
        for v in ("", "0", "no", "false"):
            monkeypatch.setenv("ADMIN_BYPASS_AUTH", v)
            assert dev_bypass_enabled() is False, v

    def test_dev_login_403_en_prod(self, monkeypatch):
        from fastapi import HTTPException
        from auth.staging import auth_dev_login

        monkeypatch.setenv("ADMIN_BYPASS_AUTH", "1")
        monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
        with pytest.raises(HTTPException) as exc:
            auth_dev_login()
        assert exc.value.status_code == 404


# ── auth_middleware: assets estáticos de dist root son públicos ───────────────


class _FakeURL:
    def __init__(self, path):
        self.path = path


class _MiddlewareRequest:
    """Request mínimo para auth_middleware: solo necesita .url.path."""
    def __init__(self, path, method="GET"):
        self.url = _FakeURL(path)
        self.cookies = {}
        self.method = method


class TestAuthMiddlewareStaticAssets:
    """Regresión: los archivos estáticos de la raíz del build (fotos del
    estudio, favicon, icons, manifest, robots) NO deben redirigir a /login.

    Bug original: `/estudio/*.jpg` y `/favicon.png` caían al guard de sesión
    (307 → /login) → imagen rota en el hero del catálogo. El guard de datos
    (/api/*, /admin/*) tiene que seguir intacto.
    """

    @pytest.fixture(autouse=True)
    def _no_session(self, monkeypatch):
        # Sin sesión: el peor caso para un asset público.
        monkeypatch.setattr("middleware.get_session", lambda req: None)

    async def _classify(self, path, method="GET"):
        """Corre el middleware con un call_next sentinela. Devuelve
        'PASS' si llamó a call_next, o la respuesta de redirect/401."""
        from middleware import auth_middleware

        sentinel = object()

        async def call_next(_req):
            return sentinel

        result = await auth_middleware(_MiddlewareRequest(path, method), call_next)
        return "PASS" if result is sentinel else result

    @pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE", "PUT"])
    async def test_escritura_equipos_no_es_publica(self, method):
        """Regresión del fix de authz: `/api/equipos` es público SOLO para
        lectura. Una escritura sin sesión NO debe pasar el middleware (defensa
        en profundidad; el handler además exige require_admin)."""
        res = await self._classify("/api/equipos/5", method=method)
        assert res != "PASS", f"{method} /api/equipos no debería eximirse sin sesión"

    async def test_lectura_equipos_sigue_publica(self):
        """El catálogo anónimo (GET) tiene que seguir pasando."""
        assert await self._classify("/api/equipos", method="GET") == "PASS"

    @pytest.mark.parametrize("path", [
        "/favicon.png",
        "/apple-touch-icon.png",
        "/icon-512.png",
        "/og-image.png",
        "/manifest-admin.json",
        "/robots.txt",
        "/wordmark.svg",
    ])
    async def test_assets_estaticos_pasan(self, path):
        assert await self._classify(path) == "PASS", path

    async def test_pagina_admin_redirige_a_login(self):
        from fastapi.responses import RedirectResponse

        res = await self._classify("/admin/equipos")
        assert isinstance(res, RedirectResponse)
        assert res.headers["location"] == "/login"

    @pytest.mark.parametrize("path", [
        "/api/pedidos",
        "/api/admin/inventario",
        "/api/admin/export.json",  # extensión NO debe abrir un endpoint de datos
    ])
    async def test_api_protegida_sigue_401(self, path):
        from fastapi.responses import JSONResponse

        res = await self._classify(path)
        assert isinstance(res, JSONResponse)
        assert res.status_code == 401

    @pytest.mark.parametrize("method", ["POST", "GET"])
    async def test_webhook_es_publico(self, method):
        """Regresión: los webhooks server-to-server (Didit) los llama un tercero
        SIN cookie de sesión y se autentican por HMAC DENTRO del handler. Si el
        middleware los corta con 401 (como pasaba), el handler nunca corre y la
        verificación de identidad nunca se persiste. Deben PASAR el middleware
        (POST incluido) → el HMAC decide adentro."""
        assert await self._classify("/api/webhooks/didit", method=method) == "PASS"


# ── Regresión por-endpoint del fix de authz de /api/equipos (#795) ──
# Pega a CADA handler de escritura SIN sesión y exige rechazo. Si alguien saca el
# require_admin de un handler a futuro (la misma clase de bug que #55, recurrente),
# este test lo caza de punta a punta (app real + middleware + handler).
_EQUIPOS_WRITE_ENDPOINTS = [
    ("POST", "/api/equipos"),
    ("PATCH", "/api/equipos/1"),
    ("DELETE", "/api/equipos/1"),
    ("POST", "/api/equipos/1/duplicate"),
    ("PUT", "/api/equipos/1/ficha"),
    ("POST", "/api/equipos/1/mantenimiento"),
    ("PATCH", "/api/equipos/1/mantenimiento/1"),
    ("DELETE", "/api/equipos/1/mantenimiento/1"),
    ("POST", "/api/equipos/1/kit"),
    ("DELETE", "/api/equipos/1/kit/1"),
    ("PUT", "/api/equipos/1/etiquetas"),
    ("PUT", "/api/equipos/1/categorias"),
]


@pytest.mark.parametrize("method,path", _EQUIPOS_WRITE_ENDPOINTS)
def test_escritura_equipos_sin_sesion_rechazada(method, path):
    """Anónimo (sin cookie) → 401/403 en toda escritura de /api/equipos."""
    from fastapi.testclient import TestClient
    import main

    client = TestClient(main.app)
    res = client.request(method, path, json={})
    assert res.status_code in (401, 403), f"{method} {path} dejó pasar a un anónimo ({res.status_code})"
