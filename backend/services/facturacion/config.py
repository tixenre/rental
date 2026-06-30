"""Configuración por emisor del motor ARCA.

Lee no-secretos de `app_settings` (CUIT/PtoVta) y secretos de ENV
(cert/clave en PEM). Determina el ambiente por `is_production` con
gating default-deny: ante la duda → homologación, NUNCA producción.

Secretos: AFIP_PABLO_CERT / AFIP_PABLO_KEY / AFIP_SANTINI_CERT / AFIP_SANTINI_KEY
(bytes PEM en las vars de entorno de Railway — no en app_settings, que tiene
GET público y se copia al clon de staging).
"""
from __future__ import annotations

import os
from dataclasses import dataclass


# ── Endpoints AFIP/ARCA ───────────────────────────────────────────────────────

_WSAA_HOMO = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms"
_WSFE_HOMO = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"

_WSAA_PROD = "https://wsaa.afip.gov.ar/ws/services/LoginCms"
_WSFE_PROD = "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL"


@dataclass(frozen=True)
class CredARCA:
    """Credenciales + configuración de un emisor para una llamada ARCA."""

    emisor: str          # 'pablo' | 'santini'
    ambiente: str        # 'homologacion' | 'produccion'
    cuit: int
    punto_venta: int
    cert_pem: bytes      # Certificado X.509 en PEM
    key_pem: bytes       # Clave privada en PEM
    endpoint_wsaa: str
    endpoint_wsfe: str


def credenciales(emisor: str, conn) -> CredARCA:
    """Resuelve las credenciales del emisor para el ambiente actual.

    Gating default-deny (INVERSO a GA4): emite en producción SÓLO si
    `is_production` es True Y el cert parece ser el de producción
    (contiene la URL de WSAA de prod en su uso previo o simplemente
    se fía del `is_production` del entorno). Ante la duda → homologación.

    Args:
        emisor: 'pablo' | 'santini'
        conn:   conexión DB activa (PGConnection) para leer app_settings.

    Raises:
        ValueError: si el emisor no es reconocido o faltan datos críticos.
    """
    if emisor not in ("pablo", "santini"):
        raise ValueError(f"Emisor desconocido: {emisor!r}. Debe ser 'pablo' o 'santini'.")

    from config import settings as app_settings  # import local → no cargar en boot

    # ── Ambiente (gating default-deny) ────────────────────────────────
    ambiente = "produccion" if app_settings.is_production else "homologacion"
    endpoint_wsaa = _WSAA_PROD if ambiente == "produccion" else _WSAA_HOMO
    endpoint_wsfe = _WSFE_PROD if ambiente == "produccion" else _WSFE_HOMO

    # ── No-secretos (CUIT/PtoVta) de app_settings ────────────────────
    cuit_key = f"afip_{emisor}_cuit"
    ptovta_key = f"afip_{emisor}_ptovta"

    rows = conn.execute(
        "SELECT key, value FROM app_settings WHERE key = ANY(%s)",
        ([cuit_key, ptovta_key],),
    ).fetchall()
    kv = {r["key"]: r["value"] for r in rows}

    cuit_str = (kv.get(cuit_key) or "").strip()
    ptovta_str = (kv.get(ptovta_key) or "").strip()

    if not cuit_str or not ptovta_str:
        raise ValueError(
            f"Faltan datos de facturación para el emisor '{emisor}'. "
            f"Cargá CUIT y Punto de Venta en Settings → Facturación."
        )

    try:
        cuit = int(cuit_str)
        punto_venta = int(ptovta_str)
    except ValueError:
        raise ValueError(
            f"CUIT o PtoVta de '{emisor}' no son números válidos: "
            f"cuit={cuit_str!r}, ptovta={ptovta_str!r}"
        )

    # ── Secretos (cert/clave) de ENV ─────────────────────────────────
    cert_var = f"AFIP_{emisor.upper()}_CERT"
    key_var = f"AFIP_{emisor.upper()}_KEY"
    cert_pem_str = os.getenv(cert_var, "").strip()
    key_pem_str = os.getenv(key_var, "").strip()

    if not cert_pem_str or not key_pem_str:
        raise ValueError(
            f"Faltan las variables de entorno {cert_var} y/o {key_var}. "
            "Cargalas en Railway (nunca en app_settings)."
        )

    return CredARCA(
        emisor=emisor,
        ambiente=ambiente,
        cuit=cuit,
        punto_venta=punto_venta,
        cert_pem=cert_pem_str.encode(),
        key_pem=key_pem_str.encode(),
        endpoint_wsaa=endpoint_wsaa,
        endpoint_wsfe=endpoint_wsfe,
    )


def cert_cargado(emisor: str) -> bool:
    """Devuelve True si las variables de entorno del cert/clave están presentes.

    No valida el contenido; solo informa al admin si las ENV están configuradas.
    Nunca expone el valor del secreto.
    """
    cert_var = f"AFIP_{emisor.upper()}_CERT"
    key_var = f"AFIP_{emisor.upper()}_KEY"
    return bool(os.getenv(cert_var, "").strip() and os.getenv(key_var, "").strip())
