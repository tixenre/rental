"""Tests de `services/finanzas_flujo/reconciliacion.py::estado` — el semáforo
unificado. Delega 1:1 en los dos `reconciliar()` existentes (mockeados acá; su
lógica interna ya está testeada en `test_reportes_liquidacion_db.py`/
`test_contabilidad_db.py`): acá solo se ejerce que `estado()` los une bien.
"""
from __future__ import annotations

import pytest

from services.finanzas_flujo import reconciliacion as facade

pytestmark = pytest.mark.unit


class TestEstado:
    def test_ambos_ok_da_ok(self, monkeypatch):
        monkeypatch.setattr(
            "reportes.reconciliacion.reconciliar", lambda conn: {"ok": True, "x": 1}
        )
        monkeypatch.setattr(
            "contabilidad.queries.reconciliacion.reconciliar", lambda conn: {"ok": True, "y": 2}
        )
        out = facade.estado(conn=None)
        assert out["ok"] is True
        assert out["reporte"] == {"ok": True, "x": 1}
        assert out["contabilidad"] == {"ok": True, "y": 2}

    def test_reporte_falla_tumba_el_ok_global(self, monkeypatch):
        monkeypatch.setattr(
            "reportes.reconciliacion.reconciliar", lambda conn: {"ok": False}
        )
        monkeypatch.setattr(
            "contabilidad.queries.reconciliacion.reconciliar", lambda conn: {"ok": True}
        )
        assert facade.estado(conn=None)["ok"] is False

    def test_contabilidad_falla_tumba_el_ok_global(self, monkeypatch):
        monkeypatch.setattr(
            "reportes.reconciliacion.reconciliar", lambda conn: {"ok": True}
        )
        monkeypatch.setattr(
            "contabilidad.queries.reconciliacion.reconciliar", lambda conn: {"ok": False}
        )
        assert facade.estado(conn=None)["ok"] is False
