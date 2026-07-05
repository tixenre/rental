"""Candado de robustez de `routes/checkout.py::checkout_validar` (HTTP layer).

El portero (`services.checkout.validar.validar_checkout`) ya aísla cada check
(`_run_check`, ver test_checkout_portero.py) — esto cubre la red RESIDUAL del
route: si algo revienta ANTES/fuera de esos checks (ej. un bug en el propio
`validar_checkout`, o algo que escapa al aislamiento), el cliente tiene que
recibir un 503 limpio, nunca un 500 crudo con detalle interno.
"""
import contextlib

import pytest
from fastapi.testclient import TestClient

import main
from auth.session import signer

pytestmark = pytest.mark.unit

client = TestClient(main.app, raise_server_exceptions=False)

_COOKIE_CLIENTE = f"session={signer.dumps({'email': 'checkout-robustez@test.com', 'role': 'cliente', 'cliente_id': 1, 'jti': 'checkout-robustez-cli'})}"


@pytest.fixture(autouse=True)
def _sessions_active(monkeypatch):
    monkeypatch.setattr("auth.queries.sessions.is_active", lambda jti: {"jti": jti})


def test_checkout_validar_error_inesperado_devuelve_503_limpio(monkeypatch):
    def _explota(*args, **kwargs):
        raise RuntimeError("bug interno de prueba — no debería llegar al cliente")

    # `validar_checkout` es lo que revienta acá — `get_db()` se mockea para no
    # necesitar Postgres real (el `conn` nunca se usa, `_explota` lo ignora).
    @contextlib.contextmanager
    def _fake_get_db():
        yield object()

    monkeypatch.setattr("routes.checkout.get_db", _fake_get_db)
    monkeypatch.setattr("routes.checkout.validar_checkout", _explota)

    res = client.post(
        "/api/checkout/validar",
        json={"session_id": "11111111-1111-1111-1111-111111111111"},
        headers={"Cookie": _COOKIE_CLIENTE},
    )
    assert res.status_code == 503
    body = res.json()
    assert "bug interno de prueba" not in body["detail"]
    assert "Reintentá" in body["detail"]
