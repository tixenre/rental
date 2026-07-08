"""Gate anti-duplicado en `POST /cliente/verificacion/sesion` + self-recheck del
cliente (`POST /cliente/verificacion/recheck`).

Caso real: un cliente cuya identificación queda `en_revision` (o directamente
`rechazado` sin que lo vea) sale del pedido y vuelve a entrar — antes, cada
"Verificar mi identidad" creaba una sesión Didit nueva incondicionalmente,
pisando `didit_session_id` y huerfanando la revisión en curso (hasta 10 veces
en un caso real). Ahora: si sigue `en_revision` tras un recheck en vivo, se
bloquea con 409 en vez de crear una sesión nueva; si el recheck la resolvió
(aprobada o rechazada), se procede con normalidad.
"""
import pytest
from fastapi import HTTPException

from routes.didit import cliente_iniciar_verificacion, cliente_recheck_verificacion
from services.didit import ClienteSinVerificacionError, DiditNotConfiguredError, DiditSession

pytestmark = pytest.mark.unit


class _Cur:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _Conn:
    """Devuelve `estado_row` para cualquier SELECT sobre `clientes` (alcanza para
    el gate, que solo lee `dni_verificacion_estado`/`dni_verificacion_motivo`). El
    cooldown anti-ráfaga (#1169) consulta `kyc_events` aparte — sin fila "reciente"
    acá (None), o quedaría siempre bloqueado con 429."""

    def __init__(self, estado_row):
        self.estado_row = estado_row
        self.executed = []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        if "kyc_events" in sql:
            return _Cur(None)
        return _Cur(self.estado_row)

    def commit(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _cliente_ok(monkeypatch, estado_row, recheck_efecto=None, session_id="sess-nueva"):
    monkeypatch.setattr("routes.didit.require_cliente", lambda request: {"cliente_id": 7})
    monkeypatch.setattr("routes.didit.get_db", lambda: _Conn(estado_row))
    monkeypatch.setattr(
        "routes.didit.create_session",
        lambda **kw: DiditSession(session_id=session_id, url="https://verify.didit.me/y"),
    )
    monkeypatch.setattr("routes.didit.kyc.registrar_evento", lambda *a, **kw: None)
    monkeypatch.setattr("routes.didit.kyc.registrar_consentimiento", lambda cliente_id: None)
    if recheck_efecto is not None:
        monkeypatch.setattr("routes.didit.recheck_cliente", recheck_efecto)


def test_no_verificado_no_dispara_gate_ni_recheck(monkeypatch):
    """Regresión: si nunca hubo intento previo, no se llama a recheck_cliente
    (nada que re-chequear) y se crea la sesión con normalidad."""
    llamado = []
    _cliente_ok(
        monkeypatch,
        estado_row={"dni_verificacion_estado": "no_verificado"},
        recheck_efecto=lambda cliente_id: llamado.append(cliente_id),
    )
    res = cliente_iniciar_verificacion.__wrapped__(request=object(), body=None)
    assert res == {"session_id": "sess-nueva", "url": "https://verify.didit.me/y"}
    assert llamado == []  # el gate solo actúa sobre "en_revision"


def test_en_revision_sigue_en_revision_tras_recheck_bloquea_409(monkeypatch):
    def _estado_iterator():
        # Primera lectura (antes del recheck) y segunda (después) — ambas en_revision.
        yield {"dni_verificacion_estado": "en_revision", "dni_verificacion_motivo": None}
        yield {"dni_verificacion_estado": "en_revision", "dni_verificacion_motivo": None}

    it = _estado_iterator()
    monkeypatch.setattr("routes.didit.require_cliente", lambda request: {"cliente_id": 7})

    class _ConnSecuencial:
        def execute(self, sql, params=()):
            return _Cur(next(it))
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    monkeypatch.setattr("routes.didit.get_db", lambda: _ConnSecuencial())
    monkeypatch.setattr("routes.didit.recheck_cliente", lambda cliente_id: {"status": "In Review"})

    with pytest.raises(HTTPException) as exc:
        cliente_iniciar_verificacion.__wrapped__(request=object(), body=None)
    assert exc.value.status_code == 409


def test_en_revision_resuelta_a_rechazado_por_recheck_permite_reintentar(monkeypatch):
    """El recheck en vivo encontró que Didit ya la había rechazado (webhook
    perdido) — es un reintento legítimo, se crea sesión nueva."""
    def _estado_iterator():
        yield {"dni_verificacion_estado": "en_revision", "dni_verificacion_motivo": None}
        yield {"dni_verificacion_estado": "rechazado", "dni_verificacion_motivo": "Foto oscura"}

    it = _estado_iterator()
    monkeypatch.setattr("routes.didit.require_cliente", lambda request: {"cliente_id": 7})

    class _ConnSecuencial:
        def execute(self, sql, params=()):
            # Solo los dos SELECT de estado (antes/después del recheck) consumen
            # del iterador — el cooldown anti-ráfaga (#1169) sobre `kyc_events` y
            # el UPDATE de didit_session_id que siguen no leen de acá.
            if "SELECT" in sql and "kyc_events" not in sql:
                return _Cur(next(it))
            return _Cur(None)
        def commit(self):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    monkeypatch.setattr("routes.didit.get_db", lambda: _ConnSecuencial())
    monkeypatch.setattr("routes.didit.recheck_cliente", lambda cliente_id: {"status": "Declined"})
    monkeypatch.setattr(
        "routes.didit.create_session",
        lambda **kw: DiditSession(session_id="sess-reintento", url="https://verify.didit.me/z"),
    )
    monkeypatch.setattr("routes.didit.kyc.registrar_evento", lambda *a, **kw: None)
    monkeypatch.setattr("routes.didit.kyc.registrar_consentimiento", lambda cliente_id: None)

    res = cliente_iniciar_verificacion.__wrapped__(request=object(), body=None)
    assert res == {"session_id": "sess-reintento", "url": "https://verify.didit.me/z"}


def test_cooldown_bloquea_sesion_creada_hace_instantes(monkeypatch):
    """#1169 seguimiento — el gate `en_revision` no alcanza a frenar reintentos
    ANTES de que llegue el webhook de Didit (el estado sigue `no_verificado`
    hasta entonces). El cooldown sobre `kyc_events.evento='iniciado'` sí: si el
    cliente ya generó una sesión hace instantes, bloquea con 429 SIN llamar a
    create_session (evita el caso real de #1169: hasta 10 sesiones/persona)."""
    llamado = []

    class _ConnConSesionReciente:
        def execute(self, sql, params=()):
            if "kyc_events" in sql:
                return _Cur(True)  # hay una fila "iniciado" dentro del cooldown
            return _Cur({"dni_verificacion_estado": "no_verificado"})
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    monkeypatch.setattr("routes.didit.require_cliente", lambda request: {"cliente_id": 7})
    monkeypatch.setattr("routes.didit.get_db", lambda: _ConnConSesionReciente())
    monkeypatch.setattr(
        "routes.didit.create_session",
        lambda **kw: llamado.append(1) or DiditSession(session_id="x", url="https://verify.didit.me/x"),
    )

    with pytest.raises(HTTPException) as exc:
        cliente_iniciar_verificacion.__wrapped__(request=object(), body=None)
    assert exc.value.status_code == 429
    assert llamado == []


def test_cliente_recheck_delega_al_motor_compartido(monkeypatch):
    monkeypatch.setattr("routes.didit.require_cliente", lambda request: {"cliente_id": 7})
    monkeypatch.setattr(
        "routes.didit.recheck_cliente",
        lambda cliente_id: {"status": "Approved", "aplicado": True, "session_id": "sess-x"},
    )
    res = cliente_recheck_verificacion.__wrapped__(request=object())
    assert res == {"status": "Approved", "aplicado": True, "session_id": "sess-x"}


def test_cliente_recheck_sin_sesion_conocida_409(monkeypatch):
    monkeypatch.setattr("routes.didit.require_cliente", lambda request: {"cliente_id": 7})

    def _raise(cliente_id):
        raise ClienteSinVerificacionError("nope")

    monkeypatch.setattr("routes.didit.recheck_cliente", _raise)
    with pytest.raises(HTTPException) as exc:
        cliente_recheck_verificacion.__wrapped__(request=object())
    assert exc.value.status_code == 409


def test_cliente_recheck_didit_no_configurado_503(monkeypatch):
    monkeypatch.setattr("routes.didit.require_cliente", lambda request: {"cliente_id": 7})

    def _raise(cliente_id):
        raise DiditNotConfiguredError("no key")

    monkeypatch.setattr("routes.didit.recheck_cliente", _raise)
    with pytest.raises(HTTPException) as exc:
        cliente_recheck_verificacion.__wrapped__(request=object())
    assert exc.value.status_code == 503
