"""Re-chequeo admin del estado Didit (`POST /admin/verificacion/recheck/{cliente_id}`).

Caso real que motiva el endpoint: Didit rechazó por una razón menor (foto oscura),
el admin revisó el caso a mano *en el dashboard de Didit* y ahí quedó aprobado —
pero eso no llega solo a Rambla. El endpoint re-consulta `retrieve_decision` (fuente
canónica, mismo GET que usa el webhook como respaldo) y aplica el resultado por la
pluma única `identity.kyc` — nunca aprueba a mano.

Caso real #2 (el que motiva el historial): el cliente reintentó la verificación
varias veces MIENTRAS el admin revisaba una sesión anterior en Didit — cada
reintento pisa `clientes.didit_session_id` con la sesión nueva, así que la sesión
que terminó aprobada ya no es la "actual". El recheck revisa TODO el historial
conocido (`kyc_events`), no solo la sesión actual.
"""
import pytest
from fastapi import HTTPException

from routes.didit import recheck_verificacion

pytestmark = pytest.mark.unit


class _Cur:
    def __init__(self, rows):
        self._rows = rows if isinstance(rows, list) else ([rows] if rows is not None else [])

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _Conn:
    """Fake de `with get_db() as conn`: distingue la query por `clientes` (una
    fila) de la de `kyc_events` (historial, varias filas) mirando el SQL."""

    def __init__(self, session_row, historial_session_ids=()):
        self.session_row = session_row
        self.historial = [{"session_id": s} for s in historial_session_ids]

    def execute(self, sql, params=()):
        if "kyc_events" in sql:
            return _Cur(self.historial)
        if "UPDATE clientes" in sql:
            return _Cur(None)
        return _Cur(self.session_row)

    def commit(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _setup(
    monkeypatch,
    *,
    session_row,
    decisiones,
    historial_session_ids=(),
    aprobar_calls=None,
    estado_calls=None,
):
    """`decisiones`: dict session_id -> decision (o excepción-lanzadora) que
    `retrieve_decision` devuelve para esa sesión puntual."""
    monkeypatch.setattr("routes.didit.require_admin", lambda request: None)
    monkeypatch.setattr("routes.didit.get_db", lambda: _Conn(session_row, historial_session_ids))

    def _retrieve(session_id):
        d = decisiones.get(session_id, {})
        if callable(d):
            return d()
        return d

    monkeypatch.setattr("routes.didit.retrieve_decision", _retrieve)

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
    _setup(monkeypatch, session_row={"didit_session_id": None}, decisiones={})
    with pytest.raises(HTTPException) as exc:
        recheck_verificacion(1, request=object())
    assert exc.value.status_code == 409


def test_cliente_inexistente_404(monkeypatch):
    _setup(monkeypatch, session_row=None, decisiones={})
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
        decisiones={"sess-1": decision},
        aprobar_calls=aprobar_calls,
    )
    res = recheck_verificacion(7, request=object())
    assert res == {"status": "Approved", "aplicado": True, "session_id": "sess-1"}
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
        decisiones={"sess-2": decision},
        estado_calls=estado_calls,
    )
    res = recheck_verificacion(8, request=object())
    assert res == {"status": "Declined", "aplicado": True, "session_id": "sess-2"}
    assert estado_calls[0]["estado"] == "rechazado"
    assert estado_calls[0]["motivo"] == "Foto oscura"


def test_estado_no_accionable_no_llama_kyc(monkeypatch):
    aprobar_calls, estado_calls = [], []
    decision = {"status": "Abandoned"}
    _setup(
        monkeypatch,
        session_row={"didit_session_id": "sess-3"},
        decisiones={"sess-3": decision},
        aprobar_calls=aprobar_calls,
        estado_calls=estado_calls,
    )
    res = recheck_verificacion(9, request=object())
    assert res == {"status": "Abandoned", "aplicado": None, "session_id": "sess-3"}
    assert aprobar_calls == [] and estado_calls == []


