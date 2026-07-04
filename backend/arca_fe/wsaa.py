"""arca_fe.wsaa — cliente del WS de Autenticación ARCA (WSAA). PORTABLE.

Sin estado; sin I/O de BD. Recibe cert/key como bytes (PEM), devuelve (token, sign,
expira_at). El cacheado en `afip_ta` lo hace el adapter (`services/facturacion/wsaa_cache.py`).

Operaciones: `login`/`login_con_cert` son COMMANDS (mintean un Ticket de Acceso
en AFIP — hacen I/O de red); `construir_tra`/`firmar_tra` son puros (sin I/O).
Errores tipados vía `arca_fe.errores`: red → ArcaNetworkError, cert/clave →
ArcaAuthError, respuesta inesperada → ArcaResponseError.

Única dependencia extra: `cryptography` (ya instalada vía pyjwt[crypto]).
"""

from __future__ import annotations

import base64
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from xml.etree import ElementTree as ET

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.primitives.serialization.pkcs7 import (
    PKCS7SignatureBuilder,
)
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from ._ssl_afip import afip_ssl_context
from .errores import ArcaAuthError, ArcaNetworkError, ArcaResponseError


_logger = logging.getLogger(__name__)

_WSAA_SERVICE = "wsfe"
_TRA_TTL_SECONDS = 12 * 3600  # 12 h — AFIP rechaza expirationTime > 24 h


# ---------------------------------------------------------------------------
# TRA (Ticket de Requerimiento de Autenticación)
# ---------------------------------------------------------------------------


def construir_tra(
    servicio: str = _WSAA_SERVICE,
    *,
    ahora: Optional[datetime] = None,
    ttl: int = _TRA_TTL_SECONDS,
) -> bytes:
    """Construye el XML del TRA (LoginTicketRequest) — el pedido de autenticación que después
    firma `firmar_tra` y envía `login`/`login_con_cert` al WSAA.

    `servicio`: el WSAA_SERVICIO a autenticar (ej. `"wsfe"` para facturación,
    `"ws_sr_constancia_inscripcion"` para el padrón — `arca_fe.padron.WSAA_SERVICIO`) — CADA
    servicio necesita su propio TA, no son intercambiables.
    `ahora`: hora UTC de generación (inyectable para tests). Por defecto = now(UTC).
    `ttl`: segundos de vigencia del TRA (no del TA que WSAA devuelve — eso lo decide AFIP,
    típicamente ~12hs) antes de que expire el REQUEST mismo si no se usa.

    Devuelve el XML como bytes UTF-8, listo para `firmar_tra`."""
    if ahora is None:
        ahora = datetime.now(timezone.utc)

    _AR = timezone(timedelta(hours=-3))
    gen_time = (ahora - timedelta(minutes=10)).astimezone(_AR)
    exp_time = (ahora + timedelta(seconds=ttl)).astimezone(_AR)

    unique_id = int(hashlib.sha256(str(ahora.timestamp()).encode()).hexdigest(), 16) % (
        2**31
    )

    tra_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<loginTicketRequest version="1.0">
  <header>
    <uniqueId>{unique_id}</uniqueId>
    <generationTime>{gen_time.isoformat(timespec="seconds")}</generationTime>
    <expirationTime>{exp_time.isoformat(timespec="seconds")}</expirationTime>
  </header>
  <service>{servicio}</service>
