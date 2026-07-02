"""Tests de arca_fe.padron — sin red. Mockea la respuesta de zeep para el
padrón A13, prueba el parseo de persona física/jurídica, monotributo/RI/exento,
y que un CUIT sin datos (o un fault de AFIP) devuelva None sin explotar."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _persona_juridica(razon_social="Empresa XYZ SRL", con_iva=True):
    persona = MagicMock(spec=["datosGenerales", "datosRegimenGeneral", "datosMonotributo"])
    dg = MagicMock()
    dg.razonSocial = razon_social
    dom = MagicMock()
    dom.direccion = "Ruta 88 km 12"
    dom.localidad = "Mar del Plata"
    dom.descripcionProvincia = "Buenos Aires"
    dg.domicilioFiscal = dom
    persona.datosGenerales = dg
    persona.datosMonotributo = None

    if con_iva:
        dr = MagicMock()
        imp = MagicMock()
        imp.idImpuesto = 32
        dr.impuesto = [imp]
        persona.datosRegimenGeneral = dr
    else:
        persona.datosRegimenGeneral = None
    return persona


def _persona_fisica_monotributo(nombre="Juan", apellido="Pérez"):
    persona = MagicMock(spec=["datosGenerales", "datosMonotributo", "datosRegimenGeneral"])
    dg = MagicMock()
    dg.razonSocial = ""
    dg.nombre = nombre
    dg.apellido = apellido
    dg.domicilioFiscal = None
    persona.datosGenerales = dg
    persona.datosMonotributo = MagicMock()
    persona.datosRegimenGeneral = None
    return persona


def test_get_persona_juridica_responsable_inscripto():
    from arca_fe.padron import PadronClient

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")
    resp = MagicMock()
    resp.persona = _persona_juridica()

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        result = client.get_persona("30-71234567-8")

    assert result is not None
    assert result.razon_social == "Empresa XYZ SRL"
    assert "Ruta 88 km 12" in result.domicilio
    assert result.condicion_iva == "responsable_inscripto"


def test_get_persona_fisica_monotributo_arma_nombre_completo():
    from arca_fe.padron import PadronClient

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")
    resp = MagicMock()
    resp.persona = _persona_fisica_monotributo()

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        result = client.get_persona("20301234567")

    assert result.razon_social == "Juan Pérez"
    assert result.condicion_iva == "monotributo"
    assert result.domicilio == ""


def test_get_persona_fisica_expone_nombre_y_apellido_por_separado():
    """Un formulario con campos Nombre/Apellido separados (cliente) no tiene
    que quedarse solo con el combinado — AFIP los da separados, no hay que
    tirarlos."""
    from arca_fe.padron import PadronClient

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")
    resp = MagicMock()
    resp.persona = _persona_fisica_monotributo(nombre="Juan", apellido="Pérez")

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        result = client.get_persona("20301234567")

    assert result.nombre == "Juan"
    assert result.apellido == "Pérez"


def test_get_persona_juridica_no_tiene_nombre_ni_apellido_separado():
    """Una empresa solo tiene razón social — no hay Nombre/Apellido que
    inventar."""
    from arca_fe.padron import PadronClient

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")
    resp = MagicMock()
    resp.persona = _persona_juridica()

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        result = client.get_persona("30-71234567-8")

    assert result.nombre == ""
    assert result.apellido == ""


def test_get_persona_sin_datos_devuelve_none():
    from arca_fe.padron import PadronClient

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")
    resp = MagicMock()
    resp.persona = None

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        assert client.get_persona("20999999999") is None


def test_get_persona_fault_sin_resultados_devuelve_none():
    import zeep.exceptions
    from arca_fe.padron import PadronClient

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.side_effect = zeep.exceptions.Fault(
            "No se encuentran datos referentes al contribuyente consultado"
        )
        mock_client_fn.return_value.service = mock_service

        assert client.get_persona("20999999999") is None


def test_get_persona_fault_desconocido_propaga():
    import zeep.exceptions
    from arca_fe.padron import PadronClient

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.side_effect = zeep.exceptions.Fault("coe.alreadyAuthenticated")
        mock_client_fn.return_value.service = mock_service

        with pytest.raises(zeep.exceptions.Fault):
            client.get_persona("20999999999")
