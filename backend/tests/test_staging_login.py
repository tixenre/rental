"""Tests del login programático de STAGING (`/auth/staging-login`).

A diferencia de `/auth/dev-login` (apagado en CUALQUIER entorno Railway), este
corre en el `dev` de Railway para que un cliente automatizado pruebe flujos
autenticados del back-office en staging. Por eso el gate es crítico:

- NUNCA en producción (`settings.is_production`, que falla hacia "sí prod").
- Solo con `STAGING_LOGIN_SECRET` configurado (la BD de staging es copia de prod
  → tiene PII real; un login abierto sería una fuga).
- Secreto comparado en tiempo constante; rate-limit por IP; todo logueado.
"""
import pytest
from fastapi import HTTPException

import config
import routes.auth as auth

pytestmark = pytest.mark.unit


class _FakeHeaders:
    def get(self, _key, default=""):
        return default


class _FakeClient:
    host = "203.0.113.7"


class _FakeRequest:
    """Mínimo para `get_client_ip` (headers + client) y `get_session` (cookies)."""

    def __init__(self, cookies=None, host="203.0.113.7"):
        self.headers = _FakeHeaders()
        self.client = type("C", (), {"host": host})()
        self.cookies = cookies or {}


def _env(monkeypatch, railway_env, secret=None):
    monkeypatch.setattr(config.settings, "RAILWAY_ENVIRONMENT", railway_env)
    if secret is None:
        monkeypatch.delenv("STAGING_LOGIN_SECRET", raising=False)
    else:
        monkeypatch.setenv("STAGING_LOGIN_SECRET", secret)
    auth._failures.clear()  # aislar el rate-limit entre tests


# ── staging_login_enabled: la doble llave ────────────────────────────────────

class TestGate:
    def test_dev_con_secreto_habilita(self, monkeypatch):
        _env(monkeypatch, "dev", "s3cr3t")
        assert auth.staging_login_enabled() is True

    def test_prod_nunca_aunque_haya_secreto(self, monkeypatch):
        _env(monkeypatch, "production", "s3cr3t")
        assert auth.staging_login_enabled() is False

    def test_dev_sin_secreto_no_habilita(self, monkeypatch):
        _env(monkeypatch, "dev", None)
        assert auth.staging_login_enabled() is False

    def test_entorno_desconocido_falla_a_prod(self, monkeypatch):
        # Nombre de ambiente nuevo mal nombrado → tratado como prod → apagado,
        # aunque haya secreto. (is_production falla hacia "sí prod".)
        _env(monkeypatch, "produccion-2", "s3cr3t")
        assert auth.staging_login_enabled() is False

    def test_local_sin_railway_no_habilita_sin_secreto(self, monkeypatch):
        _env(monkeypatch, None, None)
        assert auth.staging_login_enabled() is False


# ── endpoint: 404 / 401 / 200 ────────────────────────────────────────────────

class TestEndpoint:
    def test_404_si_no_habilitado(self, monkeypatch):
        _env(monkeypatch, "dev", None)  # sin secreto → como si no existiera
        with pytest.raises(HTTPException) as exc:
            auth.auth_staging_login(auth.StagingLoginInput(secret="x"), _FakeRequest())
        assert exc.value.status_code == 404

    def test_404_en_prod_aunque_secreto_correcto(self, monkeypatch):
        _env(monkeypatch, "production", "s3cr3t")
        with pytest.raises(HTTPException) as exc:
            auth.auth_staging_login(auth.StagingLoginInput(secret="s3cr3t"), _FakeRequest())
        assert exc.value.status_code == 404

    def test_401_secreto_incorrecto(self, monkeypatch):
        _env(monkeypatch, "dev", "s3cr3t")
        with pytest.raises(HTTPException) as exc:
            auth.auth_staging_login(auth.StagingLoginInput(secret="wrong"), _FakeRequest())
        assert exc.value.status_code == 401

    def test_200_secreto_correcto_mintea_sesion_del_bot(self, monkeypatch):
        _env(monkeypatch, "dev", "s3cr3t")
        res = auth.auth_staging_login(auth.StagingLoginInput(secret="s3cr3t"), _FakeRequest())

        # La cookie de sesión está seteada y decodifica al email del bot.
        set_cookie = res.headers.get("set-cookie", "")
        assert "session=" in set_cookie
        token = set_cookie.split("session=", 1)[1].split(";", 1)[0]
        session = auth.get_session(_FakeRequest(cookies={"session": token}))
        assert session is not None
        assert session["email"] == auth.STAGING_LOGIN_EMAIL

    def test_login_no_saltea_admin_check(self, monkeypatch):
        """El login mintea sesión, pero la admin-ness la sigue resolviendo
        `is_admin_email` (fuente única): un email fuera del allowlist NO es admin
        aunque consiga sesión por este endpoint."""
        from admin_guard import is_admin_email
        monkeypatch.setattr(auth, "STAGING_LOGIN_EMAIL", "no-admin@rambla.local")
        _env(monkeypatch, "dev", "s3cr3t")
        res = auth.auth_staging_login(auth.StagingLoginInput(secret="s3cr3t"), _FakeRequest())
        token = res.headers.get("set-cookie", "").split("session=", 1)[1].split(";", 1)[0]
        session = auth.get_session(_FakeRequest(cookies={"session": token}))
        assert session["email"] == "no-admin@rambla.local"
        assert is_admin_email(session["email"]) is False

    def test_admin_es_el_default_sin_target(self, monkeypatch):
        """Backward-compat: sin `target` mintea sesión de admin (sin `role`)."""
        _env(monkeypatch, "dev", "s3cr3t")
        res = auth.auth_staging_login(auth.StagingLoginInput(secret="s3cr3t"), _FakeRequest())
        token = res.headers.get("set-cookie", "").split("session=", 1)[1].split(";", 1)[0]
        session = auth.get_session(_FakeRequest(cookies={"session": token}))
        assert session["email"] == auth.STAGING_LOGIN_EMAIL
        assert "role" not in session  # NO es sesión de cliente

    def test_target_invalido_400(self, monkeypatch):
        _env(monkeypatch, "dev", "s3cr3t")
        with pytest.raises(HTTPException) as exc:
            auth.auth_staging_login(
                auth.StagingLoginInput(secret="s3cr3t", target="otro"), _FakeRequest()
            )
        assert exc.value.status_code == 400


