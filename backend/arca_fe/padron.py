"""arca_fe.padron — cliente del webservice de Padrón (ws_sr_padron_a13) de ARCA. PORTABLE.

Dado un CUIT, devuelve razón social / nombre, domicilio fiscal y condición
frente al IVA — lo mismo que autocompleta el facturador oficial de ARCA al
tipear un CUIT. Reusa el mismo mecanismo de autenticación que WSFE (un TA de
`arca_fe.wsaa`, pero pedido para el servicio "ws_sr_padron_a13" en vez de
"wsfe" — son TAs distintos, no intercambiables).

El WSAA autentica una relación (CUIT del cert ↔ servicio); una vez autenticado,
se puede consultar el padrón de CUALQUIER CUIT — no hace falta que el CUIT
consultado sea el mismo que autentica. Por eso alcanza con el cert de
CUALQUIER emisor ya configurado para resolver el padrón de un CUIT nuevo
(típicamente al dar de alta un emisor o un cliente).

Requiere que el CUIT autenticador tenga la relación "Consulta de padrón"
(ws_sr_padron_a13) delegada en AFIP con clave fiscal — es un paso administrativo
en el portal de AFIP, no algo que el código resuelva.

Nunca crítico: si el padrón no responde o el CUIT no tiene datos, el caller
degrada a "no se pudo autocompletar" (no bloquea nada — es una comodidad de
carga, no un dato exigido por RG4892 como el QR/CAE de la factura).
"""
from __future__ import annotations

import ssl
import urllib3
from dataclasses import dataclass
from typing import Any, Optional

import requests
import zeep
import zeep.helpers
import zeep.transports
from requests.adapters import HTTPAdapter

WSAA_SERVICIO = "ws_sr_padron_a13"

_WSDL_HOMO = "https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA13?wsdl"
_WSDL_PROD = "https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA13?wsdl"

_CLIENT_CACHE: dict[str, zeep.Client] = {}

_TIMEOUT_SECONDS = 20.0

# idImpuesto de IVA en datosRegimenGeneral.impuesto (padrón A13)
_ID_IMPUESTO_IVA = 32


class _AfipSSLAdapter(HTTPAdapter):
    """Mismo ajuste que wsfe.py: los servidores de AFIP usan parámetros DH
    cortos (DH_KEY_TOO_SMALL) que openssl moderno rechaza por default."""

    def init_poolmanager(self, num_pools, maxsize, block=False):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        self.poolmanager = urllib3.PoolManager(
            num_pools=num_pools, maxsize=maxsize, block=block, ssl_context=ctx,
        )


def _afip_transport() -> zeep.transports.Transport:
    session = requests.Session()
    session.mount("https://", _AfipSSLAdapter())
    return zeep.transports.Transport(
        session=session, timeout=_TIMEOUT_SECONDS, operation_timeout=_TIMEOUT_SECONDS
    )


def _get_client(endpoint: str) -> zeep.Client:
    ep = endpoint.rstrip("/")
    if ep not in _CLIENT_CACHE:
        wsdl = _WSDL_HOMO if "homo" in ep else _WSDL_PROD
        _CLIENT_CACHE[ep] = zeep.Client(wsdl, transport=_afip_transport())
    return _CLIENT_CACHE[ep]


@dataclass
class PersonaArca:
    """Datos resueltos del padrón para autocompletar un formulario.

    Cualquier campo puede venir vacío — el padrón no garantiza completitud
    (ej: un monotributista puede no tener domicilio fiscal cargado)."""

    cuit: str
    razon_social: str
    domicilio: str
    condicion_iva: str  # 'responsable_inscripto' | 'monotributo' | 'exento' | ''


@dataclass
class PadronClient:
    endpoint: str
    cuit_representada: int
    token: str
    sign: str

    def _client(self) -> zeep.Client:
        return _get_client(self.endpoint)

    def get_persona(self, cuit_buscado: str) -> Optional[PersonaArca]:
        """Consulta el padrón para `cuit_buscado`. None si AFIP no tiene datos."""
        client = self._client()
        try:
            resp = client.service.getPersona(
                token=self.token,
                sign=self.sign,
                cuitRepresentada=self.cuit_representada,
                idPersona=int(_solo_digitos(cuit_buscado)),
            )
        except zeep.exceptions.Fault as exc:
            if "no se encuentran datos" in str(exc).lower() or "sin resultados" in str(exc).lower():
                return None
            raise

        if resp is None or getattr(resp, "persona", None) is None:
            return None

        return _parsear_persona(cuit_buscado, resp.persona)


def _solo_digitos(s: str) -> str:
    return "".join(c for c in str(s) if c.isdigit())


def _parsear_persona(cuit: str, persona: Any) -> PersonaArca:
    dg = getattr(persona, "datosGenerales", None)

    razon_social = ""
    domicilio = ""
    if dg is not None:
        razon_social = str(getattr(dg, "razonSocial", "") or "")
        if not razon_social:
            nombre = getattr(dg, "nombre", "") or ""
            apellido = getattr(dg, "apellido", "") or ""
            razon_social = f"{nombre} {apellido}".strip()

        dom = getattr(dg, "domicilioFiscal", None)
        if dom is not None:
            partes = [
                getattr(dom, "direccion", "") or "",
                getattr(dom, "localidad", "") or "",
                getattr(dom, "descripcionProvincia", "") or "",
            ]
            domicilio = ", ".join(p for p in partes if p)

    condicion_iva = ""
    if getattr(persona, "datosMonotributo", None) is not None:
        condicion_iva = "monotributo"
    else:
        dr = getattr(persona, "datosRegimenGeneral", None)
        impuestos = getattr(dr, "impuesto", None) if dr is not None else None
        if impuestos:
            ids = {getattr(i, "idImpuesto", None) for i in impuestos}
            if _ID_IMPUESTO_IVA in ids:
                condicion_iva = "responsable_inscripto"
        exento = getattr(persona, "datosExentos", None) if hasattr(persona, "datosExentos") else None
        if exento is not None:
            condicion_iva = "exento"

    return PersonaArca(
        cuit=cuit,
        razon_social=razon_social,
        domicilio=domicilio,
        condicion_iva=condicion_iva,
    )
