"""Ruta de fusión de clientes del back-office (Fase 2 #1098) — transporte fino.

La lógica vive en identity/merge (testeada en test_identity_merge*.py); acá clavamos el
contrato del handler llamándolo directo (la protección de admin a nivel HTTP la da el
middleware + require_admin, cubierto por los tests de auth): gateo por admin, delegación
al motor, y los 400 (self-merge + ValueError del motor → 400, no 500).
"""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import main
from routes.clientes import MergeClientesIn, merge_clientes

pytestmark = pytest.mark.unit

_http = TestClient(main.app, raise_server_exceptions=False)


def test_duplicados_no_colisiona_con_clientes_id_http():
    """Regresión de ORDEN de rutas (cazada por el supervisor): `/clientes/duplicados` se
    declara ANTES de `/clientes/{id}`. Si no, `/{id}` captura "duplicados" como id → 422
    (la feature entera muere). Bien ordenado, resuelve al handler → require_admin → 401.
    Pega al HTTP real: los tests de handler directo (abajo) NO cazan esta colisión."""
    r = _http.get("/api/clientes/duplicados")
    assert r.status_code != 422, "/clientes/duplicados capturada por /clientes/{id} — reordenar"
    assert r.status_code in (401, 403)  # ruta resuelta → gateó por admin (sin sesión → 401)


def test_merge_chequea_admin_y_delega(monkeypatch):
    admin_calls, merge_calls = [], []
    monkeypatch.setattr("routes.clientes.require_admin", lambda request: admin_calls.append(1))
    monkeypatch.setattr(
        "routes.clientes.merge.merge_accounts",
        lambda *, source, target: merge_calls.append((source, target)),
    )
    res = merge_clientes(MergeClientesIn(source=5, target=9), request=object())
    assert admin_calls  # gateó por admin antes de tocar nada
    assert merge_calls == [(5, 9)]  # source→target, una sola vez
    assert res["merged_into"] == 9


def test_merge_self_400(monkeypatch):
    monkeypatch.setattr("routes.clientes.require_admin", lambda request: None)
    merge_calls = []
    monkeypatch.setattr("routes.clientes.merge.merge_accounts", lambda **kw: merge_calls.append(kw))
    with pytest.raises(HTTPException) as ei:
        merge_clientes(MergeClientesIn(source=3, target=3), request=object())
    assert ei.value.status_code == 400
    assert not merge_calls  # ni siquiera toca el motor


def test_merge_value_error_es_400(monkeypatch):
    monkeypatch.setattr("routes.clientes.require_admin", lambda request: None)

    def _raise(*, source, target):
        raise ValueError("son dos personas, no un duplicado")

    monkeypatch.setattr("routes.clientes.merge.merge_accounts", _raise)
    with pytest.raises(HTTPException) as ei:
        merge_clientes(MergeClientesIn(source=1, target=2), request=object())
    assert ei.value.status_code == 400
    assert "dos personas" in ei.value.detail
