"""Tests de services.facturacion.padron — resolver_persona() es best-effort:
elige cualquier emisor activo con cert para autenticar, y CUALQUIER falla
(sin emisor disponible, AFIP caído, CUIT sin datos) degrada a None, nunca
levanta — es una comodidad de autocompletado, no algo que pueda romper un
formulario."""
from __future__ import annotations

from datetime import datetime

import pytest

from services.facturacion.emisores_repo import EmisorArca
from services.facturacion.padron import resolver_persona

pytestmark = pytest.mark.unit


def _emisor(nombre="pablo", activo=True, cert_cargado=True):
    return EmisorArca(
        id=1, nombre=nombre, cuit="20300000000", pto_vta=1,
        condicion_iva="responsable_inscripto", cert_cargado=cert_cargado,
        activo=activo, razon_social=None, domicilio=None, iibb=None,
        inicio_actividades=None, notas=None,
        created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1),
    )


def test_sin_emisor_activo_con_cert_devuelve_none(monkeypatch):
    monkeypatch.setattr(
        "services.facturacion.emisores_repo.list_emisores",
        lambda conn: [_emisor(activo=False), _emisor(cert_cargado=False)],
    )
    assert resolver_persona("20301234567", conn=object()) is None


def test_usa_el_primer_emisor_activo_con_cert(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        "services.facturacion.emisores_repo.list_emisores",
        lambda conn: [_emisor(nombre="pablo")],
    )

    class _FakeCred:
        ambiente = "homologacion"
        cuit = 20300000000

    monkeypatch.setattr(
        "services.facturacion.config.credenciales",
        lambda emisor, conn: (captured.setdefault("emisor", emisor), _FakeCred())[1],
    )
    monkeypatch.setattr(
        "services.facturacion.wsaa_cache.get_ta",
        lambda emisor, conn, servicio=None: (captured.setdefault("servicio", servicio), ("tok", "sign"))[1],
    )

    class _FakePersona:
        razon_social = "Empresa XYZ"

    monkeypatch.setattr(
        "arca_fe.padron.PadronClient.get_persona", lambda self, cuit: _FakePersona()
    )

    result = resolver_persona("30712345678", conn=object())

    assert result.razon_social == "Empresa XYZ"
    assert captured["emisor"] == "pablo"
    assert captured["servicio"] == "ws_sr_padron_a5"


def test_cualquier_excepcion_degrada_a_none(monkeypatch):
    """AFIP caído / relación de padrón no delegada / cert vencido — nunca
    levanta, el formulario sigue editable a mano."""
    monkeypatch.setattr(
        "services.facturacion.emisores_repo.list_emisores",
        lambda conn: [_emisor()],
    )
    monkeypatch.setattr(
        "services.facturacion.config.credenciales",
        lambda emisor, conn: (_ for _ in ()).throw(RuntimeError("cert vencido")),
    )
    assert resolver_persona("30712345678", conn=object()) is None
