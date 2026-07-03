"""Barrido automático de verificaciones Didit abandonadas (`jobs/recheck_didit_pendientes.py`).

Cubre el caso que el gate de `cliente_iniciar_verificacion` y el self-recheck del
front no alcanzan: el cliente que abandona del todo y no vuelve a interactuar con
el sitio. El job corre server-side (scheduler) sin depender de que vuelva."""
import pytest

from jobs.recheck_didit_pendientes import recheck_verificaciones_pendientes
from services.didit import ClienteSinVerificacionError, DiditNotConfiguredError

pytestmark = pytest.mark.unit


class _Cur:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=()):
        return _Cur(self.rows)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_sin_pendientes_no_llama_a_recheck(monkeypatch):
    llamados = []
    monkeypatch.setattr("jobs.recheck_didit_pendientes.get_db", lambda: _Conn([]))
    monkeypatch.setattr("jobs.recheck_didit_pendientes.recheck_cliente", lambda cid: llamados.append(cid))
    n = recheck_verificaciones_pendientes()
    assert n == 0
    assert llamados == []


def test_rechequea_cada_cliente_pendiente(monkeypatch):
    llamados = []
    monkeypatch.setattr(
        "jobs.recheck_didit_pendientes.get_db", lambda: _Conn([{"id": 1}, {"id": 2}, {"id": 3}])
    )
    monkeypatch.setattr("jobs.recheck_didit_pendientes.recheck_cliente", lambda cid: llamados.append(cid))
    n = recheck_verificaciones_pendientes()
    assert n == 3
    assert llamados == [1, 2, 3]


def test_un_cliente_sin_sesion_no_frena_el_resto(monkeypatch):
    """No debería pasar (la query ya filtra por didit_session_id IS NOT NULL),
    pero si pasara, un ClienteSinVerificacionError puntual no debe abortar el resto."""
    llamados = []

    def _recheck(cid):
        if cid == 2:
            raise ClienteSinVerificacionError("raro")
        llamados.append(cid)

    monkeypatch.setattr(
        "jobs.recheck_didit_pendientes.get_db", lambda: _Conn([{"id": 1}, {"id": 2}, {"id": 3}])
    )
    monkeypatch.setattr("jobs.recheck_didit_pendientes.recheck_cliente", _recheck)
    n = recheck_verificaciones_pendientes()
    assert llamados == [1, 3]
    assert n == 2  # el 2 no cuenta como re-chequeado


def test_didit_no_configurado_corta_la_corrida(monkeypatch):
    """Si la feature está apagada, no tiene sentido seguir intentando el resto."""
    llamados = []

    def _recheck(cid):
        llamados.append(cid)
        raise DiditNotConfiguredError("no key")

    monkeypatch.setattr(
        "jobs.recheck_didit_pendientes.get_db", lambda: _Conn([{"id": 1}, {"id": 2}])
    )
    monkeypatch.setattr("jobs.recheck_didit_pendientes.recheck_cliente", _recheck)
    n = recheck_verificaciones_pendientes()
    assert llamados == [1]  # corta después del primero
    assert n == 0


def test_error_puntual_no_frena_el_resto(monkeypatch):
    llamados = []

    def _recheck(cid):
        llamados.append(cid)
        if cid == 1:
            raise RuntimeError("Didit no respondió")

    monkeypatch.setattr(
        "jobs.recheck_didit_pendientes.get_db", lambda: _Conn([{"id": 1}, {"id": 2}])
    )
    monkeypatch.setattr("jobs.recheck_didit_pendientes.recheck_cliente", _recheck)
    n = recheck_verificaciones_pendientes()
    assert llamados == [1, 2]
    assert n == 1
