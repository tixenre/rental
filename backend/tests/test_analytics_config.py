"""Tests de la config de analítica (GA4) — integración Google Analytics.

Cubre:
- `GET /analytics-config` (función `analytics_config`): solo expone el
  Measurement ID en producción; staging/local devuelven null para no contaminar
  las métricas de prod (la BD de staging es copia de prod).
- Validación del `ga4_measurement_id` en `update_setting`: formato G-XXXX,
  normalización a mayúsculas, y rechazo de basura.
"""

import pytest
from fastapi import HTTPException
from starlette.requests import Request

pytestmark = pytest.mark.unit


def _fake_request() -> Request:
    """Request real (no `None`) — update_setting lleva `@limiter.limit`
    (barrido de seguimiento #1263/#1265): slowapi exige una instancia genuina
    de `starlette.requests.Request`. Sin conexión real — alcanza con el scope
    ASGI mínimo. Pasarlo SIEMPRE posicional en el call site (no `request=`):
    el wrapper de slowapi resuelve `args[idx] if args else None` de forma
    ansiosa incluso cuando `request` ya está en kwargs — con args parciales
    (call directo, no vía FastAPI) eso revienta con IndexError."""
    return Request(
        {"type": "http", "method": "PUT", "path": "/admin/settings/ga4_measurement_id",
         "headers": [], "client": ("127.0.0.1", 0)}
    )


class _FakeRow(dict):
    """Row indexable por clave, como las del driver (row["value"])."""


class _FakeConn:
    def __init__(self, row=None):
        self._row = row
        self.committed = False
        self.closed = False

    def execute(self, query, params=None):
        conn = self

        class _Result:
            def fetchone(self_inner):
                return conn._row

        return _Result()

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def close(self):
        self.closed = True


# ── analytics_config: gate por ambiente ──────────────────────────────────────


def _set_env(monkeypatch, value):
    import config

    monkeypatch.setattr(config.settings, "RAILWAY_ENVIRONMENT", value)


def test_analytics_config_devuelve_id_en_produccion(monkeypatch):
    import routes.settings as mod

    _set_env(monkeypatch, "production")
    monkeypatch.setattr(mod, "get_db", lambda: _FakeConn(_FakeRow(value="G-ABC12345")))

    assert mod.analytics_config() == {"ga4_id": "G-ABC12345"}


def test_analytics_config_null_en_staging(monkeypatch):
    import routes.settings as mod

    _set_env(monkeypatch, "dev")
    # Aunque la BD tenga un ID (staging = copia de prod), no debe exponerlo.
    monkeypatch.setattr(mod, "get_db", lambda: _FakeConn(_FakeRow(value="G-ABC12345")))

    assert mod.analytics_config() == {"ga4_id": None}


def test_analytics_config_null_en_local(monkeypatch):
    import routes.settings as mod

    _set_env(monkeypatch, None)
    # En local ni siquiera tocamos la BD; igual mockeamos por las dudas.
    monkeypatch.setattr(mod, "get_db", lambda: _FakeConn(None))

    assert mod.analytics_config() == {"ga4_id": None}


def test_analytics_config_id_vacio_devuelve_null(monkeypatch):
    import routes.settings as mod

    _set_env(monkeypatch, "production")
    monkeypatch.setattr(mod, "get_db", lambda: _FakeConn(_FakeRow(value="   ")))

    assert mod.analytics_config() == {"ga4_id": None}


# ── update_setting: validación del Measurement ID ────────────────────────────


def _admin(monkeypatch, mod):
    # `update_setting` usa el guard CANÓNICO (`admin_guard.require_admin`), que
    # resuelve la sesión vía `admin_guard.get_session` y exige email ∈ ADMIN_EMAILS
    # (admin@test.com en el entorno de tests). `mod` se mantiene por compat de firma.
    import auth.guards as admin_guard

    monkeypatch.delenv("ADMIN_BYPASS_AUTH", raising=False)
    monkeypatch.setattr(admin_guard, "get_session", lambda request: {"email": "admin@test.com"})


def test_update_ga4_valido_normaliza_mayusculas(monkeypatch):
    import routes.settings as mod

    _admin(monkeypatch, mod)
    fake = _FakeConn()
    monkeypatch.setattr(mod, "get_db", lambda: fake)

    res = mod.update_setting("ga4_measurement_id", {"value": "g-ab12cd34"}, _fake_request())
    assert res["value"] == "G-AB12CD34"
    assert fake.committed is True


def test_update_ga4_invalido_rechaza(monkeypatch):
    import routes.settings as mod

    _admin(monkeypatch, mod)
    monkeypatch.setattr(mod, "get_db", lambda: _FakeConn())

    with pytest.raises(HTTPException) as exc:
        mod.update_setting("ga4_measurement_id", {"value": "UA-12345"}, _fake_request())
    assert exc.value.status_code == 400


def test_update_ga4_vacio_apaga(monkeypatch):
    """Vaciar el ID lo borra (clearable) → GA apagado, sin error."""
    import routes.settings as mod

    _admin(monkeypatch, mod)
    fake = _FakeConn()
    monkeypatch.setattr(mod, "get_db", lambda: fake)

    res = mod.update_setting("ga4_measurement_id", {"value": ""}, _fake_request())
    assert res["value"] == ""
