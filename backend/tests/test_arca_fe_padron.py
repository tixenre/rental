"""Tests de arca_fe.padron.PadronClient.get_persona — el parseo de la
respuesta CRUDA del WSDL real de AFIP (personaServiceA5), sin pasar por el
mock de alto nivel de services.facturacion.padron.

Regresión: el WSDL oficial (getPersonaResponse) trae el dato bajo el campo
`personaReturn` — NO `persona`. El código leía `getattr(resp, "persona",
None)`, un atributo que no existe en la respuesta real; `getattr` con
default silencia el AttributeError y siempre da None, indistinguible de
"AFIP no tiene datos" — bug real de prod: un CUIT con Constancia de
Inscripción vigente, cert y relación delegada correctos, igual devolvía
"sin datos ni motivo" porque el código nunca miraba el campo correcto de la
respuesta (verificado contra el WSDL real: `xs:element name="personaReturn"`
en `getPersonaResponse`, WS_SR_constancia_inscripcion v3.7)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from arca_fe.padron import PadronClient

pytestmark = pytest.mark.unit


def _fake_client(get_persona_return):
    """Devuelve un doble de zeep.Client cuyo .service.getPersona(...) resuelve
    a `get_persona_return` (el objeto que en la vida real trae el WSDL)."""
    service = SimpleNamespace(getPersona=lambda **kwargs: get_persona_return)
    return SimpleNamespace(service=service)


def test_parsea_personaReturn_de_la_respuesta_real_del_wsdl(monkeypatch):
    resp = SimpleNamespace(
        personaReturn=SimpleNamespace(
            datosGenerales=SimpleNamespace(
                razonSocial="Rambla SRL",
                nombre="",
                apellido="",
                estadoClave="ACTIVO",
                domicilioFiscal=None,
            ),
            datosMonotributo=None,
            datosRegimenGeneral=None,
            errorConstancia=None,
            errorMonotributo=None,
            errorRegimenGeneral=None,
        )
    )
    client = PadronClient(endpoint="https://x", cuit_representada=20300000000, token="t", sign="s")
    monkeypatch.setattr(client, "_client", lambda: _fake_client(resp))

    persona = client.get_persona("23373891029")

    assert persona is not None
    assert persona.razon_social == "Rambla SRL"
    assert persona.estado_clave == "ACTIVO"


def test_respuesta_sin_personaReturn_es_silencio_limpio(monkeypatch):
    """`resp` sin el campo `personaReturn` en absoluto (AFIP realmente no
    encontró nada) sigue siendo None — a diferencia del bug, acá no hay
    ningún dato que se esté ignorando por mirar el campo equivocado."""
    resp = SimpleNamespace()
    client = PadronClient(endpoint="https://x", cuit_representada=20300000000, token="t", sign="s")
    monkeypatch.setattr(client, "_client", lambda: _fake_client(resp))

    assert client.get_persona("23373891029") is None
