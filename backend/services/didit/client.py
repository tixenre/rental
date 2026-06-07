"""Cliente HTTP para la API de Didit — creación de sesiones de verificación.

Patrón "construido, se activa por config": si DIDIT_API_KEY está vacía, lanza
DiditNotConfiguredError. El route decide cómo manejarlo (devuelve 503).

Refs: https://docs.didit.me/integration/api-full-flow
"""

import logging
from dataclasses import dataclass

import httpx

from config import settings

logger = logging.getLogger(__name__)

_SESSION_ENDPOINT = "https://verification.didit.me/v3/session/"


class DiditNotConfiguredError(Exception):
    """DIDIT_API_KEY no está configurada — la feature está apagada."""


@dataclass
class DiditSession:
    session_id: str
    url: str


def create_session(*, return_url: str, vendor_data: str) -> DiditSession:
    """Crea una sesión de verificación en Didit y devuelve el session_id + URL.

    Args:
        return_url:   URL a la que Didit **redirige al usuario** cuando termina
                      el flujo (campo `callback` de la API). NO es el webhook:
                      el webhook server-to-server se configura aparte, una sola
                      vez, en el Console de Didit (de ahí sale DIDIT_WEBHOOK_SECRET).
                      Acá va una URL del portal para que el cliente vuelva a una
                      pantalla nuestra, no a un endpoint técnico.
        vendor_data:  String opaco para correlacionar el webhook con nuestro
                      cliente. Usamos str(cliente_id).

    Returns:
        DiditSession con session_id y url (redirigir al cliente a esta URL).

    Raises:
        DiditNotConfiguredError: DIDIT_API_KEY vacía — feature apagada.
        httpx.HTTPStatusError:   La API de Didit devolvió un error HTTP.
        httpx.TimeoutException:  Timeout de red.
    """
    if not settings.DIDIT_API_KEY:
        raise DiditNotConfiguredError("DIDIT_API_KEY no configurada")

    payload = {
        "callback": return_url,
        "vendor_data": vendor_data,
    }
    resp = httpx.post(
        _SESSION_ENDPOINT,
        headers={"Authorization": f"Bearer {settings.DIDIT_API_KEY}"},
        json=payload,
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return DiditSession(session_id=data["session_id"], url=data["url"])
