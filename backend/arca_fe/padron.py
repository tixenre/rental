"""arca_fe.padron — cliente del webservice de Padrón — Constancia de
Inscripción (WSDL personaServiceA5) de ARCA. PORTABLE.

Dado un CUIT, devuelve razón social / nombre, domicilio fiscal y condición
frente al IVA — lo mismo que autocompleta el facturador oficial de ARCA al
tipear un CUIT. Reusa el mismo mecanismo de autenticación que WSFE (un TA de
`arca_fe.wsaa`, pero pedido para el servicio "ws_sr_constancia_inscripcion" en
vez de "wsfe" — son TAs distintos, no intercambiables).

**El id del servicio para pedir el TA a WSAA NO es "ws_sr_padron_a5"** (verificado
contra el manual oficial de ARCA, "WS_SR_constancia_inscripcion" v3.7): ese id
está DEPRECADO — AFIP renombró el servicio a "ws_sr_constancia_inscripcion". El
WSDL (`personaServiceA5`) es el mismo de siempre; lo único que cambió es el
nombre que hay que usar al solicitar el Ticket de Acceso — pedirlo con el id
viejo hace que WSAA no emita un TA válido para este servicio, y la consulta
degrada silenciosamente a "no se pudo autocompletar" (bug real de prod: un
CUIT real, registrado y habilitado, aparecía como "ARCA no tiene datos").

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

Requiere que el CUIT autenticador tenga la relación **"Consulta Constancia de
Inscripción"** delegada en AFIP con clave fiscal (Administrador de Relaciones
de Clave Fiscal → Adherir servicio → buscar "Constancia de Inscripción", NO
"Padrón" — ese nombre viejo ya no aparece en el buscador de AFIP) — es un paso
administrativo en el portal de AFIP, no algo que el código resuelva.

Nunca crítico: si el padrón no responde o el CUIT no tiene datos, el caller
degrada a "no se pudo autocompletar" (no bloquea nada — es una comodidad de
carga, no un dato exigido por RG4892 como el QR/CAE de la factura).

Igual que `arca_fe.wsfe`: este módulo NO guarda su propia copia de las URLs
de homologación/producción — el caller (`services/facturacion/padron.py`)
las resuelve según ambiente y pasa la URL completa del WSDL ya armada.

Operaciones: `get_persona` es una QUERY (consulta de solo lectura — no tiene
efecto en AFIP). Errores tipados vía `arca_fe.errores` (Fault → ArcaResponseError,
bloqueo de negocio → ArcaBusinessError).
"""

from __future__ import annotations

import logging
import ssl
import urllib3
from dataclasses import dataclass
from typing import Any

import requests
import zeep
import zeep.helpers
import zeep.transports
from requests.adapters import HTTPAdapter

from .errores import ArcaBusinessError, ArcaResponseError

WSAA_SERVICIO = "ws_sr_constancia_inscripcion"

_CLIENT_CACHE: dict[str, zeep.Client] = {}

_TIMEOUT_SECONDS = 20.0

_log = logging.getLogger(__name__)

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
            num_pools=num_pools,
            maxsize=maxsize,
            block=block,
            ssl_context=ctx,
        )


def _afip_transport() -> zeep.transports.Transport:
    session = requests.Session()
    session.mount("https://", _AfipSSLAdapter())
    return zeep.transports.Transport(
        session=session, timeout=_TIMEOUT_SECONDS, operation_timeout=_TIMEOUT_SECONDS
    )


