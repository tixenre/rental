"""test_global_exception_handler.py — auditoría de seguridad (identidad/auth/checkout,
2026-07-08): el handler global de excepciones devolvía el tipo + mensaje crudo de
CUALQUIER excepción no manejada a un caller externo, en cualquier ambiente — puede
filtrar nombres de constraint/columna/librería. Ahora: detalle genérico en Railway
(dev/staging incluido — corre con datos copiados de prod, ver MEMORIA — y prod);
solo en local (`RAILWAY_ENVIRONMENT` ausente) se muestra el detalle crudo, para
debug cómodo. El detalle completo SIEMPRE queda en server_errors/logs vía
`log_server_error` (best-effort, no se testea acá).
"""
import pytest
from fastapi.testclient import TestClient

import config
import main

pytestmark = pytest.mark.unit

client = TestClient(main.app, raise_server_exceptions=False)


def _romper_health(monkeypatch, mensaje):
    def _throw():
        raise RuntimeError(mensaje)

    monkeypatch.setattr("migration_state.get_status", _throw)


def test_excepcion_no_manejada_oculta_detalle_en_railway(monkeypatch):
    monkeypatch.setattr(config.settings, "RAILWAY_ENVIRONMENT", "production")
    _romper_health(monkeypatch, "boom-interno-con-detalle-sensible")

    res = client.get("/health")
    assert res.status_code == 500
    detail = res.json()["detail"]
    assert "boom-interno-con-detalle-sensible" not in detail
    assert "RuntimeError" not in detail


def test_excepcion_no_manejada_oculta_detalle_en_dev_staging(monkeypatch):
    """Staging (`dev` en Railway) NO es "confiable" para filtrar detalle — corre
    con una BD copiada de prod (MEMORIA 2026-06-20)."""
    monkeypatch.setattr(config.settings, "RAILWAY_ENVIRONMENT", "dev")
    _romper_health(monkeypatch, "boom-staging-con-detalle-sensible")

    res = client.get("/health")
    assert res.status_code == 500
    detail = res.json()["detail"]
    assert "boom-staging-con-detalle-sensible" not in detail
    assert "RuntimeError" not in detail


def test_excepcion_no_manejada_muestra_detalle_en_local(monkeypatch):
    monkeypatch.setattr(config.settings, "RAILWAY_ENVIRONMENT", None)
    _romper_health(monkeypatch, "boom-debug-local")

    res = client.get("/health")
    assert res.status_code == 500
    detail = res.json()["detail"]
    assert "RuntimeError" in detail
    assert "boom-debug-local" in detail
