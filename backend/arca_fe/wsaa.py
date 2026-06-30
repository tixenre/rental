"""arca_fe.wsaa — cliente del WS de Autenticación ARCA (WSAA). PORTABLE.

Sin estado; sin I/O de BD. Recibe cert/key como bytes (PEM), devuelve (token, sign,
expira_at). El cacheado en `afip_ta` lo hace el adapter (`services/facturacion/wsaa_cache.py`).

Única dependencia extra: `cryptography` (ya instalada vía pyjwt[crypto]).
"""
from __future__ import annotations

import base64
import hashlib
import textwrap
from datetime import datetime, timedelta, timezone
from typing import Optional
from xml.etree import ElementTree as ET

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.primitives.serialization.pkcs7 import (
    PKCS7Options,
    PKCS7SignatureBuilder,
)
from cryptography.hazmat.primitives.serialization import load_pem_private_key

import httpx


_WSAA_SERVICE = "wsfe"
_TRA_TTL_SECONDS = 36 * 3600  # 36 h (AFIP acepta hasta 48h, dejamos margen)


# ---------------------------------------------------------------------------
# TRA (Ticket de Requerimiento de Autenticación)
# ---------------------------------------------------------------------------


def construir_tra(
    servicio: str = _WSAA_SERVICE,
    *,
    ahora: Optional[datetime] = None,
    ttl: int = _TRA_TTL_SECONDS,
) -> bytes:
    """Construye el XML del TRA (LoginTicketRequest).

    `ahora` es la hora UTC de generación (inyectable para tests). Por defecto = now(UTC).
    """
    if ahora is None:
        ahora = datetime.now(timezone.utc)

    gen_time = ahora - timedelta(minutes=10)
    exp_time = ahora + timedelta(seconds=ttl)

    unique_id = int(hashlib.sha256(str(ahora.timestamp()).encode()).hexdigest(), 16) % (
        2**31
    )

    tra_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<loginTicketRequest version="1.0">
  <header>
    <uniqueId>{unique_id}</uniqueId>
    <generationTime>{gen_time.strftime("%Y-%m-%dT%H:%M:%S")}</generationTime>
    <expirationTime>{exp_time.strftime("%Y-%m-%dT%H:%M:%S")}</expirationTime>
  </header>
  <service>{servicio}</service>
</loginTicketRequest>"""
    return tra_xml.encode("utf-8")


# ---------------------------------------------------------------------------
# Firma CMS (PKCS#7 detached)
# ---------------------------------------------------------------------------


def firmar_tra(tra: bytes, cert_pem: bytes, key_pem: bytes) -> bytes:
    """Firma el TRA con CMS/PKCS#7 (signed-data, detached) usando el cert ARCA.

    Devuelve el mensaje CMS como bytes DER, que luego va en base64 al endpoint
    WSAA `LoginCms`.
    """
    cert = load_pem_x509_certificate(cert_pem)
    private_key = load_pem_private_key(key_pem, password=None)

    cms = (
        PKCS7SignatureBuilder()
        .set_data(tra)
        .add_signer(cert, private_key, hashes.SHA256())
        .sign(serialization.Encoding.DER, [PKCS7Options.DetachedSignature])
    )
    return cms


# ---------------------------------------------------------------------------
# Login al WSAA
# ---------------------------------------------------------------------------


def _tra_cms_b64(tra: bytes, cert_pem: bytes, key_pem: bytes) -> str:
    der = firmar_tra(tra, cert_pem, key_pem)
    return base64.b64encode(der).decode("ascii")


def login(
    tra_cms: bytes,
    endpoint: str,
    *,
    timeout: float = 30.0,
) -> tuple[str, str, datetime]:
    """POST al WSAA con el CMS firmado, devuelve (token, sign, expira_at UTC).

    `tra_cms` puede ser:
    - bytes DER del CMS (firma cruda) → se codifica en base64 internamente.
    - bytes ya en base64 (ASCII) → se usa directamente.
    """
    if _parece_base64(tra_cms):
        cms_b64 = tra_cms.decode("ascii")
    else:
        cms_b64 = base64.b64encode(tra_cms).decode("ascii")

    soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:wsaa="http://wsaa.view.sua.dvadac.desein.afip.gov.ar">
  <soapenv:Body>
    <wsaa:loginCms>
      <wsaa:in0>{cms_b64}</wsaa:in0>
    </wsaa:loginCms>
  </soapenv:Body>
</soapenv:Envelope>"""

    url = _wsaa_url(endpoint)
    resp = httpx.post(
        url,
        content=soap_body.encode("utf-8"),
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "loginCms",
        },
        timeout=timeout,
        verify=True,
    )
    resp.raise_for_status()
    return _parsear_login_response(resp.text)


def login_con_cert(
    servicio: str,
    cert_pem: bytes,
    key_pem: bytes,
    endpoint: str,
    *,
    ahora: Optional[datetime] = None,
    timeout: float = 30.0,
) -> tuple[str, str, datetime]:
    """Helper de alto nivel: construye TRA, firma y llama a `login`."""
    tra = construir_tra(servicio, ahora=ahora)
    der = firmar_tra(tra, cert_pem, key_pem)
    return login(der, endpoint, timeout=timeout)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _wsaa_url(endpoint: str) -> str:
    """Normaliza el endpoint: agrega /ws/services/LoginCms si hace falta."""
    ep = endpoint.rstrip("/")
    suffix = "/ws/services/LoginCms"
    if ep.endswith(suffix):
        return ep
    if "://" not in ep:
        ep = "https://" + ep
    return ep + suffix


def _parece_base64(b: bytes) -> bool:
    try:
        b.decode("ascii")
        return True
    except UnicodeDecodeError:
        return False


def _parsear_login_response(xml_text: str) -> tuple[str, str, datetime]:
    """Extrae (token, sign, expira_at) del XML de respuesta del WSAA."""
    # Limpia namespace prefixes para simplificar la búsqueda
    xml_clean = xml_text
    try:
        root = ET.fromstring(xml_clean)
    except ET.ParseError:
        raise ValueError(f"Respuesta WSAA inválida: {xml_text[:200]}")

    # Busca el nodo loginTicketResponse en cualquier namespace
    def _find(tag: str) -> Optional[str]:
        for el in root.iter():
            local = el.tag.split("}")[-1] if "}" in el.tag else el.tag
            if local == tag:
                return el.text
        return None

    token = _find("token")
    sign = _find("sign")
    expiration = _find("expirationTime")

    if not token or not sign:
        raise ValueError(f"WSAA no devolvió token/sign: {xml_text[:300]}")

    expira_at: datetime
    if expiration:
        # Formato: "2024-12-01T15:30:00.000-03:00"
        try:
            expira_at = datetime.fromisoformat(expiration.replace("Z", "+00:00"))
        except ValueError:
            # fallback: 12h desde ahora
            expira_at = datetime.now(timezone.utc) + timedelta(hours=12)
    else:
        expira_at = datetime.now(timezone.utc) + timedelta(hours=12)

    if expira_at.tzinfo is None:
        expira_at = expira_at.replace(tzinfo=timezone.utc)

    return token, sign, expira_at
