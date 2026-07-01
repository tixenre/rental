"""arca_fe.wsfe — cliente WSFEv1 (Facturación Electrónica) de ARCA. PORTABLE.

Construye el cliente zeep on-demand a partir del endpoint. No cachea; no persiste.
El caller (services/facturacion/) maneja la sesión y la BD.

Deps: zeep (SOAP), ya en requirements.txt.
"""
from __future__ import annotations

import ssl
import urllib3
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .modelos import CaeResult

import requests
import zeep
import zeep.helpers
import zeep.transports
from requests.adapters import HTTPAdapter

# WSDLs oficiales ARCA
_WSDL_HOMO = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"
_WSDL_PROD = "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL"

# Caché local de clientes SOAP (por endpoint, dentro del proceso)
_CLIENT_CACHE: dict[str, zeep.Client] = {}


class _AfipSSLAdapter(HTTPAdapter):
    """Los servidores de prod de AFIP usan parámetros DH cortos (DH_KEY_TOO_SMALL).
    SECLEVEL=1 los acepta sin bajar la verificación de certificado."""

    def init_poolmanager(self, num_pools, maxsize, block=False):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        self.poolmanager = urllib3.PoolManager(
            num_pools=num_pools,
            maxsize=maxsize,
            block=block,
            ssl_context=ctx,
        )


_TIMEOUT_SECONDS = 30.0


def _afip_transport() -> zeep.transports.Transport:
    session = requests.Session()
    session.mount("https://", _AfipSSLAdapter())
    # operation_timeout: sin esto zeep no aplica límite a las llamadas SOAP —
    # si AFIP se cuelga, la llamada espera indefinidamente sosteniendo el
    # advisory lock + el FOR UPDATE de afip_ta (bloquea TODA la facturación
    # de ese emisor). `timeout` cubre el fetch inicial del WSDL.
    return zeep.transports.Transport(
        session=session, timeout=_TIMEOUT_SECONDS, operation_timeout=_TIMEOUT_SECONDS
    )


def _get_client(endpoint: str) -> zeep.Client:
    """Devuelve el cliente zeep (cacheado en memoria por proceso)."""
    ep = endpoint.rstrip("/")
    if ep not in _CLIENT_CACHE:
        wsdl = _WSDL_HOMO if "homo" in ep or "wswhomo" in ep else _WSDL_PROD
        _CLIENT_CACHE[ep] = zeep.Client(wsdl, transport=_afip_transport())
    return _CLIENT_CACHE[ep]


@dataclass
class WsfeClient:
    """Cliente de alto nivel para WSFEv1.

    `endpoint`: base URL del servicio (ej: "wswhomo.afip.gov.ar").
    `cuit`: CUIT del emisor (sin guiones).
    `token`, `sign`: del TA vigente.
    """

    endpoint: str
    cuit: int
    token: str
    sign: str

    def _auth(self) -> dict:
        return {"Token": self.token, "Sign": self.sign, "Cuit": str(self.cuit)}

    def _client(self) -> zeep.Client:
        return _get_client(self.endpoint)

    # ------------------------------------------------------------------
    # FECompUltimoAutorizado — último comprobante autorizado
    # ------------------------------------------------------------------

    def ultimo_autorizado(self, pto_vta: int, cbte_tipo: int) -> int:
        """Devuelve el último número de comprobante autorizado para (pto_vta, cbte_tipo).

        Si nunca se emitió ninguno, ARCA devuelve 0.
        """
        client = self._client()
        resp = client.service.FECompUltimoAutorizado(
            Auth=self._auth(),
            PtoVta=pto_vta,
            CbteTipo=cbte_tipo,
        )
        _check_errors(resp, "FECompUltimoAutorizado")
        return int(resp.CbteNro)

    # ------------------------------------------------------------------
    # FECompConsultar — consultar un comprobante ya autorizado
    # ------------------------------------------------------------------

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
            if "10016" in str(exc) or "El comprobante consultado no existe" in str(exc):
                return None
            raise

        if resp is None:
            return None

        # Chequear si hay error de "no existe"
        if hasattr(resp, "Errors") and resp.Errors:
            for e in resp.Errors.Err:
                if e.Code in (10016,):
                    return None
            _raise_errors(resp.Errors.Err, "FECompConsultar")

        return zeep.helpers.serialize_object(resp.ResultGet, dict)

    # ------------------------------------------------------------------
    # FECAESolicitar — solicitar CAE
    # ------------------------------------------------------------------

    def solicitar_cae(self, fecae: dict) -> CaeResult:
        """Envía FECAESolicitar y parsea la respuesta en un CaeResult.

        NUNCA asume éxito: valida Resultado == 'A' y extrae errores si 'R'.
        """
        from .modelos import CaeResult  # import local para evitar circulares

        client = self._client()
        resp = client.service.FECAESolicitar(
            Auth=self._auth(),
            FeCAEReq=fecae,
        )

        result_obj = resp.FeDetResp.FECAEDetResponse[0]
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

        # Errores a nivel cabecera
        if hasattr(resp, "Errors") and resp.Errors:
            for err in resp.Errors.Err:
                errores.append(f"{err.Code}: {err.Msg}")

        # Errores a nivel ítem
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

    # ------------------------------------------------------------------
    # FEParamGetPtosVenta / FEParamGetTiposCbte — validaciones
    # ------------------------------------------------------------------

    def param_puntos_venta(self) -> list[dict]:
        """Devuelve los puntos de venta habilitados para el CUIT."""
        client = self._client()
        resp = client.service.FEParamGetPtosVenta(Auth=self._auth())
        _check_errors(resp, "FEParamGetPtosVenta")
        if resp.ResultGet is None:
            return []
        return zeep.helpers.serialize_object(resp.ResultGet.PtoVenta, list) or []

    def param_tipos_cbte(self) -> list[dict]:
        """Devuelve los tipos de comprobante disponibles."""
        client = self._client()
        resp = client.service.FEParamGetTiposCbte(Auth=self._auth())
        _check_errors(resp, "FEParamGetTiposCbte")
        if resp.ResultGet is None:
            return []
        return zeep.helpers.serialize_object(resp.ResultGet.CbteTipo, list) or []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_fecha(s: Any) -> Optional[date]:
    if s is None:
        return None
    s = str(s).strip()
    if len(s) == 8:
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _check_errors(resp: Any, op: str) -> None:
    if hasattr(resp, "Errors") and resp.Errors:
        _raise_errors(resp.Errors.Err, op)


def _raise_errors(errs: Any, op: str) -> None:
    msgs = [f"{e.Code}: {e.Msg}" for e in errs]
    raise RuntimeError(f"{op} error — {'; '.join(msgs)}")
