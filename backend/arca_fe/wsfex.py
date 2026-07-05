"""arca_fe.wsfex — cliente WSFEXv1 (Factura de Exportación) de ARCA. PORTABLE.

Espeja la arquitectura de `wsfe.py` (WSFEv1) byte a byte — mismo criterio de cache de clientes
zeep, mismo manejo de errores tipados, misma separación QUERY/COMMAND — para un webservice de AFIP
DISTINTO (RG 2758, operación `FEXAuthorize`).

**Nombres de operación SOAP no verificados contra el WSDL real** (a diferencia de `wsfe.py`, que sí
está confirmado) — `FEXAuthorize`/`FEXGetLast_CMP`/`FEXGetCMP`/`FEXGetPARAM_*` son la mejor
referencia disponible sin acceso al WSDL de homologación de WSFEXv1. Se confirman/ajustan contra
AFIP real antes de que este módulo se use en producción — mismo criterio que ya aplicó `padron.py`
cuando el nombre de servicio documentado públicamente resultó estar deprecado en la práctica.

`autorizar` es el único COMMAND (emite un CAE de exportación — efecto legal en AFIP);
`ultimo_autorizado`, `consultar` y los `param_*` son QUERIES.

Deps: zeep (SOAP), ya en requirements.txt — mismas que `wsfe.py`."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .modelos import CaeResult
    from .modelos_exportacion import ComprobanteExportacionRequest

import zeep
import zeep.helpers

from .errores import ArcaBusinessError, ArcaResponseError
from .wsfe import _afip_transport, _AfipSSLAdapter, parse_fecha_arca  # noqa: F401 (reexport)

_logger = logging.getLogger(__name__)

# Cache separado del de `wsfe.py` — mismo criterio de `(endpoint, timeout)`, pero WSFEXv1 y WSFEv1
# hablan con endpoints DISTINTOS (WSDLs separados), así que compartir el diccionario no ahorraría
# nada y acoplaría los dos módulos sin necesidad.
_CLIENT_CACHE: dict[tuple[str, float], zeep.Client] = {}
_cache_lock = threading.Lock()

_TIMEOUT_SECONDS = 30.0

# Nombre del servicio WSAA para WSFEXv1 (Administrador de Relaciones de Clave Fiscal) — a
# CONFIRMAR contra el manual oficial de AFIP: no asumir que es literalmente "wsfex" solo porque
# es el nombre "obvio" (mismo motivo que `padron.py::WSAA_SERVICIO` documenta: AFIP a veces usa
# un id de servicio no obvio, `"ws_sr_constancia_inscripcion"` en vez de `"ws_sr_padron_a5"`).
WSFEX_WSAA_SERVICIO = "wsfex"


def _get_client(endpoint: str, timeout: float) -> zeep.Client:
    """Devuelve el cliente zeep (cacheado en memoria por proceso, por `(endpoint, timeout)`).
    `endpoint` es la URL COMPLETA del WSDL de WSFEXv1, ya resuelta por el caller según ambiente."""
    ep = endpoint.rstrip("/")
    clave = (ep, timeout)
    with _cache_lock:
        if clave not in _CLIENT_CACHE:
            _CLIENT_CACHE[clave] = zeep.Client(ep, transport=_afip_transport(timeout))
        return _CLIENT_CACHE[clave]


def clear_cache() -> None:
    """Limpia el cache de clientes SOAP de WSFEXv1 — para tests, o para forzar un cliente nuevo
    tras rotar un certificado. No afecta el cache de `wsfe.py` (son cachés separados)."""
    with _cache_lock:
        _CLIENT_CACHE.clear()


@dataclass
class WsfexClient:
    """Cliente de alto nivel para WSFEXv1.

    `endpoint`: base URL del servicio WSFEXv1 (homologación/producción, DISTINTA de la de WSFEv1).
    `cuit`: CUIT del emisor (sin guiones). `token`/`sign`: del TA vigente para el servicio
    `WSFEX_WSAA_SERVICIO` (NO el mismo TA que WSFEv1 — un TA autentica una relación CUIT↔servicio,
    ver `services/facturacion/wsaa_cache.py::get_ta`). `timeout`: igual criterio que `WsfeClient`."""

    endpoint: str
    cuit: int
    token: str
    sign: str
    timeout: float = _TIMEOUT_SECONDS

    def _auth(self) -> dict:
        return {"Token": self.token, "Sign": self.sign, "Cuit": self.cuit}

    def _client(self) -> zeep.Client:
        return _get_client(self.endpoint, self.timeout)

    @staticmethod
    def _soap(op: str, fn, /, *args, **kwargs):
        """Ejecuta una operación SOAP y traduce un `zeep.exceptions.Fault` a `ArcaResponseError` —
        mismo criterio que `WsfeClient._soap`, no filtra la dependencia `zeep` al consumidor."""
        try:
            return fn(*args, **kwargs)
        except zeep.exceptions.Fault as exc:
            raise ArcaResponseError(
                f"{op}: SOAP Fault de AFIP — {exc}", raw=str(exc)
            ) from exc

    # ------------------------------------------------------------------
    # QUERIES (lecturas — sin efecto en AFIP)
    # ------------------------------------------------------------------

    def ultimo_autorizado(self, pto_vta: int, cbte_tipo: int) -> int:
        """Último número de comprobante de exportación autorizado para (pto_vta, cbte_tipo).
        Si nunca se emitió ninguno, ARCA devuelve 0 (mismo contrato que `WsfeClient.ultimo_autorizado`).

        Operación tentativa `FEXGetLast_CMP` — a confirmar contra el WSDL real."""
        client = self._client()
        resp = self._soap(
            "FEXGetLast_CMP",
            client.service.FEXGetLast_CMP,
            Auth=self._auth(),
            Pto_venta=pto_vta,
            Cbte_Tipo=cbte_tipo,
        )
        _check_errors(resp, "FEXGetLast_CMP")
        return int(getattr(resp, "Cbte_nro", 0) or 0)

    def consultar(self, pto_vta: int, cbte_tipo: int, numero: int) -> Optional[dict[str, Any]]:
        """Consulta el comprobante de exportación (pto_vta, cbte_tipo, numero). Devuelve un dict
        con los campos, o `None` si no existe. Operación tentativa `FEXGetCMP` — a confirmar."""
        client = self._client()
        resp = self._soap(
            "FEXGetCMP",
            client.service.FEXGetCMP,
            Auth=self._auth(),
            Cmp={"Cbte_tipo": cbte_tipo, "Punto_vta": pto_vta, "Cbte_nro": numero},
        )
        if hasattr(resp, "FEXErr") and resp.FEXErr and getattr(resp.FEXErr, "ErrCode", 0):
            return None
        result = getattr(resp, "FEXResultGet", None)
        if result is None:
            return None
        return zeep.helpers.serialize_object(result, dict)

    # ------------------------------------------------------------------
    # COMMAND (efecto en AFIP — emite un comprobante de exportación legal)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_authorize_resp(resp: Any) -> "CaeResult":
        """Parsea la respuesta de `FEXAuthorize` a un `CaeResult` (reusado tal cual de
        `modelos.py` — la forma Resultado/CAE/CAEFchVto/Cbte_nro de WSFEXv1 es estructuralmente
        equivalente a la de WSFEv1; si al confirmar contra el WSDL real difiere, se separa recién
        ahí, ver docstring del módulo)."""
        from .modelos import CaeResult  # import local, evita circulares

        fex_resp = getattr(resp, "FEXResultAuth", None)
        if fex_resp is None:
            raise ArcaResponseError(
                "FEXAuthorize: AFIP no devolvió FEXResultAuth — respuesta inesperada, no se "
                "puede determinar el resultado.",
                raw=str(resp),
            )

        resultado = fex_resp.Resultado  # 'A' | 'R'
        cae: Optional[str] = None
        cae_vto = None
        numero: Optional[int] = None
        observaciones: list[str] = []
        errores: list[str] = []

        if resultado == "A":
            cae = fex_resp.Cae
            cae_vto = parse_fecha_arca(fex_resp.Fch_venc_Cae)
            numero = int(fex_resp.Cbte_nro)

        fex_err = getattr(resp, "FEXErr", None)
        if fex_err is not None and getattr(fex_err, "ErrCode", 0):
            errores.append(f"{fex_err.ErrCode}: {fex_err.ErrMsg}")

        fex_obs = getattr(resp, "FEXEvents", None)
        if fex_obs is not None and getattr(fex_obs, "EventCode", None):
            observaciones.append(f"{fex_obs.EventCode}: {fex_obs.EventMsg}")

        return CaeResult(
            resultado=resultado,
            cae=cae,
            cae_vto=cae_vto,
            numero=numero,
            observaciones=tuple(observaciones),
            errores=tuple(errores),
        )

    def autorizar(self, comprobante: "ComprobanteExportacionRequest", numero: int) -> "CaeResult":
        """Arma el payload (`comprobante_exportacion.armar_fexauthorize`) y envía `FEXAuthorize`.
        Parsea la respuesta en un `CaeResult` (reusado de `modelos.py`, ver `_parse_authorize_resp`).

        NUNCA asume éxito: valida `Resultado == 'A'` y extrae errores si `'R'` — mismo criterio
        que `WsfeClient.solicitar_cae`."""
        from .comprobante_exportacion import armar_fexauthorize

        payload = armar_fexauthorize(comprobante, numero)
        client = self._client()
        resp = self._soap(
            "FEXAuthorize",
            client.service.FEXAuthorize,
            Auth=self._auth(),
            Cmp=payload["Cmp"],
        )
        resultado = self._parse_authorize_resp(resp)

        fex_err = getattr(resp, "FEXErr", None)
        if fex_err is not None and getattr(fex_err, "ErrCode", 0) and not resultado.errores:
            resultado = replace(
                resultado, errores=resultado.errores + (f"{fex_err.ErrCode}: {fex_err.ErrMsg}",)
            )
        return resultado

    # ------------------------------------------------------------------
    # QUERIES (FEXGetPARAM_* — catálogos, sin efecto en AFIP)
    # ------------------------------------------------------------------

    def param_paises_destino(self) -> list[dict]:
        """Países destino válidos para `ReceptorExterior.pais_destino_id`
        (`FEXGetPARAM_DST_pais`, tentativo — campo de respuesta `Dst_pais`)."""
        client = self._client()
        resp = self._soap(
            "FEXGetPARAM_DST_pais", client.service.FEXGetPARAM_DST_pais, Auth=self._auth()
        )
        _check_errors_fex(resp)
        return _serialize_catalogo(getattr(resp, "FEXResultGet", None), "Dst_pais")

    def param_incoterms(self) -> list[dict]:
        """Incoterms válidos para `DatosExportacion.incoterm` (`FEXGetPARAM_Incoterms`, tentativo
        — campo de respuesta `Incoterm`)."""
        client = self._client()
        resp = self._soap(
            "FEXGetPARAM_Incoterms", client.service.FEXGetPARAM_Incoterms, Auth=self._auth()
        )
        _check_errors_fex(resp)
        return _serialize_catalogo(getattr(resp, "FEXResultGet", None), "Incoterm")

    def param_monedas(self) -> list[dict]:
        """Códigos de moneda válidos para `ComprobanteExportacionRequest.moneda`
        (`FEXGetPARAM_MON`, tentativo — campo de respuesta `Mon`)."""
        client = self._client()
        resp = self._soap("FEXGetPARAM_MON", client.service.FEXGetPARAM_MON, Auth=self._auth())
        _check_errors_fex(resp)
        return _serialize_catalogo(getattr(resp, "FEXResultGet", None), "Mon")

    def param_unidades_medida(self) -> list[dict]:
        """Unidades de medida válidas (`FEXGetPARAM_UMed`, tentativo — campo de respuesta `Umed`)
        — por si un ítem de exportación necesita discriminar cantidad/unidad en el futuro."""
        client = self._client()
        resp = self._soap("FEXGetPARAM_UMed", client.service.FEXGetPARAM_UMed, Auth=self._auth())
        _check_errors_fex(resp)
        return _serialize_catalogo(getattr(resp, "FEXResultGet", None), "Umed")

    def param_cotizacion(self, mon_id: str) -> dict:
        """Cotización oficial de ARCA para `mon_id` — mismo criterio que
        `WsfeClient.param_cotizacion`: el motor no la aplica solo, la trae para que el consumidor
        decida (`FEXGetPARAM_Ctz`, tentativo)."""
        client = self._client()
        resp = self._soap(
            "FEXGetPARAM_Ctz", client.service.FEXGetPARAM_Ctz, Auth=self._auth(), Mon_id=mon_id
        )
        _check_errors_fex(resp)
        result = getattr(resp, "FEXResultGet", None)
        return {
            "mon_id": getattr(result, "Mon_id", mon_id) if result else mon_id,
            "cotizacion": getattr(result, "Mon_ctz", None) if result else None,
        }


def _serialize_catalogo(result: Any, campo: str) -> list[dict]:
    """Extrae el array de un `FEXResultGet` (ej. `.Dst_pais`, `.Incoterm`) y lo serializa a
    `list[dict]` — nombres de campo TENTATIVOS (a confirmar contra el WSDL real, ver docstring del
    módulo). `[]` si `result` es `None` o el campo no está poblado."""
    if result is None:
        return []
    valores = getattr(result, campo, None)
    if not valores:
        return []
    return zeep.helpers.serialize_object(valores, dict) or []


def _check_errors_fex(resp: Any) -> None:
    """Levanta `ArcaBusinessError` si `resp.FEXErr.ErrCode` viene poblado — WSFEXv1 usa un nodo
    `FEXErr` singular (no un array `Errors.Err` como WSFEv1), tentativo, a confirmar."""
    fex_err = getattr(resp, "FEXErr", None)
    if fex_err is not None and getattr(fex_err, "ErrCode", 0):
        raise ArcaBusinessError(
            f"{fex_err.ErrCode}: {fex_err.ErrMsg}",
            errores=((_int_o_none(fex_err.ErrCode), str(fex_err.ErrMsg)),),
        )


def _check_errors(resp: Any, op: str) -> None:
    fex_err = getattr(resp, "FEXErr", None)
    if fex_err is not None and getattr(fex_err, "ErrCode", 0):
        raise ArcaBusinessError(
            f"{op} error — {fex_err.ErrCode}: {fex_err.ErrMsg}",
            errores=((_int_o_none(fex_err.ErrCode), str(fex_err.ErrMsg)),),
        )


def _int_o_none(v: Any) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
