"""Didit — motor único de verificación de identidad (DNI + selfie → RENAPER).

Se activa por configuración: si DIDIT_API_KEY / DIDIT_WEBHOOK_SECRET no están
seteadas, los llamadores reciben un error claro (fail-closed).

Exports públicos:
  create_session         — crea una sesión de verificación en Didit
  retrieve_decision      — recupera la decisión final por API (respaldo del webhook)
  extraer_datos_renaper  — parsea el `decision` v3 → DatosRenaper (puro)
  verify_webhook         — verifica firma HMAC-SHA256 + freshness de un webhook
  DatosRenaper           — datos del documento confirmados por RENAPER
  DiditNotConfiguredError — API key / secret no seteada
  DiditSignatureError     — firma inválida o timestamp viejo
"""

from services.didit.client import (
    DiditNotConfiguredError,
    DiditSession,
    create_session,
    retrieve_decision,
)
from services.didit.decision import DatosRenaper, extraer_datos_renaper
from services.didit.webhook import DiditSignatureError, verify_webhook

__all__ = [
    "create_session",
    "retrieve_decision",
    "extraer_datos_renaper",
    "verify_webhook",
    "DatosRenaper",
    "DiditSession",
    "DiditNotConfiguredError",
    "DiditSignatureError",
]
