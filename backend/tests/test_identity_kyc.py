"""Tests de identity/kyc — orquestación del KYC.

FakeConn recorder que soporta `transaction()` y responde el SELECT de
didit_session_id (para pasar `_session_coincide`). Valida que aprobar/actualizar_estado
escriban la identidad/estado, anclen el CUIL (mod-11), guarden contactos y dejen evento.
"""
from contextlib import contextmanager

import pytest

from identity import kyc
from services.didit.decision import ContactoVerificado, ContactosVerificados, DatosRenaper

pytestmark = pytest.mark.unit


class _Cur:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row

    def fetchall(self):
        return []


class _Recorder:
    """Conn fake: graba execute(); soporta transaction(); el SELECT de
    didit_session_id devuelve el `session_id` esperado."""

    def __init__(self, session_id):
        self.session_id = session_id
        self.calls = []

    def execute(self, sql, params=()):
        norm = " ".join(sql.split())
        self.calls.append((norm, tuple(params)))
        if "SELECT didit_session_id" in norm:
            return _Cur({"didit_session_id": self.session_id})
        return _Cur(None)

    @contextmanager
    def transaction(self):
        yield self

    def commit(self):
        pass

    def close(self):
        pass


def _patch(monkeypatch, rec):
    monkeypatch.setattr("identity.kyc.get_db", lambda: rec)


def _sql(rec, needle):
    return [c for c in rec.calls if needle in c[0]]


def test_actualizar_estado_rechazado(monkeypatch):
    rec = _Recorder("sess-1")
    _patch(monkeypatch, rec)
    assert kyc.actualizar_estado(cliente_id=1, session_id="sess-1", estado="rechazado", motivo="x") is True
    upd = _sql(rec, "dni_verificacion_estado")
    assert upd and upd[0][1][0] == "rechazado" and upd[0][1][1] == "x"
    assert _sql(rec, "INSERT INTO kyc_events")  # bitácora


def test_actualizar_estado_session_no_coincide(monkeypatch):
    rec = _Recorder("otra-sess")
    _patch(monkeypatch, rec)
    assert kyc.actualizar_estado(cliente_id=1, session_id="sess-1", estado="rechazado") is False
    assert not _sql(rec, "UPDATE clientes")  # vendor_data forjado / carrera → no aplica


def test_aprobar_ancla_identidad_contactos_y_evento(monkeypatch):
    rec = _Recorder("sess-1")
    _patch(monkeypatch, rec)
    datos = DatosRenaper(dni="12345678", cuil="20123456786",
                         nombre_completo="Juan Pérez", direccion="Av. Corrientes 1234")
    contactos = ContactosVerificados(
        email=ContactoVerificado(kind="email", value="juan@gmail.com"),
        phone=ContactoVerificado(kind="phone", value="+5492235551234"),
    )
    assert kyc.aprobar(cliente_id=1, session_id="sess-1", datos=datos, contactos=contactos) is True
    params = _sql(rec, "dni_validado_at")[0][1]
    assert "12345678" in params and "20123456786" in params  # dni + CUIL válido anclados
    assert _sql(rec, "INSERT INTO verified_contacts")  # contactos verificados
    assert _sql(rec, "INSERT INTO kyc_events")  # evento de auditoría


def test_aprobar_cuil_invalido_no_se_ancla(monkeypatch):
    rec = _Recorder("sess-1")
    _patch(monkeypatch, rec)
    datos = DatosRenaper(dni="12345678", cuil="20-12345678-9")  # dígito verificador malo
    assert kyc.aprobar(cliente_id=1, session_id="sess-1", datos=datos) is True
    params = _sql(rec, "dni_validado_at")[0][1]
    assert "20123456789" not in params  # CUIL inválido NO se ancla (mod-11)


def test_consentimiento(monkeypatch):
    rec = _Recorder("sess-1")
    _patch(monkeypatch, rec)
    kyc.registrar_consentimiento(1)
    assert _sql(rec, "kyc_consent_at")  # marca el consentimiento
    assert _sql(rec, "INSERT INTO kyc_events")
