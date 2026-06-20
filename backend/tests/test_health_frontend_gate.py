"""El healthcheck `/health/frontend` (gate de deploy de Railway) debe responder
503 si el SPA no se sirve y 200 si sí.

Es la red que faltó en la caída de prod (#930): staging no cubría "el backend
Railway sirviendo el SPA" porque el front de dev va por Vercel. Con este gate
apuntado desde `railway.json`, un deploy que no puede servir el frontend falla el
healthcheck y NO se promueve (ni staging ni prod). Hermético (fakea el dist).
"""
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


def test_health_frontend_503_si_falta_el_spa(monkeypatch, tmp_path):
    import main

    monkeypatch.setattr(main, "FRONT_NEW", tmp_path)  # tmp vacío → sin index.html
    res = TestClient(main.app, raise_server_exceptions=False).get("/health/frontend")
    assert res.status_code == 503
    assert res.json()["frontend"] == "not_built"


def test_health_frontend_200_con_spa(monkeypatch, tmp_path):
    import main

    (tmp_path / "index.html").write_text("<!DOCTYPE html>")
    monkeypatch.setattr(main, "FRONT_NEW", tmp_path)
    res = TestClient(main.app, raise_server_exceptions=False).get("/health/frontend")
    assert res.status_code == 200
    assert res.json()["frontend"] == "served"
