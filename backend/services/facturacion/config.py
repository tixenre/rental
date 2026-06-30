"""Configuración por emisor del motor ARCA.

Lee todo de la tabla `emisores_arca` (CUIT, PtoVta, cert/clave cifrados).
La única variable de entorno necesaria es `ARCA_MASTER_KEY` (clave de cifrado)
y está en Railway — nunca en app_settings.

Gating default-deny (INVERSO a GA4): emite en producción SÓLO si `is_production`
es True. Ante la duda → homologación.
"""
from __future__ import annotations

from dataclasses import dataclass


_WSAA_HOMO = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms"
_WSFE_HOMO = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"

_WSAA_PROD = "https://wsaa.afip.gov.ar/ws/services/LoginCms"
_WSFE_PROD = "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL"


@dataclass(frozen=True)
class CredARCA:
    """Credenciales + configuración de un emisor para una llamada ARCA."""

    emisor_id: int
    emisor: str          # nombre del emisor (display / clave en afip_ta)
    condicion_iva: str   # 'responsable_inscripto' | 'monotributo' | 'exento'
    ambiente: str        # 'homologacion' | 'produccion'
    cuit: int
    punto_venta: int
    cert_pem: bytes
    key_pem: bytes
    endpoint_wsaa: str
    endpoint_wsfe: str


def credenciales(nombre_emisor: str, conn) -> CredARCA:
    """Resuelve las credenciales del emisor desde `emisores_arca`.

    Gating default-deny: producción solo si is_production=True.

    Args:
        nombre_emisor: nombre del emisor en `emisores_arca`.
        conn:          conexión DB activa.

    Raises:
        ValueError: emisor no encontrado, inactivo, sin cert, o datos inválidos.
        RuntimeError: ARCA_MASTER_KEY no configurada o no puede descifrar.
    """
    from services.facturacion.emisores_repo import get_by_nombre, get_cert_pem

    emisor = get_by_nombre(nombre_emisor, conn)
    if emisor is None:
        raise ValueError(
            f"Emisor '{nombre_emisor}' no encontrado. "
            "Configuralo en el back-office → Facturación ARCA → Emisores."
        )
    if not emisor.activo:
        raise ValueError(f"El emisor '{nombre_emisor}' está inactivo.")

    cert_pem, key_pem = get_cert_pem(emisor.id, conn)

    from config import settings as app_settings
    ambiente = "produccion" if app_settings.is_production else "homologacion"
    endpoint_wsaa = _WSAA_PROD if ambiente == "produccion" else _WSAA_HOMO
    endpoint_wsfe = _WSFE_PROD if ambiente == "produccion" else _WSFE_HOMO

    try:
        cuit_int = int(emisor.cuit.replace("-", "").replace(".", ""))
    except ValueError:
        raise ValueError(
            f"CUIT de '{nombre_emisor}' no es un número válido: '{emisor.cuit}'"
        )

    return CredARCA(
        emisor_id=emisor.id,
        emisor=nombre_emisor,
        condicion_iva=emisor.condicion_iva,
        ambiente=ambiente,
        cuit=cuit_int,
        punto_venta=emisor.pto_vta,
        cert_pem=cert_pem,
        key_pem=key_pem,
        endpoint_wsaa=endpoint_wsaa,
        endpoint_wsfe=endpoint_wsfe,
    )


def cert_cargado_para_emisor(emisor_id: int, conn) -> bool:
    """True si el emisor tiene cert + clave cargados en la tabla."""
    row = conn.execute(
        "SELECT cert_enc, key_enc FROM emisores_arca WHERE id = %s", (emisor_id,)
    ).fetchone()
    if not row:
        return False
    return bool(row["cert_enc"] and row["key_enc"])
