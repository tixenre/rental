"""Regresión: el middleware sirve las páginas públicas del SPA por URL directa
(deep link / refresh / crawler) en vez de redirigir a /login.

Cazó la regresión de mover el catálogo de `/` a `/rental`: las páginas públicas
del SPA (URL limpia, no-/api, no-/admin) caían a /login en deep link/refresh
porque solo `/` estaba en PUBLIC_EXACT. /admin y /api siguen protegidos.
"""

import pytest
from fastapi.testclient import TestClient

import main

pytestmark = pytest.mark.unit

client = TestClient(main.app, raise_server_exceptions=False, follow_redirects=False)


class TestMiddlewareSPA:
    def test_paginas_publicas_no_redirigen_a_login(self):
        # Deep link / refresh a una página pública del SPA → la sirve el catch-all
        # (index.html), NO redirige a /login.
        for path in ("/rental", "/workshops", "/estudio", "/preguntas-frecuentes", "/catalogo"):
            res = client.get(path)
            cayo_a_login = res.status_code in (302, 307) and res.headers.get("location") == "/login"
            assert not cayo_a_login, f"{path} redirige a /login; debería servir el SPA"

    def test_admin_sin_sesion_redirige_a_login(self):
        res = client.get("/admin/dashboard")
        assert res.status_code == 307
        assert res.headers.get("location") == "/login"

    def test_api_sin_sesion_401(self):
        res = client.get("/api/cliente/me")
        assert res.status_code == 401
