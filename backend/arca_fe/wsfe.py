"""arca_fe.wsfe — cliente WSFEv1 (Facturación Electrónica) de ARCA. PORTABLE.

Construye el cliente zeep on-demand a partir del endpoint. No cachea; no persiste.
El caller (services/facturacion/) maneja la sesión y la BD — INCLUIDA la URL del
WSDL: este módulo no guarda su propia copia de las URLs de homologación/producción
(vivían duplicadas acá y en services/facturacion/config.py, con un match de string
frágil para elegir una u otra) — recibe la URL ya resuelta y la usa tal cual.

Operaciones: `solicitar_cae` es el único COMMAND (emite un CAE — efecto legal
en AFIP); `ultimo_autorizado`, `consultar` y los `param_*` son QUERIES (lecturas
sin efecto). Los errores salen tipados vía `arca_fe.errores` (ningún método
filtra un `zeep.Fault` crudo).

`param_*` cubre todos los catálogos vivos de WSFEv1 que un consumidor puede
necesitar para armar un `ComprobanteRequest` sin hardcodear ids a mano:
puntos de venta, tipos de comprobante/documento/concepto, condición IVA del
receptor, tributos, datos opcionales (incluidos los de FCE MiPyme), monedas,
y la cotización oficial del día (`param_cotizacion`) — todos verificados
contra el WSDL real y el manual oficial de WSFEv1.

Deps: zeep (SOAP), ya en requirements.txt.
"""

from __future__ import annotations

import logging
import re
import threading
import urllib3
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .modelos import CaeResult, ComprobanteRequest

import requests
import zeep
import zeep.helpers
import zeep.transports
from requests.adapters import HTTPAdapter

from ._ssl_afip import afip_ssl_context
from .errores import ArcaBusinessError, ArcaResponseError

_logger = logging.getLogger(__name__)

# Caché local de clientes SOAP (por (endpoint, timeout), dentro del proceso) — protegida por
# `_cache_lock` (check-then-set no atómico en Python puro: dos threads pidiendo el mismo cliente
# por primera vez podían construirlo dos veces; con el lock, uno construye y el otro reusa).
_CLIENT_CACHE: dict[tuple[str, float], zeep.Client] = {}
_cache_lock = threading.Lock()

# Códigos de error de FECompConsultar que significan "no existe" (no un error
# real): 10016 = hueco en una secuencia con historial; 602 = combinación
# (pto_vta, cbte_tipo) sin NINGÚN historial todavía (ver comentario en `consultar`).
_CODES_NO_EXISTE = (10016, 602)


class _AfipSSLAdapter(HTTPAdapter):
    """Ver `_ssl_afip.afip_ssl_context` — mismo ajuste que `padron.py` (y,
    para el cliente httpx de `wsaa.py`, `afip_ssl_context()` directo)."""

    def init_poolmanager(self, num_pools, maxsize, block=False):
        self.poolmanager = urllib3.PoolManager(
            num_pools=num_pools,
            maxsize=maxsize,
            block=block,
            ssl_context=afip_ssl_context(),
        )


_TIMEOUT_SECONDS = 30.0  # default de `WsfeClient.timeout` — configurable por instancia


def _afip_transport(timeout: float) -> zeep.transports.Transport:
    session = requests.Session()
    session.mount("https://", _AfipSSLAdapter())
    # operation_timeout: sin esto zeep no aplica límite a las llamadas SOAP —
    # si AFIP se cuelga, la llamada espera indefinidamente sosteniendo el
    # advisory lock + el FOR UPDATE de afip_ta (bloquea TODA la facturación
    # de ese emisor). `timeout` cubre el fetch inicial del WSDL.
    return zeep.transports.Transport(
        session=session, timeout=timeout, operation_timeout=timeout
    )


def _get_client(endpoint: str, timeout: float) -> zeep.Client:
    """Devuelve el cliente zeep (cacheado en memoria por proceso, por `(endpoint, timeout)`).
    `endpoint` es la URL COMPLETA del WSDL, ya resuelta por el caller según ambiente."""
    ep = endpoint.rstrip("/")
    clave = (ep, timeout)
    with _cache_lock:
        if clave not in _CLIENT_CACHE:
            _CLIENT_CACHE[clave] = zeep.Client(ep, transport=_afip_transport(timeout))
        return _CLIENT_CACHE[clave]


