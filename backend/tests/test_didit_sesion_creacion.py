"""Al crear una sesión de verificación Didit (admin o cliente), se registra un
evento "iniciado" en `kyc_events` YA — sin esperar a que el webhook llegue.

Motivo: `_sesiones_conocidas` (el historial que usa el recheck admin) se arma
leyendo `kyc_events`. Si el webhook de Didit nunca llega para una sesión —la
falla de origen que motiva todo el recheck—, esa sesión no dejaba ningún
rastro y el historial no la podía encontrar aunque Didit la hubiera decidido.
Registrar "iniciado" en el momento de la creación cierra ese hueco.
"""
import pytest

from routes.didit import cliente_iniciar_verificacion, iniciar_verificacion
from services.didit import DiditSession

pytestmark = pytest.mark.unit


class _Cur:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _Conn:
    def __init__(self, row=None):
        self.row = row
        self.executed = []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        return _Cur(self.row)

    def commit(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_admin_registra_iniciado_al_crear_sesion(monkeypatch):
    eventos = []
    monkeypatch.setattr("routes.didit.require_admin", lambda request: None)
    monkeypatch.setattr("routes.didit.get_db", lambda: _Conn(row={"id": 1}))
    monkeypatch.setattr(
        "routes.didit.create_session",
        lambda **kw: DiditSession(session_id="sess-nueva", url="https://verify.didit.me/x"),
    )
    monkeypatch.setattr(
        "routes.didit.kyc.registrar_evento",
        lambda conn, cliente_id, evento, detalle=None, session_id=None: eventos.append(
            (cliente_id, evento, session_id)
        ),
    )
    res = iniciar_verificacion(1, request=object())
    assert res == {"session_id": "sess-nueva", "url": "https://verify.didit.me/x"}
    assert eventos == [(1, "iniciado", "sess-nueva")]


def test_cliente_registra_iniciado_al_crear_su_sesion(monkeypatch):
    eventos = []
    monkeypatch.setattr("routes.didit.require_cliente", lambda request: {"cliente_id": 7})
    monkeypatch.setattr("routes.didit.get_db", lambda: _Conn())
    monkeypatch.setattr(
        "routes.didit.create_session",
        lambda **kw: DiditSession(session_id="sess-cliente", url="https://verify.didit.me/y"),
    )
    monkeypatch.setattr(
        "routes.didit.kyc.registrar_evento",
        lambda conn, cliente_id, evento, detalle=None, session_id=None: eventos.append(
            (cliente_id, evento, session_id)
        ),
    )
    monkeypatch.setattr("routes.didit.kyc.registrar_consentimiento", lambda cliente_id: None)
    res = cliente_iniciar_verificacion(request=object(), body=None)
    assert res == {"session_id": "sess-cliente", "url": "https://verify.didit.me/y"}
    assert eventos == [(7, "iniciado", "sess-cliente")]