def test_in_review_normaliza_espacio_a_guion_bajo(monkeypatch):
    """La API directa documenta 'In Review' (con espacio); normalizamos antes de comparar."""
    estado_calls = []
    decision = {"status": "In Review"}
    _setup(
        monkeypatch,
        session_row={"didit_session_id": "sess-4"},
        decisiones={"sess-4": decision},
        estado_calls=estado_calls,
    )
    res = recheck_verificacion(10, request=object())
    assert res == {"status": "In Review", "aplicado": True, "session_id": "sess-4"}
    assert estado_calls[0]["estado"] == "en_revision"


def test_reintentos_mientras_se_revisaba_encuentra_la_aprobada_en_el_historial(monkeypatch):
    """El caso real #2: el cliente reintentó varias veces mientras el admin
    revisaba una sesión vieja en Didit — `didit_session_id` ahora apunta a una
    sesión NUEVA todavía "En revisión", pero una sesión anterior del historial
    (`kyc_events`) sí quedó Aprobada. El recheck la encuentra y la aplica."""
    aprobar_calls = []
    decisiones = {
        "sess-nueva": {"status": "In Review"},  # la que `clientes.didit_session_id` rastrea hoy
        "sess-vieja-aprobada": {
            "status": "Approved",
            "id_verifications": [{"status": "Approved", "document_number": "999", "full_name": "X"}],
        },
        "sess-mas-vieja-rechazada": {"status": "Declined"},
    }
    _setup(
        monkeypatch,
        session_row={"didit_session_id": "sess-nueva"},
        decisiones=decisiones,
        historial_session_ids=["sess-nueva", "sess-vieja-aprobada", "sess-mas-vieja-rechazada"],
        aprobar_calls=aprobar_calls,
    )
    res = recheck_verificacion(11, request=object())
    assert res == {"status": "Approved", "aplicado": True, "session_id": "sess-vieja-aprobada"}
    assert aprobar_calls[0]["session_id"] == "sess-vieja-aprobada"


def test_sin_aprobada_en_el_historial_reporta_la_sesion_actual(monkeypatch):
    """Si ninguna sesión del historial está aprobada, reporta la actual (comportamiento
    previo, sin historial) — no hay nada mejor que ofrecer."""
    estado_calls = []
    decisiones = {
        "sess-actual": {"status": "In Review"},
        "sess-vieja": {"status": "Declined"},
    }
    _setup(
        monkeypatch,
        session_row={"didit_session_id": "sess-actual"},
        decisiones=decisiones,
        historial_session_ids=["sess-actual", "sess-vieja"],
        estado_calls=estado_calls,
    )
    res = recheck_verificacion(12, request=object())
    assert res == {"status": "In Review", "aplicado": True, "session_id": "sess-actual"}


def test_sesion_del_historial_expirada_no_aborta_la_busqueda(monkeypatch):
    """Una sesión vieja puede haber expirado/borrado en Didit (404) — no debe
    frenar la búsqueda de las demás candidatas."""
    import httpx

    aprobar_calls = []

    def _expirada():
        raise httpx.HTTPStatusError(
            "not found", request=httpx.Request("GET", "https://x"),
            response=httpx.Response(404, request=httpx.Request("GET", "https://x")),
        )

    decisiones = {
        "sess-actual": {"status": "In Review"},
        "sess-expirada": _expirada,
        "sess-aprobada": {
            "status": "Approved",
            "id_verifications": [{"status": "Approved", "document_number": "111", "full_name": "Y"}],
        },
    }
    _setup(
        monkeypatch,
        session_row={"didit_session_id": "sess-actual"},
        decisiones=decisiones,
        historial_session_ids=["sess-actual", "sess-expirada", "sess-aprobada"],
        aprobar_calls=aprobar_calls,
    )
    res = recheck_verificacion(13, request=object())
    assert res == {"status": "Approved", "aplicado": True, "session_id": "sess-aprobada"}
