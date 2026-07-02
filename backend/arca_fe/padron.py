"""arca_fe.padron — cliente del webservice de Padrón — Constancia de
Inscripción (ws_sr_padron_a5) de ARCA. PORTABLE.

Dado un CUIT, devuelve razón social / nombre, domicilio fiscal y condición
frente al IVA — lo mismo que autocompleta el facturador oficial de ARCA al
tipear un CUIT. Reusa el mismo mecanismo de autenticación que WSFE (un TA de
`arca_fe.wsaa`, pero pedido para el servicio "ws_sr_padron_a5" en vez de
"wsfe" — son TAs distintos, no intercambiables).

**Por qué A5 y no A13** (verificado contra el WSDL real de AFIP, homologación
y producción — ambos idénticos): A13 (`personaServiceA13`) devuelve un
`persona` PLANO, sin `datosGenerales`/`datosMonotributo`/`datosRegimenGeneral`
— consultarlo y parsearlo como si tuviera esos campos anidados (lo que hacía
este módulo antes) devuelve TODO vacío en producción real, aunque AFIP
encuentre el CUIT. **A5** (`personaServiceA5`, "Constancia de Inscripción")
sí tiene esa forma anidada — es el servicio correcto para razón social /
domicilio / condición IVA.

El WSAA autentica una relación (CUIT del cert ↔ servicio); una vez autenticado,
se puede consultar el padrón de CUALQUIER CUIT — no hace falta que el CUIT
consultado sea el mismo que autentica. Por eso alcanza con el cert de
CUALQUIER emisor ya configurado para resolver el padrón de un CUIT nuevo
(típicamente al dar de alta un emisor o un cliente).

Requiere que el CUIT autenticador tenga la relación "Consulta de padrón"
(ws_sr_padron_a5) delegada en AFIP con clave fiscal — es un paso administrativo
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

WSAA_SERVICIO = "ws_sr_padron_a5"

_WSDL_HOMO = "https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl"
_WSDL_PROD = "https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl"

_CLIENT_CACHE: dict[str, zeep.Client] = {}

_TIMEOUT_SECONDS = 20.0

# idImpuesto en datosRegimenGeneral.impuesto (padrón A5) — verificado contra
# pyafipws (referencia de facto del ecosistema): 30 = IVA Responsable
# Inscripto, 32 = IVA Exento. Ojo: el código viejo tenía esto AL REVÉS
# (trataba 32 como "responsable_inscripto"), lo que hubiera detectado un
# cliente EXENTO como RI — corregido acá.
_ID_IMPUESTO_RI = 30
_ID_IMPUESTO_EXENTO = 32


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
    (ej: un monotributista puede no tener domicilio fiscal cargado).

    `nombre`/`apellido` solo vienen poblados para una PERSONA FÍSICA sin
    razón social propia registrada (AFIP los da separados) — un formulario
    con campos Nombre/Apellido separados (cliente) los usa así; uno con un
    solo campo "razón social" (emisor, siempre una identidad de negocio)
    usa `razon_social`, que ya viene combinado como fallback."""

    cuit: str
    razon_social: str
    nombre: str
    apellido: str
    domicilio: str
    condicion_iva: str  # 'responsable_inscripto' | 'monotributo' | 'exento' | ''
    estado_clave: str  # 'ACTIVO' | 'INACTIVO' | '' — señal de calidad de dato,
    # no bloqueante: un CUIT dado de baja en AFIP es motivo de aviso al
    # usuario, no un error del autocompletado en sí.


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
    nombre = ""
    apellido = ""
    domicilio = ""
    estado_clave = ""
    if dg is not None:
        razon_social = str(getattr(dg, "razonSocial", "") or "")
        if not razon_social:
            nombre = getattr(dg, "nombre", "") or ""
            apellido = getattr(dg, "apellido", "") or ""
            razon_social = f"{nombre} {apellido}".strip()

        estado_clave = str(getattr(dg, "estadoClave", "") or "")

        dom = getattr(dg, "domicilioFiscal", None)
        if dom is not None:
            partes = [
                getattr(dom, "direccion", "") or "",
                getattr(dom, "localidad", "") or "",
                getattr(dom, "descripcionProvincia", "") or "",
            ]
            domicilio = ", ".join(p for p in partes if p)

    # Orden de chequeo — mismo criterio que pyafipws (referencia de facto):
    # exento se chequea ANTES que RI (un mismo padrón podría traer ambos
    # ids en teoría; exento es la condición más específica).
    condicion_iva = ""
    if getattr(persona, "datosMonotributo", None) is not None:
        condicion_iva = "monotributo"
    else:
        dr = getattr(persona, "datosRegimenGeneral", None)
        impuestos = getattr(dr, "impuesto", None) if dr is not None else None
        ids = {getattr(i, "idImpuesto", None) for i in impuestos} if impuestos else set()
        if _ID_IMPUESTO_EXENTO in ids:
            condicion_iva = "exento"
        elif _ID_IMPUESTO_RI in ids:
            condicion_iva = "responsable_inscripto"

    return PersonaArca(
        cuit=cuit,
        razon_social=razon_social,
        nombre=nombre,
        apellido=apellido,
        domicilio=domicilio,
        condicion_iva=condicion_iva,
        estado_clave=estado_clave,
    )