# ── target="cliente": sesión del portal del cliente ──────────────────────────

class TestClienteTarget:
    def test_cliente_target_mintea_sesion_de_cliente(self, monkeypatch):
        """target="cliente" mintea una sesión que `require_cliente` acepta:
        lleva `role="cliente"` + `cliente_id` del cliente resuelto."""
        _env(monkeypatch, "dev", "s3cr3t")
        monkeypatch.setattr(
            auth, "_resolve_staging_cliente",
            lambda cid: {"id": 77, "email": "cli@rambla.local", "name": "Cliente Test"},
        )
        res = auth.auth_staging_login(
            auth.StagingLoginInput(secret="s3cr3t", target="cliente"), _FakeRequest()
        )
        token = res.headers.get("set-cookie", "").split("session=", 1)[1].split(";", 1)[0]
        session = auth.get_session(_FakeRequest(cookies={"session": token}))
        assert session["role"] == "cliente"
        assert session["cliente_id"] == 77
        assert session["email"] == "cli@rambla.local"

        # Regresión real: la sesión minteada pasa el guard del portal.
        from routes.cliente_portal.core import require_cliente
        ok = require_cliente(_FakeRequest(cookies={"session": token}))
        assert ok["cliente_id"] == 77

        # Boundary admin≠cliente (bug #31/#55): la sesión de cliente NO es admin.
        from admin_guard import require_admin
        with pytest.raises(HTTPException) as exc:
            require_admin(_FakeRequest(cookies={"session": token}))
        assert exc.value.status_code == 403

    def test_cliente_target_404_si_no_existe(self, monkeypatch):
        """Sin cliente de servicio ni `cliente_id` válido → 404 (no se crea nada)."""
        _env(monkeypatch, "dev", "s3cr3t")
        monkeypatch.setattr(auth, "_resolve_staging_cliente", lambda cid: None)
        with pytest.raises(HTTPException) as exc:
            auth.auth_staging_login(
                auth.StagingLoginInput(secret="s3cr3t", target="cliente"), _FakeRequest()
            )
        assert exc.value.status_code == 404

    def test_cliente_target_404_en_prod(self, monkeypatch):
        """El gate aplica igual al target cliente: 404 en prod aunque el secreto sea correcto."""
        _env(monkeypatch, "production", "s3cr3t")
        with pytest.raises(HTTPException) as exc:
            auth.auth_staging_login(
                auth.StagingLoginInput(secret="s3cr3t", target="cliente"), _FakeRequest()
            )
        assert exc.value.status_code == 404

    def test_cliente_id_se_pasa_al_resolver(self, monkeypatch):
        """Si el body trae `cliente_id`, el resolver lo recibe (impersonar un cliente puntual)."""
        _env(monkeypatch, "dev", "s3cr3t")
        recibido = {}

        def _fake_resolver(cid):
            recibido["cid"] = cid
            return {"id": cid, "email": "c@x.local", "name": "C"}

        monkeypatch.setattr(auth, "_resolve_staging_cliente", _fake_resolver)
        auth.auth_staging_login(
            auth.StagingLoginInput(secret="s3cr3t", target="cliente", cliente_id=42),
            _FakeRequest(),
        )
        assert recibido["cid"] == 42
