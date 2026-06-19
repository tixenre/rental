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
    """DIDIT_API_KEY o DIDIT_WORKFLOW_ID no configurados — feature apagada."""


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
        DiditNotConfiguredError: DIDIT_API_KEY o DIDIT_WORKFLOW_ID vacíos.
        httpx.HTTPStatusError:   La API de Didit devolvió un error HTTP.
        httpx.TimeoutException:  Timeout de red.
    """
    if not settings.DIDIT_API_KEY:
        raise DiditNotConfiguredError("DIDIT_API_KEY no configurada")
    if not settings.DIDIT_WORKFLOW_ID:
        raise DiditNotConfiguredError("DIDIT_WORKFLOW_ID no configurado")

    # API v3: auth por header `x-api-key` (NO Bearer); `workflow_id` obligatorio.
    payload = {
        "workflow_id": settings.DIDIT_WORKFLOW_ID,
        "callback": return_url,
        "vendor_data": vendor_data,
    }
    resp = httpx.post(
        _SESSION_ENDPOINT,
        headers={
            "x-api-key": settings.DIDIT_API_KEY,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30.0,
    )
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # El body de Didit contiene el mensaje real (ej. {"workflow_id": "Invalid workflow_id."}).
        # raise_for_status() lo descartaría — lo logueamos antes de re-lanzar.
        logger.error(
            "didit: HTTP %s al crear sesión — body=%s workflow_id=%s",
            exc.response.status_code,
            exc.response.text,
            settings.DIDIT_WORKFLOW_ID,
        )
        raise
    data = resp.json()
    return DiditSession(session_id=data["session_id"], url=data["url"])
