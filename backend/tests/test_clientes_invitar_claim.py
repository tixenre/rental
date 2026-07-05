"""Rutas de invitación (admin) + claim (cliente) — Fase 4 #1098.

`invitar` (admin, gateado por middleware) se prueba llamando al handler directo (mock de
require_admin + get_db + magic). `claim`/`claim-info` son PÚBLICAS (se reclama con token,
sin sesión) → se prueban por HTTP real (confirma que el middleware las deja pasar) con
el motor `magic` + el minteo mockeados.
"""
import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import main
from routes.clientes import InvitarClienteIn, invitar_cliente

pytestmark = pytest.mark.unit

_http = TestClient(main.app, raise_server_exceptions=False)


class _Cur:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _InvitarConn:
    """Fake de `with get_db() as conn` para invitar (execute + insert_returning).
    `verificado`: dni_validado_at de la cuenta existente (None = sin verificar)."""

    def __init__(self, existing_id=None, new_id=99, verificado=None):
        self.existing_id, self.new_id, self.verificado = existing_id, new_id, verificado

    def execute(self, sql, params=()):
        if self.existing_id:
            return _Cur({"id": self.existing_id, "dni_validado_at": self.verificado})
        return _Cur(None)

    def insert_returning(self, sql, params=(), **kw):
        return self.new_id

    def commit(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _CtxConn:
    """Fake de `with get_db() as conn` para claim/claim-info (SELECT → row)."""

    def __init__(self, row):
        self.row = row

    def execute(self, sql, params=()):
        return _Cur(self.row)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# ── invitar (admin, handler directo) ──────────────────────────────────────────

def test_invitar_crea_cuenta_nueva(monkeypatch):
    monkeypatch.setattr("routes.clientes.require_admin", lambda request: None)
    monkeypatch.setattr("routes.clientes.get_db", lambda: _InvitarConn(existing_id=None, new_id=42))
    monkeypatch.setattr("routes.clientes.magic_commands.crear", lambda **kw: "TOK")
    res = invitar_cliente(InvitarClienteIn(email="Nuevo@X.com", nombre="Ana"), request=object())
    assert res["cliente_id"] == 42 and res["ya_existia"] is False
    assert "TOK" in res["url"] and "/cliente/claim?t=" in res["url"]


def test_invitar_reusa_cuenta_sin_verificar(monkeypatch):
    monkeypatch.setattr("routes.clientes.require_admin", lambda request: None)
    monkeypatch.setattr("routes.clientes.get_db", lambda: _InvitarConn(existing_id=7, verificado=None))
    monkeypatch.setattr("routes.clientes.magic_commands.crear", lambda **kw: "T")
    res = invitar_cliente(InvitarClienteIn(email="ya@x.com"), request=object())
    assert res["cliente_id"] == 7 and res["ya_existia"] is True  # no duplica; sin verificar → OK


def test_invitar_cuenta_verificada_se_rechaza(monkeypatch):
    # Anti-takeover: una cuenta ya verificada NO se invita por link (se recupera por Didit).
    monkeypatch.setattr("routes.clientes.require_admin", lambda request: None)
    monkeypatch.setattr(
        "routes.clientes.get_db", lambda: _InvitarConn(existing_id=7, verificado="2026-06-29T12:00:00")
    )
    with pytest.raises(HTTPException) as ei:
        invitar_cliente(InvitarClienteIn(email="verificado@x.com"), request=object())
    assert ei.value.status_code == 400 and "verificada" in ei.value.detail


def test_invitar_email_invalido_400(monkeypatch):
    monkeypatch.setattr("routes.clientes.require_admin", lambda request: None)
    with pytest.raises(HTTPException) as ei:
        invitar_cliente(InvitarClienteIn(email="sinarroba"), request=object())
    assert ei.value.status_code == 400


# ── claim / claim-info (públicas, por HTTP) ───────────────────────────────────

def test_claim_info_invalido_400(monkeypatch):
    monkeypatch.setattr("auth.queries.magic.peek", lambda t, *, purpose: None)
    r = _http.get("/api/cliente/claim-info?t=bad")
    assert r.status_code == 400  # pública (no 401) + token malo → 400


def test_claim_info_ok(monkeypatch):
    monkeypatch.setattr("auth.queries.magic.peek", lambda t, *, purpose: {"cliente_id": 5, "email": "a@b.com"})
    monkeypatch.setattr("routes.cliente_portal.cuenta.get_db", lambda: _CtxConn({"nombre": "Ana"}))
    r = _http.get("/api/cliente/claim-info?t=ok")
    assert r.status_code == 200
    assert r.json() == {"email": "a@b.com", "nombre": "Ana"}


def test_claim_invalido_400(monkeypatch):
    monkeypatch.setattr("auth.commands.magic.consumir", lambda token, *, purpose: None)
    r = _http.post("/api/cliente/claim", json={"token": "x"})
    assert r.status_code == 400


def test_claim_ok_mintea_sesion(monkeypatch):
    monkeypatch.setattr(
        "auth.commands.magic.consumir", lambda token, *, purpose: {"cliente_id": 5, "email": "a@b.com"}
    )
    monkeypatch.setattr(
        "routes.cliente_portal.cuenta.get_db", lambda: _CtxConn({"id": 5, "nombre": "Ana"})
    )
    linked = []
    monkeypatch.setattr(
        "auth.commands.identities.link_identity", lambda **kw: linked.append(kw) or "linked"
    )
    monkeypatch.setattr(
        "routes.cliente_portal.cuenta._make_session_response",
        lambda *a, **k: JSONResponse({"ok": True}),
    )
    r = _http.post("/api/cliente/claim", json={"token": "t"})
    assert r.status_code == 200
    assert linked and linked[0]["method"] == "email" and linked[0]["identifier"] == "a@b.com"
