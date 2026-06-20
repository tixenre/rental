"""Gate de verificación de identidad (PR1).

"Verificado" = `clientes.dni_validado_at IS NOT NULL`. El gate rechaza con 403
los flujos de creación de pedido (`POST /api/cliente/pedidos`) y de reserva del
estudio (`POST /api/estudio/reservas`) cuando el cliente no completó la
verificación Didit. Además, la creación de sesión Didit acepta un `return_to`
interno opcional (allowlist anti open-redirect) que se cuela urlencodeado en el
return_url; un `return_to` inválido/ausente cae al fallback (nunca 400).

Tests puros: TestClient (routing + middleware + guards) + monkeypatch de la capa
de DB (`get_db`) y del cliente Didit (`create_session`). Sin DB ni red.
"""

import pytest
from fastapi.testclient import TestClient

import main
from routes.auth import signer
from routes.didit import _es_path_interno_seguro

pytestmark = pytest.mark.unit

client = TestClient(main.app, raise_server_exceptions=False)

# Cookie de cliente firmada con el signer real de la app (mismo SECRET_KEY de tests).
_COOKIE_CLIENTE = f"session={signer.dumps({'email': 'x@test.com', 'role': 'cliente', 'cliente_id': 123})}"


# ── Fakes de DB ───────────────────────────────────────────────────────────────

class _FakeRow(dict):
    """sqlite3.Row-like: subscriptable y .keys()."""


class _FakeCursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row

    def fetchall(self):
        return []


class _FakeConn:
    """Conn fake que siempre devuelve la misma fila de cliente para cualquier
    SELECT. Suficiente para que el gate (único SELECT antes del rechazo) decida."""

    def __init__(self, cliente_row):
        self._row = cliente_row

    def execute(self, sql, params=()):
        return _FakeCursor(self._row)

    def commit(self):
        pass

    def rollback(self):
        # El handler del estudio envuelve todo en try/except → rollback() al
        # propagar (incluso un HTTPException del gate). El conn real lo tiene.
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def close(self):
        pass


def _fake_get_db(cliente_row):
    return lambda: _FakeConn(cliente_row)


# ── Gate: POST /api/cliente/pedidos ───────────────────────────────────────────

_BODY_PEDIDO = {
    "fecha_desde": "2030-01-01T10:00",
    "fecha_hasta": "2030-01-02T10:00",
    "items": [{"equipo_id": 7, "cantidad": 1, "precio_jornada": 1}],
}


def test_pedido_cliente_sin_verificar_devuelve_403(monkeypatch):
    """Cliente con dni_validado_at=None → el gate corta con 403 antes de crear."""
    monkeypatch.setattr(
        "routes.cliente_portal.core.get_db",
        _fake_get_db(_FakeRow(id=123, dni_validado_at=None)),
    )
    res = client.post(
        "/api/cliente/pedidos", json=_BODY_PEDIDO, headers={"Cookie": _COOKIE_CLIENTE}
    )
    assert res.status_code == 403, res.text


def test_pedido_cliente_verificado_no_bloquea_por_identidad(monkeypatch):
    """Cliente verificado → el gate NO bloquea. Puede fallar después por otra
    validación, pero NUNCA con 403 por identidad."""
    monkeypatch.setattr(
        "routes.cliente_portal.core.get_db",
        _fake_get_db(_FakeRow(id=123, dni_validado_at="2026-06-01T10:00:00")),
    )
    res = client.post(
        "/api/cliente/pedidos", json=_BODY_PEDIDO, headers={"Cookie": _COOKIE_CLIENTE}
    )
    assert res.status_code != 403, (
        f"El gate bloqueó por identidad a un cliente verificado → {res.status_code}"
    )


# ── Gate: POST /api/estudio/reservas ──────────────────────────────────────────

_BODY_ESTUDIO = {
    "fecha": "2030-01-01",
    "start": "09:00",
    "horas": 2,
    "con_pack": False,
}


def test_reserva_estudio_sin_verificar_devuelve_403(monkeypatch):
    """Cliente sin verificar → 403 en la reserva del estudio. El handler hace su
    propio SELECT del cliente (al que le agregamos dni_validado_at); la fila del
    estudio (id=1) la sirve el mismo FakeConn antes — devolvemos una fila con
    equipo_id seteado para pasar el chequeo previo y llegar al cliente."""
    fila = _FakeRow(
        id=1, equipo_id=99, nombre="X", apellido="Y", email="x@test.com",
        telefono="1", dni_validado_at=None,
    )
    monkeypatch.setattr("routes.estudio.get_db", _fake_get_db(fila))
    res = client.post(
        "/api/estudio/reservas", json=_BODY_ESTUDIO, headers={"Cookie": _COOKIE_CLIENTE}
    )
    assert res.status_code == 403, res.text


# ── Allowlist anti open-redirect ──────────────────────────────────────────────

@pytest.mark.parametrize(
    "p",
    [
        "/",
        "/x",
        "/?pedido=retomar",
        "/estudio?d=2026-01-01&h=09:00",
    ],
)
def test_path_interno_seguro_acepta(p):
    assert _es_path_interno_seguro(p) is True


@pytest.mark.parametrize(
    "p",
    [
        "",
        None,
        "//evil.com",
        "http://evil",
        "https://x",
        "/\\evil",
        "\\\\evil",
        "/x\n",
        "/" + "a" * 600,
    ],
)
def test_path_interno_seguro_rechaza(p):
    assert _es_path_interno_seguro(p) is False


# ── return_to en la sesión Didit ──────────────────────────────────────────────

class _FakeSession:
    def __init__(self):
        self.session_id = "sess-test"
        self.url = "https://verification.didit.me/redirect"


def _capture_create_session(monkeypatch):
    """Mockea create_session en routes.didit para capturar el return_url y evita
    pegarle a la API real. Mockea también el UPDATE de clientes (get_db)."""
    captured = {}

    def fake_create_session(*, return_url, vendor_data):
        captured["return_url"] = return_url
        return _FakeSession()

    monkeypatch.setattr("routes.didit.create_session", fake_create_session)
    monkeypatch.setattr(
        "routes.didit.get_db", _fake_get_db(_FakeRow(id=123)),
    )
    return captured


def test_sesion_return_to_interno_se_cuela_urlencoded(monkeypatch):
    captured = _capture_create_session(monkeypatch)
    res = client.post(
        "/api/cliente/verificacion/sesion",
        json={"return_to": "/?pedido=retomar"},
        headers={"Cookie": _COOKIE_CLIENTE},
    )
    assert res.status_code == 201, res.text
    ru = captured["return_url"]
    assert "return_to=" in ru
    # Urlencodeado: la barra y el '?' del path interno van escapados (%2F / %3F).
    assert "%2F" in ru


def test_sesion_return_to_externo_cae_al_fallback(monkeypatch):
    captured = _capture_create_session(monkeypatch)
    res = client.post(
        "/api/cliente/verificacion/sesion",
        json={"return_to": "http://evil"},
        headers={"Cookie": _COOKIE_CLIENTE},
    )
    assert res.status_code == 201, res.text
    assert "return_to=" not in captured["return_url"]


def test_sesion_sin_body_sigue_creando(monkeypatch):
    """El portal hoy postea SIN body → no debe romper (no 422); usa el fallback."""
    captured = _capture_create_session(monkeypatch)
    res = client.post(
        "/api/cliente/verificacion/sesion",
        headers={"Cookie": _COOKIE_CLIENTE},
    )
    assert res.status_code == 201, res.text
    assert "return_to=" not in captured["return_url"]