def _get_client(endpoint: str) -> zeep.Client:
    """`endpoint` es la URL COMPLETA del WSDL, ya resuelta por el caller
    según ambiente (ver docstring del módulo)."""
    ep = endpoint.rstrip("/")
    if ep not in _CLIENT_CACHE:
        _CLIENT_CACHE[ep] = zeep.Client(ep, transport=_afip_transport())
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

    def get_persona(self, cuit_buscado: str) -> PersonaArca:
        """Consulta el padrón para `cuit_buscado`. Devuelve la `PersonaArca` si
        AFIP la encontró.

        **NUNCA devuelve None en silencio** — ese silencio era la raíz del
        "ARCA no devolvió datos ni motivo" indistinguible entre un CUIT que no
        existe, un bloqueo de negocio, una relación no delegada o un ambiente
        equivocado. Ahora todo lo que no sea "persona encontrada" levanta la
        taxonomía tipada de `errores`:
        - `ArcaBusinessError`: AFIP contestó pero rechazó/no encontró por una
          regla propia — `personaReturn` sin `datosGenerales` pero con
          `errorConstancia`/`errorRegimenGeneral`/`errorMonotributo` poblado
          (ej. "No existe persona con ese id", o el bloqueo RG 3990-E por falta
          de adhesión al Domicilio Fiscal Electrónico; manual oficial
          "WS_SR_constancia_inscripcion" v3.7 §5.3). Mensajes en `.errores`.
        - `ArcaResponseError`: AFIP contestó en una forma que no podemos
          interpretar como persona NI como motivo reconocible (sin
          `personaReturn`, o `datosGenerales` None sin ningún nodo de error) —
          lleva la respuesta cruda en `.raw` para diagnosticar, en vez de un
          None mudo. También ante un Fault SOAP (texto de AFIP en `.raw`).
        """
        client = self._client()
        try:
            resp = client.service.getPersona(
                token=self.token,
                sign=self.sign,
                cuitRepresentada=self.cuit_representada,
                idPersona=int(_solo_digitos(cuit_buscado)),
            )
        except zeep.exceptions.Fault as exc:
            raise ArcaResponseError(str(exc), raw=str(exc)) from exc

        persona = getattr(resp, "personaReturn", None) if resp is not None else None
        if persona is None:
            crudo = _serializar(resp)
            _log.warning(
                "getPersona sin 'personaReturn' para %s — respuesta cruda: %s",
                cuit_buscado,
                crudo,
            )
            raise ArcaResponseError(
                "AFIP no devolvió 'personaReturn' para este CUIT (respuesta "
                "vacía o inesperada, sin un motivo reconocible).",
                raw=crudo,
            )

        if getattr(persona, "datosGenerales", None) is None:
            mensajes = _errores_constancia(persona)
            if mensajes:
                raise ArcaBusinessError(
                    "; ".join(mensajes),
                    errores=tuple((None, m) for m in mensajes),
                )
            crudo = _serializar(persona)
            _log.warning(
                "getPersona sin 'datosGenerales' ni motivo reconocible para %s "
                "— respuesta cruda: %s",
                cuit_buscado,
                crudo,
            )
            raise ArcaResponseError(
                "AFIP devolvió una respuesta sin 'datosGenerales' y sin un "
                "motivo reconocible (ningún nodo de error poblado).",
                raw=crudo,
            )

        return _parsear_persona(cuit_buscado, persona)


def _solo_digitos(s: str) -> str:
    return "".join(c for c in str(s) if c.isdigit())


def _serializar(obj: Any) -> str:
    """Serializa una respuesta de zeep a texto para diagnóstico (`.raw` de la
    excepción la trunca a 2000). Best-effort: si zeep no puede serializar el
    objeto, cae a `repr`."""
    if obj is None:
        return "None"
    try:
        return str(zeep.helpers.serialize_object(obj, dict))
    except Exception:
        return repr(obj)


def _errores_constancia(persona: Any) -> list[str]:
    """Junta el/los mensaje(s) que AFIP puso en `errorConstancia`/
    `errorRegimenGeneral`/`errorMonotributo` (manual §5.3) cuando bloqueó o no
    encontró la constancia. AFIP NO es consistente en la forma: puede venir un
    objeto con `.error`, un string suelto, o —lo más común— un array/lista
    (`ArrayOfString`). Antes solo se leía `.error` de un objeto único y un array
    se perdía → "sin motivo" espurio. Ahora se aplanan todas las formas (mismo
    criterio que pyafipws)."""
    mensajes: list[str] = []
    for campo in ("errorConstancia", "errorRegimenGeneral", "errorMonotributo"):
        mensajes.extend(_extraer_mensajes(getattr(persona, campo, None)))
    return mensajes


def _extraer_mensajes(nodo: Any) -> list[str]:
    """Aplana un nodo de error de AFIP a una lista de strings, sea cual sea su
    forma: None → []; string → [texto]; lista/tupla → recursivo sobre cada
    ítem; objeto con `.error` → recursivo sobre `.error`; cualquier otro objeto
    con contenido → su `str()`."""
    if nodo is None:
        return []
    if isinstance(nodo, str):
        texto = nodo.strip()
        return [texto] if texto else []
    if isinstance(nodo, (list, tuple)):
        out: list[str] = []
        for item in nodo:
            out.extend(_extraer_mensajes(item))
        return out
    err_attr = getattr(nodo, "error", None)
    if err_attr is not None:
        return _extraer_mensajes(err_attr)
    texto = str(nodo).strip()
    return [texto] if texto and texto != "None" else []


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
        ids = (
            {getattr(i, "idImpuesto", None) for i in impuestos} if impuestos else set()
        )
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