def clear_cache() -> None:
    """Limpia el cache de clientes SOAP — para tests, o para un consumidor multi-tenant que
    necesite forzar un cliente nuevo (ej. tras rotar un certificado)."""
    with _cache_lock:
        _CLIENT_CACHE.clear()


@dataclass
class WsfeClient:
    """Cliente de alto nivel para WSFEv1.

    `endpoint`: base URL del servicio (ej: "wswhomo.afip.gov.ar").
    `cuit`: CUIT del emisor (sin guiones).
    `token`, `sign`: del TA vigente.
    `timeout`: segundos para el fetch del WSDL y cada operación SOAP (default 30.0) —
    configurable por instancia; dos instancias con distinto `timeout` al mismo `endpoint`
    cachean clientes zeep separados (no colisionan)."""

    endpoint: str
    cuit: int
    token: str
    sign: str
    timeout: float = _TIMEOUT_SECONDS

    def _auth(self) -> dict:
        return {"Token": self.token, "Sign": self.sign, "Cuit": str(self.cuit)}

    def _client(self) -> zeep.Client:
        return _get_client(self.endpoint, self.timeout)

    @staticmethod
    def _soap(op: str, fn, /, *args, **kwargs):
        """Ejecuta una operación SOAP y traduce un `zeep.exceptions.Fault` a
        `ArcaResponseError` — para no filtrar la dependencia `zeep` al
        consumidor de la librería (que debería poder atrapar solo `ArcaError`).
        El texto del Fault viaja en `.raw`."""
        try:
            return fn(*args, **kwargs)
        except zeep.exceptions.Fault as exc:
            raise ArcaResponseError(
                f"{op}: SOAP Fault de AFIP — {exc}", raw=str(exc)
            ) from exc

    # ------------------------------------------------------------------
    # QUERIES (lecturas — sin efecto en AFIP)
    # ------------------------------------------------------------------

    # FECompUltimoAutorizado — último comprobante autorizado

    def ultimo_autorizado(self, pto_vta: int, cbte_tipo: int) -> int:
        """Devuelve el último número de comprobante autorizado para (pto_vta, cbte_tipo).

        Si nunca se emitió ninguno, ARCA devuelve 0.
        """
        client = self._client()
        resp = self._soap(
            "FECompUltimoAutorizado",
            client.service.FECompUltimoAutorizado,
            Auth=self._auth(),
            PtoVta=pto_vta,
            CbteTipo=cbte_tipo,
        )
        _check_errors(resp, "FECompUltimoAutorizado")
        return int(resp.CbteNro)

    # FECompConsultar — consultar un comprobante ya autorizado

    def consultar(
        self, pto_vta: int, cbte_tipo: int, numero: int
    ) -> Optional[dict[str, Any]]:
        """Consulta el comprobante (pto_vta, cbte_tipo, numero).

        Devuelve un dict con los campos del comprobante, o None si no existe.
        """
        client = self._client()
        try:
            resp = client.service.FECompConsultar(
                Auth=self._auth(),
                FeCompConsReq={
                    "CbteTipo": cbte_tipo,
                    "CbteNro": numero,
                    "PtoVta": pto_vta,
                },
            )
        except zeep.exceptions.Fault as exc:
            texto = str(exc)
            # Word-boundary, no substring crudo: un código real (602/10016) no
            # tiene que poder matchear como parte de un número más largo no
            # relacionado en el texto de AFIP — silenciaría un error real.
            if (
                any(re.search(rf"\b{c}\b", texto) for c in _CODES_NO_EXISTE)
                or "no existe" in texto.lower()
            ):
                return None
            raise ArcaResponseError(
                f"FECompConsultar: SOAP Fault de AFIP — {exc}", raw=texto
            ) from exc

        if resp is None:
            return None

        # Chequear si hay error de "no existe". AFIP no es consistente: 10016 es
        # el "no existe" de un hueco en una secuencia con historial; 602 ("No
        # existen datos en nuestros registros para los parámetros ingresados")
        # es lo que devuelve para una combinación (pto_vta, cbte_tipo) VIRGEN —
        # p.ej. la primera Nota de Crédito que se emite para un punto de venta
        # (bug encontrado en prod: bloqueaba la primera NC con un 503 espurio).
        if hasattr(resp, "Errors") and resp.Errors:
            for e in resp.Errors.Err:
                if e.Code in _CODES_NO_EXISTE:
                    return None
            _raise_errors(resp.Errors.Err, "FECompConsultar")

        return zeep.helpers.serialize_object(resp.ResultGet, dict)

    # ------------------------------------------------------------------
    # COMMANDS (efecto en AFIP — emite un comprobante legal)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_det_resp(result_obj: Any) -> "CaeResult":
        """Parsea UN elemento de `FeDetResp.FECAEDetResponse` a un `CaeResult` — sin errores de
        cabecera (esos los agrega el caller si corresponde; ver `solicitar_cae` vs.
        `solicitar_cae_lote`, que los atribuyen distinto)."""
        from .modelos import CaeResult  # import local para evitar circulares

        resultado = result_obj.Resultado  # 'A' | 'R' | 'P'

        cae: Optional[str] = None
        cae_vto: Optional[date] = None
        numero: Optional[int] = None
        observaciones: list[str] = []
        errores: list[str] = []

        if resultado == "A":
            cae = result_obj.CAE
            cae_vto = _parse_fecha(result_obj.CAEFchVto)
            numero = int(result_obj.CbteDesde)

        if hasattr(result_obj, "Observaciones") and result_obj.Observaciones:
            for obs in result_obj.Observaciones.Obs:
                observaciones.append(f"{obs.Code}: {obs.Msg}")

        if hasattr(result_obj, "Errors") and result_obj.Errors:
            for err in result_obj.Errors.Err:
                errores.append(f"{err.Code}: {err.Msg}")

        return CaeResult(
            resultado=resultado,
            cae=cae,
            cae_vto=cae_vto,
            numero=numero,
            observaciones=tuple(observaciones),
            errores=tuple(errores),
        )

    # FECAESolicitar — solicitar CAE

    def solicitar_cae(self, comprobante: "ComprobanteRequest", numero: int) -> CaeResult:
        """Arma el payload (`comprobante.armar_fecae`) y envía FECAESolicitar — UNA sola forma
        tipada, ya no acepta el `dict` crudo (el armado del payload dejó de ser responsabilidad
        del caller). Parsea la respuesta en un CaeResult.

        NUNCA asume éxito: valida Resultado == 'A' y extrae errores si 'R'.
        """
        from .comprobante import armar_fecae

        fecae = armar_fecae(comprobante, numero)
        client = self._client()
        resp = self._soap(
            "FECAESolicitar",
            client.service.FECAESolicitar,
            Auth=self._auth(),
            FeCAEReq=fecae,
        )

        # Chequear el detalle ANTES de indexarlo: si AFIP rechazó el pedido
        # completo (ej. Auth inválido), FeDetResp puede venir ausente —
        # `resp.FeDetResp.FECAEDetResponse[0]` a ciegas explotaría con un
        # AttributeError/IndexError críptico en vez de mostrar el motivo real.
        det_resp = getattr(resp, "FeDetResp", None)
        detalles = (
            getattr(det_resp, "FECAEDetResponse", None) if det_resp is not None else None
        )
        if not detalles:
            # Sin detalle: surfaceamos el motivo. Si hay Errors de cabecera,
            # `_check_errors` levanta ArcaBusinessError con los códigos; si no
            # hay ni detalle ni Errors, es una respuesta que no entendemos.
            _check_errors(resp, "FECAESolicitar")
            raise ArcaResponseError(
                "FECAESolicitar: AFIP no devolvió FeDetResp/FECAEDetResponse ni "
                "Errors — respuesta inesperada, no se puede determinar el resultado.",
                raw=str(resp),
            )

        resultado = self._parse_det_resp(detalles[0])

        # Errores a nivel cabecera (solo acá — para un comprobante SUELTO, el
        # header cubre exactamente este único ítem; en `solicitar_cae_lote`
        # el header cubre TODO el lote, así que ahí no se atribuyen a cada
        # ítem individual — ver ese método).
        errores_cabecera: list[str] = []
        if hasattr(resp, "Errors") and resp.Errors:
            for err in resp.Errors.Err:
                errores_cabecera.append(f"{err.Code}: {err.Msg}")
        if errores_cabecera:
            from dataclasses import replace

            resultado = replace(resultado, errores=resultado.errores + tuple(errores_cabecera))

        return resultado

    # FECAESolicitar — solicitar CAE de un LOTE de comprobantes consecutivos

    def solicitar_cae_lote(
        self, comprobantes: "list[ComprobanteRequest]", numero_desde: int
    ) -> "list[CaeResult]":
        """Pide CAE para VARIOS comprobantes CONSECUTIVOS (mismo emisor/pto_vta/cbte_tipo) en UNA
        sola llamada SOAP (`comprobante.armar_fecae_lote` arma el payload, valida homogeneidad y
        el tope de 250 por lote — ver su docstring).

        Devuelve la lista de `CaeResult` EN EL MISMO ORDEN que `comprobantes` — AFIP puede aprobar
        unos y rechazar otros dentro del mismo lote (`FeCabResp.Resultado` puede venir 'P' =
        parcial); cada `CaeResult` refleja el resultado INDIVIDUAL de su ítem, para que el
        consumidor decida item por item qué hacer. A diferencia de `solicitar_cae`, los errores de
        CABECERA no se atribuyen a cada ítem (el header cubre TODO el lote, no un ítem puntual —
        atribuirlo a cada uno sería un dato engañoso en un lote con aprobación parcial)."""
        from .comprobante import armar_fecae_lote

        fecae = armar_fecae_lote(comprobantes, numero_desde)
        client = self._client()
        resp = self._soap(
            "FECAESolicitar",
            client.service.FECAESolicitar,
            Auth=self._auth(),
            FeCAEReq=fecae,
        )

        det_resp = getattr(resp, "FeDetResp", None)
        detalles = (
            getattr(det_resp, "FECAEDetResponse", None) if det_resp is not None else None
        )
        if not detalles:
            _check_errors(resp, "FECAESolicitar")
            raise ArcaResponseError(
                "FECAESolicitar (lote): AFIP no devolvió FeDetResp/FECAEDetResponse ni "
                "Errors — respuesta inesperada, no se puede determinar el resultado.",
                raw=str(resp),
            )

        return [self._parse_det_resp(d) for d in detalles]

    # ------------------------------------------------------------------
    # QUERIES (FEParamGet* — catálogos/validaciones, sin efecto en AFIP)
    # ------------------------------------------------------------------

    def param_puntos_venta(self) -> list[dict]:
        """Devuelve los puntos de venta habilitados para el CUIT."""
        client = self._client()
        resp = self._soap(
            "FEParamGetPtosVenta", client.service.FEParamGetPtosVenta, Auth=self._auth()
        )
        _check_errors(resp, "FEParamGetPtosVenta")
        if resp.ResultGet is None:
            return []
        return zeep.helpers.serialize_object(resp.ResultGet.PtoVenta, dict) or []

    def param_tipos_cbte(self) -> list[dict]:
        """Devuelve los tipos de comprobante disponibles."""
        client = self._client()
        resp = self._soap(
            "FEParamGetTiposCbte", client.service.FEParamGetTiposCbte, Auth=self._auth()
        )
        _check_errors(resp, "FEParamGetTiposCbte")
        if resp.ResultGet is None:
            return []
        return zeep.helpers.serialize_object(resp.ResultGet.CbteTipo, dict) or []

    def param_tipos_doc(self) -> list[dict]:
        """Tipos de documento del receptor (CUIT/CUIL/DNI/...) vigentes en ARCA."""
        client = self._client()
        resp = self._soap(
            "FEParamGetTiposDoc", client.service.FEParamGetTiposDoc, Auth=self._auth()
        )
        _check_errors(resp, "FEParamGetTiposDoc")
        if resp.ResultGet is None:
            return []
        return zeep.helpers.serialize_object(resp.ResultGet.DocTipo, dict) or []

    def param_tipos_concepto(self) -> list[dict]:
        """Tipos de concepto (Productos/Servicios/Ambos) vigentes en ARCA."""
        client = self._client()
        resp = self._soap(
            "FEParamGetTiposConcepto",
            client.service.FEParamGetTiposConcepto,
            Auth=self._auth(),
        )
        _check_errors(resp, "FEParamGetTiposConcepto")
        if resp.ResultGet is None:
            return []
        return zeep.helpers.serialize_object(resp.ResultGet.ConceptoTipo, dict) or []

    def param_condicion_iva_receptor(self, clase_cmp: str) -> list[dict]:
        """Condiciones de IVA del receptor válidas para una clase de
        comprobante ("A", "B", "C", "M"). AFIP no tiene un valor "todas" —
        hay que pedirlas por clase (verificado contra pyafipws)."""
        client = self._client()
        resp = self._soap(
            "FEParamGetCondicionIvaReceptor",
            client.service.FEParamGetCondicionIvaReceptor,
            Auth=self._auth(),
            ClaseCmp=clase_cmp,
        )
        _check_errors(resp, "FEParamGetCondicionIvaReceptor")
        if resp.ResultGet is None:
            return []
        return (
            zeep.helpers.serialize_object(resp.ResultGet.CondicionIvaReceptor, dict)
            or []
        )

    def param_tipos_tributos(self) -> list[dict]:
        """Ids/descripciones de tributos válidos para `Tributo.id` (Impuestos
        Internos, percepciones de IIBB, etc.) — fuente única para no
        hardcodear un id a mano en el consumidor."""
        client = self._client()
        resp = self._soap(
            "FEParamGetTiposTributos", client.service.FEParamGetTiposTributos, Auth=self._auth()
        )
        _check_errors(resp, "FEParamGetTiposTributos")
        if resp.ResultGet is None:
            return []
        return zeep.helpers.serialize_object(resp.ResultGet.TributoTipo, dict) or []

    def param_tipos_opcional(self) -> list[dict]:
        """Ids/descripciones de datos opcionales válidos para `Opcional.id`
        (ej. los de la Factura de Crédito Electrónica MiPyme: CBU, alias)."""
        client = self._client()
        resp = self._soap(
            "FEParamGetTiposOpcional", client.service.FEParamGetTiposOpcional, Auth=self._auth()
        )
        _check_errors(resp, "FEParamGetTiposOpcional")
        if resp.ResultGet is None:
            return []
        return zeep.helpers.serialize_object(resp.ResultGet.OpcionalTipo, dict) or []

    def param_tipos_monedas(self) -> list[dict]:
        """Códigos de moneda válidos para `ComprobanteRequest.moneda`/`MonId`."""
        client = self._client()
        resp = self._soap(
            "FEParamGetTiposMonedas", client.service.FEParamGetTiposMonedas, Auth=self._auth()
        )
        _check_errors(resp, "FEParamGetTiposMonedas")
        if resp.ResultGet is None:
            return []
        return zeep.helpers.serialize_object(resp.ResultGet.Moneda, dict) or []

    def param_cotizacion(self, mon_id: str, fecha: Optional[date] = None) -> dict:
        """Cotización oficial de ARCA para `mon_id` (`ComprobanteRequest.cotizacion`).
        `fecha=None` → la más reciente. El motor NO la aplica solo — que un
        comprobante use la cotización del día es decisión/timing del
        consumidor (mismo criterio que el precio: el core no decide, ejecuta
        con lo que le pasan)."""
        client = self._client()
        kwargs = {"Auth": self._auth(), "MonId": mon_id}
        if fecha is not None:
            kwargs["FchCotiz"] = fecha.strftime("%Y%m%d")
        resp = self._soap(
            "FEParamGetCotizacion", client.service.FEParamGetCotizacion, **kwargs
        )
        _check_errors(resp, "FEParamGetCotizacion")
        cot = resp.ResultGet
        return {
            "mon_id": getattr(cot, "MonId", mon_id),
            "cotizacion": getattr(cot, "MonCotiz", None),
            "fecha": getattr(cot, "FchCotiz", None),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_fecha(s: Any) -> Optional[date]:
    if s is None:
        return None
    raw = str(s).strip()
    if not raw:
        return None  # ausente/vacío es legítimo (no una fecha malformada)
    try:
        if len(raw) == 8 and raw.isdigit():
            return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
        return date.fromisoformat(raw[:10])
    except ValueError:
        # No se pierde en silencio: una fecha de AFIP (ej. CAEFchVto) con
        # formato inesperado es señal de que algo cambió del otro lado.
        _logger.warning("WSFE: fecha con formato inesperado (%r) — se ignora.", s)
        return None


def _check_errors(resp: Any, op: str) -> None:
    if hasattr(resp, "Errors") and resp.Errors:
        _raise_errors(resp.Errors.Err, op)


def _raise_errors(errs: Any, op: str) -> None:
    """Levanta `ArcaBusinessError` con los pares (código, mensaje) que AFIP
    puso en `Errors.Err` — datos estructurados (`.errores`, `.codigo`) para que
    el consumidor no tenga que re-parsear el string del mensaje."""
    pares: tuple[tuple[Optional[int], str], ...] = tuple(
        (_int_o_none(e.Code), str(e.Msg)) for e in errs
    )
    msgs = "; ".join(f"{cod}: {msg}" for cod, msg in pares)
    raise ArcaBusinessError(f"{op} error — {msgs}", errores=pares)


def _int_o_none(v: Any) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
