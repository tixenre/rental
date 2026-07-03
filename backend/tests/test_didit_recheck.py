"""Re-chequeo admin del estado Didit (`POST /admin/verificacion/recheck/{cliente_id}`).

Caso real que motiva el endpoint: Didit rechazó por una razón menor (foto oscura),
el admin revisó el caso a mano *en el dashboard de Didit* y ahí quedó aprobado —
pero eso no llega solo a Rambla. El endpoint re-consulta `retrieve_decision` (fuente
canónica, mismo GET que usa el webhook como respaldo) y aplica el resultado por la
pluma única `identity.kyc` — nunca aprueba a mano.
"""
import pytest
from fastapi import HTTPException

from routes.didit import recheck_verificacion

pytestmark = pytest.mark.unit


class _Cur:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _Conn:
    def __init__(self, row):
        self.row = row

    def execute(self, sql, params=()):
        return _Cur(self.row)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _setup(monkeypatch, *, session_row, decision, aprobar_calls=None, estado_calls=None):
    monkeypatch.setattr("routes.didit.require_admin", lambda request: None)
    monkeypatch.setattr("routes.didit.get_db", lambda: _Conn(session_row))
    monkeypatch.setattr("routes.didit.retrieve_decision", lambda session_id: decision)

    if aprobar_calls is not None:
        def _aprobar(**kw):
            aprobar_calls.append(kw)
            return True
        monkeypatch.setattr("routes.didit.kyc.aprobar", _aprobar)

    if estado_calls is not None:
        def _actualizar(**kw):
            estado_calls.append(kw)
            return True
        monkeypatch.setattr("routes.didit.kyc.actualizar_estado", _actualizar)


def test_cliente_sin_sesion_didit_409(monkeypatch):
    _setup(monkeypatch, session_row={"didit_session_id": None}, decision={})
    with pytest.raises(HTTPException) as exc:
        recheck_verificacion(1, request=object())
    assert exc.value.status_code == 409


def test_cliente_inexistente_404(monkeypatch):
    _setup(monkeypatch, session_row=None, decision={})
    with pytest.raises(HTTPException) as exc:
        recheck_verificacion(1, request=object())
    assert exc.value.status_code == 404


def test_didit_ahora_dice_approved_aplica_kyc_aprobar(monkeypatch):
    """El caso real: Didit lo aprobó a mano tras el reclamo — el recheck lo refleja."""
    aprobar_calls = []
    decision = {
        "status": "Approved",
        "id_verifications": [
            {"status": "Approved", "document_number": "12345678", "full_name": "Juan Pérez"}
        ],
    }
    _setup(
        monkeypatch,
        session_row={"didit_session_id": "sess-1"},
        decision=decision,
        aprobar_calls=aprobar_calls,
    )
    res = recheck_verificacion(7, request=object())
    assert res == {"status": "Approved", "aplicado": True}
    assert len(aprobar_calls) == 1
    assert aprobar_calls[0]["cliente_id"] == 7
    assert aprobar_calls[0]["session_id"] == "sess-1"
    assert aprobar_calls[0]["datos"].dni == "12345678"


def test_didit_sigue_declined_no_re_aprueba(monkeypatch):
    estado_calls = []
    decision = {"status": "Declined", "decline_reason": "Foto oscura"}
    _setup(
        monkeypatch,
        session_row={"didit_session_id": "sess-2"},
        decision=decision,
        estado_calls=estado_calls,
    )
    res = recheck_verificacion(8, request=object())
    assert res == {"status": "Declined", "aplicado": True}
    assert estado_calls[0]["estado"] == "rechazado"
    assert estado_calls[0]["motivo"] == "Foto oscura"


def test_estado_no_accionable_no_llama_kyc(monkeypatch):
    aprobar_calls, estado_calls = [], []
    decision = {"status": "Abandoned"}
    _setup(
        monkeypatch,
        session_row={"didit_session_id": "sess-3"},
        decision=decision,
        aprobar_calls=aprobar_calls,
        estado_calls=estado_calls,
    )
    res = recheck_verificacion(9, request=object())
    assert res == {"status": "Abandoned", "aplicado": None}
    assert aprobar_calls == [] and estado_calls == []


def test_in_review_normaliza_espacio_a_guion_bajo(monkeypatch):
    """La API directa documenta 'In Review' (con espacio); normalizamos antes de comparar."""
    estado_calls = []
    decision = {"status": "In Review"}
    _setup(
        monkeypatch,
        session_row={"didit_session_id": "sess-4"},
        decision=decision,
        estado_calls=estado_calls,
    )
    res = recheck_verificacion(10, request=object())
    assert res == {"status": "In Review", "aplicado": True}
    assert estado_calls[0]["estado"] == "en_revision"