</loginTicketRequest>"""
    return tra_xml.encode("utf-8")


# ---------------------------------------------------------------------------
# Firma CMS (PKCS#7, TRA embebido — NO detached)
# ---------------------------------------------------------------------------


def firmar_tra(
    tra: bytes,
    cert_pem: bytes,
    key_pem: bytes,
    *,
    key_password: Optional[bytes] = None,
) -> bytes:
    """Firma el TRA con CMS/PKCS#7 (signed-data, TRA embebido) usando el cert ARCA.

    AFIP rechaza una firma detached (`ns1:cms.sign.invalid`) — el TRA tiene
    que viajar embebido dentro del blob CMS.

    `key_password`: passphrase de la clave privada, o None si no está cifrada.
    Cuando el certificado lo sube un tercero (SaaS multi-emisor) es más
    probable que la clave venga protegida — se soporta explícitamente en vez
    de fallar con la excepción cruda de `cryptography`.

    Devuelve el mensaje CMS como bytes DER, que luego va en base64 al endpoint
    WSAA `LoginCms`.

    Levanta `ArcaAuthError` si el certificado o la clave no se pueden cargar
    (PEM inválido, clave cifrada sin passphrase, o passphrase incorrecta) —
    todos son "no podés autenticar con estas credenciales", el subtipo correcto.
    """
    try:
        cert = load_pem_x509_certificate(cert_pem)
    except Exception as exc:
        raise ArcaAuthError(
            f"No se pudo cargar el certificado PEM: {type(exc).__name__}: {exc}"
        ) from exc
    try:
        private_key = load_pem_private_key(key_pem, password=key_password)
    except TypeError as exc:
        # cryptography levanta TypeError cuando la clave está cifrada y no se
        # pasó password (o viceversa) — mensaje accionable en vez del críptico.
        raise ArcaAuthError(
            "La clave privada parece estar cifrada con passphrase: pasá "
            "`key_password`. (O la clave no está cifrada y se pasó una.)"
        ) from exc
    except Exception as exc:
        raise ArcaAuthError(
            f"No se pudo cargar la clave privada (¿passphrase incorrecta o PEM "
            f"inválido?): {type(exc).__name__}: {exc}"
        ) from exc

    cms = (
        PKCS7SignatureBuilder()
        .set_data(tra)
        .add_signer(cert, private_key, hashes.SHA256())
        .sign(serialization.Encoding.DER, [])  # TRA embebido; AFIP rechaza detached
    )
    return cms


# ---------------------------------------------------------------------------
# Login al WSAA
# ---------------------------------------------------------------------------


def _tra_cms_b64(
    tra: bytes,
    cert_pem: bytes,
    key_pem: bytes,
    *,
    key_password: Optional[bytes] = None,
) -> str:
    der = firmar_tra(tra, cert_pem, key_pem, key_password=key_password)
    return base64.b64encode(der).decode("ascii")


def login(
    tra_cms: bytes,
    endpoint: str,
    *,
    timeout: float = 30.0,
) -> tuple[str, str, datetime]:
    """POST al WSAA con el CMS firmado (operación `loginCms`), devuelve `(token, sign, expira_at)`
    — `expira_at` en UTC, la vigencia real del TA que decide AFIP (típicamente ~12hs; el caller
    es responsable de cachear y renovar antes de que venza, ver `wsaa_cache.get_ta` del adapter
    de Rambla para un ejemplo).

    `tra_cms` puede ser:
    - bytes DER del CMS (firma cruda, lo que devuelve `firmar_tra`) → se codifica en base64
      internamente.
    - bytes ya en base64 (ASCII) → se usa directamente, sin doble-codificar.
    `endpoint`: URL del servicio WSAA (homologación o producción — ya resuelta por el caller).
    `timeout`: segundos para la llamada HTTP (default 30.0).

    Levanta `ArcaNetworkError` si el WSAA no responde o devuelve un status HTTP de error;
    `ArcaResponseError` si la respuesta no trae `token`/`sign` en la forma esperada."""
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

    import httpx  # lazy: solo se necesita al llamar al endpoint WSAA real

    url = _wsaa_url(endpoint)
    try:
        resp = httpx.post(
            url,
            content=soap_body.encode("utf-8"),
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": "loginCms",
            },
            timeout=timeout,
            # Mismo ajuste TLS que wsfe/padron (SECLEVEL=1 por los parámetros DH
            # cortos de AFIP) — sin bajar la verificación del certificado.
            verify=afip_ssl_context(),
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        cuerpo = exc.response.text[:800] if exc.response.text else "(sin cuerpo)"
        raise ArcaNetworkError(
            f"WSAA devolvió {exc.response.status_code} para {url}:\n{cuerpo}"
        ) from exc
    except httpx.RequestError as exc:
        # timeout, conexión rechazada, DNS, TLS — falla de transporte, no una
        # respuesta de AFIP. Se surface tipada en vez de filtrar el httpx crudo.
        raise ArcaNetworkError(
            f"No se pudo contactar el WSAA en {url}: {type(exc).__name__}: {exc}"
        ) from exc
    return _parsear_login_response(resp.text)


def login_con_cert(
    servicio: str,
    cert_pem: bytes,
    key_pem: bytes,
    endpoint: str,
    *,
    ahora: Optional[datetime] = None,
    timeout: float = 30.0,
    key_password: Optional[bytes] = None,
) -> tuple[str, str, datetime]:
    """Helper de alto nivel: construye el TRA (`construir_tra`), lo firma (`firmar_tra`) y llama
    a `login` — el atajo habitual para autenticar contra un servicio en un solo llamado, en vez
    de encadenar las 3 funciones a mano.

    `servicio`: el WSAA_SERVICIO a autenticar (ver `construir_tra`).
    `cert_pem`/`key_pem`: certificado y clave privada del emisor, en PEM.
    `endpoint`: URL del servicio WSAA (homologación o producción).
    `ahora`: hora UTC de generación del TRA (inyectable para tests; ver `construir_tra`).
    `timeout`: segundos para la llamada HTTP (default 30.0).
    `key_password`: passphrase de la clave privada (`None` si no está cifrada).

    Devuelve `(token, sign, expira_at)` — mismo contrato que `login`. Levanta `ArcaAuthError`
    (cert/clave inválidos, ver `firmar_tra`), `ArcaNetworkError` o `ArcaResponseError` (ver
    `login`)."""
    tra = construir_tra(servicio, ahora=ahora)
    der = firmar_tra(tra, cert_pem, key_pem, key_password=key_password)
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
    """True si `b` YA es base64 ASCII válido (no bytes DER crudos). Más
    estricto que "decodifica como ASCII": valida el alfabeto y el padding
    base64, así un blob DER que por casualidad fuera todo-ASCII no se confunde
    con base64 ya codificado (y se codifica, como corresponde)."""
    try:
        base64.b64decode(b, validate=True)
        return True
    except (ValueError, TypeError):
        return False


def _parsear_login_response(xml_text: str) -> tuple[str, str, datetime]:
    """Extrae (token, sign, expira_at) del XML de respuesta del WSAA.

    AFIP devuelve un SOAP envelope donde <loginCmsReturn> contiene el
    loginTicketResponse como texto XML escapado (no como nodos hijos).
    Hay que parsearlo en dos pasos.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ArcaResponseError(
            f"Respuesta WSAA inválida: {xml_text[:200]}", raw=xml_text
        ) from exc

    def _iter_find(tree: ET.Element, tag: str) -> Optional[str]:
        for el in tree.iter():
            local = el.tag.split("}")[-1] if "}" in el.tag else el.tag
            if local == tag:
                return el.text
        return None

    # loginCmsReturn contiene el loginTicketResponse como texto XML escapado
    cms_return_text = _iter_find(root, "loginCmsReturn")
    if cms_return_text:
        try:
            inner = ET.fromstring(cms_return_text.strip())

            def _find(tag: str) -> Optional[str]:
                return _iter_find(inner, tag)
        except ET.ParseError:

            def _find(tag: str) -> Optional[str]:
                return _iter_find(root, tag)
    else:

        def _find(tag: str) -> Optional[str]:
            return _iter_find(root, tag)

    token = _find("token")
    sign = _find("sign")
    expiration = _find("expirationTime")

    if not token or not sign:
        raise ArcaResponseError(
            f"WSAA no devolvió token/sign: {xml_text[:300]}", raw=xml_text
        )

    expira_at: datetime
    if expiration:
        # Formato: "2024-12-01T15:30:00.000-03:00"
        try:
            expira_at = datetime.fromisoformat(expiration.replace("Z", "+00:00"))
        except ValueError:
            # fallback: 12h desde ahora. Se loguea: un formato inesperado en un
            # campo que AFIP siempre manda es señal de que algo cambió — no se
            # traga en silencio (el TA seguiría usable, pero queremos saberlo).
            _logger.warning(
                "WSAA: expirationTime con formato inesperado (%r) — usando "
                "fallback de 12h.",
                expiration,
            )
            expira_at = datetime.now(timezone.utc) + timedelta(hours=12)
    else:
        _logger.warning(
            "WSAA: respuesta sin expirationTime — usando fallback de 12h."
        )
        expira_at = datetime.now(timezone.utc) + timedelta(hours=12)

    if expira_at.tzinfo is None:
        expira_at = expira_at.replace(tzinfo=timezone.utc)

    return token, sign, expira_at
