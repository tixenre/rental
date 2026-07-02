"""Tests de services.facturacion.padron — resolver_persona() es best-effort:
elige cualquier emisor activo con cert para autenticar, y CUALQUIER falla
(sin emisor disponible, AFIP caído, CUIT sin datos) degrada a None, nunca
levanta — es una comodidad de autocompletado, no algo que pueda romper un
formulario."""
from __future__ import annotations

from datetime import datetime

import pytest

from arca_fe.padron import WSAA_SERVICIO
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
    # Regresión: "ws_sr_padron_a5" es el id VIEJO — AFIP lo deprecó y renombró
    # el servicio a "ws_sr_constancia_inscripcion" (manual oficial
    # WS_SR_constancia_inscripcion v3.7); pedirle el TA a WSAA con el id viejo
    # hace que la relación no matchee y la consulta degrade silenciosamente a
    # "no se pudo autocompletar" — bug real de prod con un CUIT válido.
    assert captured["servicio"] == WSAA_SERVICIO == "ws_sr_constancia_inscripcion"


def test_falla_real_levanta_runtime_error_con_motivo(monkeypatch):
    """AFIP caído / relación de padrón no delegada / cert vencido — NO se
    swallowea a None: eso diría "ARCA no tiene datos" cuando en realidad no
    pudimos ni preguntarle, imposible de diagnosticar desde afuera. Levanta
    RuntimeError con el motivo real; el route (admin-only) lo muestra tal
    cual — nunca rompe el formulario (sigue editable a mano), pero ya no
    miente sobre la causa."""
    monkeypatch.setattr(
        "services.facturacion.emisores_repo.list_emisores",
        lambda conn: [_emisor()],
    )
    monkeypatch.setattr(
        "services.facturacion.config.credenciales",
        lambda emisor, conn: (_ for _ in ()).throw(RuntimeError("cert vencido")),
    )
    with pytest.raises(RuntimeError, match="cert vencido"):
        resolver_persona("30712345678", conn=object())


def test_bloqueo_de_negocio_de_afip_se_propaga_sin_doble_envoltorio(monkeypatch):
    """`get_persona` puede levantar RuntimeError con el mensaje de negocio de
    AFIP en texto plano (ej. bloqueo por Domicilio Fiscal Electrónico, RG
    3990-E) — resolver_persona lo deja pasar tal cual, sin envolverlo de
    nuevo con el genérico "No se pudo consultar el padrón con el emisor...",
    que le restaría legibilidad al mensaje que el admin tiene que leer."""
    monkeypatch.setattr(
        "services.facturacion.emisores_repo.list_emisores",
        lambda conn: [_emisor()],
    )

    class _FakeCred:
        ambiente = "homologacion"
        cuit = 20300000000

    monkeypatch.setattr(
        "services.facturacion.config.credenciales", lambda emisor, conn: _FakeCred()
    )
    monkeypatch.setattr(
        "services.facturacion.wsaa_cache.get_ta",
        lambda emisor, conn, servicio=None: ("tok", "sign"),
    )
    mensaje_afip = (
        "No consta en nuestros registros que Ud. ha cumplido con la adhesión "
        "al domicilio fiscal electrónico"
    )
    monkeypatch.setattr(
        "arca_fe.padron.PadronClient.get_persona",
        lambda self, cuit: (_ for _ in ()).throw(RuntimeError(mensaje_afip)),
    )

    with pytest.raises(RuntimeError, match=mensaje_afip):
        resolver_persona("23373891029", conn=object())
