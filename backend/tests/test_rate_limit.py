"""Tests de rate limiting + resolución de IP del cliente (#503).

- `get_client_ip`: resistente a spoofing de X-Forwarded-For (toma la IP que
  agregó el proxy de confianza, contando hops desde la derecha).
- Endpoints de registro (`/api/cliente/registro*`): cortan con 429 al exceder
  el límite por IP.
"""

import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

pytestmark = pytest.mark.unit


class FakeReq:
    """Request mínimo con headers + client.host para get_client_ip."""
    class _Client:
        def __init__(self, host):
            self.host = host

    def __init__(self, headers=None, client_host="5.5.5.5"):
        self.headers = headers or {}
        self.client = self._Client(client_host) if client_host else None


def _reload_net_utils(monkeypatch, hops):
    """Recarga net_utils con TRUSTED_PROXY_HOPS dado (se lee en import time)."""
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", str(hops))
    import net_utils
    return importlib.reload(net_utils)


class TestGetClientIp:
    def test_sin_xff_usa_client_host(self, monkeypatch):
        nu = _reload_net_utils(monkeypatch, 1)
        assert nu.get_client_ip(FakeReq(client_host="5.5.5.5")) == "5.5.5.5"

    def test_un_hop_toma_la_ultima(self, monkeypatch):
        # 1 proxy de confianza (Railway): la IP real es la última que agregó el proxy.
        nu = _reload_net_utils(monkeypatch, 1)
        req = FakeReq({"x-forwarded-for": "1.1.1.1"})
        assert nu.get_client_ip(req) == "1.1.1.1"

    def test_spoofing_no_funciona_con_un_hop(self, monkeypatch):
        # El atacante manda una IP falsa a la izquierda; el proxy agrega la real
        # a la derecha. Con 1 hop tomamos la derecha → no se puede spoofear.
        nu = _reload_net_utils(monkeypatch, 1)
        req = FakeReq({"x-forwarded-for": "9.9.9.9, 1.1.1.1"})
        assert nu.get_client_ip(req) == "1.1.1.1"

    def test_dos_hops_toma_anteultima(self, monkeypatch):
        # 2 proxies (Cloudflare → Railway): la IP real es la 2da desde la derecha.
        nu = _reload_net_utils(monkeypatch, 2)
        req = FakeReq({"x-forwarded-for": "9.9.9.9, 1.1.1.1, 2.2.2.2"})
        assert nu.get_client_ip(req) == "1.1.1.1"

    def test_menos_entradas_que_hops_no_crashea(self, monkeypatch):
        nu = _reload_net_utils(monkeypatch, 2)
        req = FakeReq({"x-forwarded-for": "1.1.1.1"})
        assert nu.get_client_ip(req) == "1.1.1.1"


def _make_app():
    """App mínima con el router de cliente_portal + el limiter (evita el thread
    de init de DB de main.py)."""
    from rate_limit import limiter
    from routes.cliente_portal import router
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(router)
    return app


class TestRateLimitRegistro:
    def test_registro_info_corta_con_429(self):
        # Límite 5/minute. El path de token inválido responde 400 sin tocar la DB;
        # tras 5 hits, el 6to debe ser 429.
        client = TestClient(_make_app())
        codes = [
            client.get("/api/cliente/registro-info", params={"t": "tok-malo"}).status_code
            for _ in range(7)
        ]
        assert codes.count(429) >= 1, codes
        assert codes[0] == 400  # los primeros pasan el limiter (token inválido → 400)
