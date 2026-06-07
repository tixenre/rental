"""Didit — motor único de verificación de identidad (DNI + selfie → RENAPER).

Se activa por configuración: si DIDIT_API_KEY / DIDIT_WEBHOOK_SECRET no están
seteadas, los llamadores reciben un error claro (fail-closed).

Exports públicos:
  create_session         — crea una sesión de verificación en Didit
  verify_webhook         — verifica firma HMAC-SHA256 + freshness de un webhook
  DiditNotConfiguredError — API key / secret no seteada
  DiditSignatureError     — firma inválida o timestamp viejo
"""

from services.didit.client import DiditNotConfiguredError, DiditSession, create_session
from services.didit.webhook import DiditSignatureError, verify_webhook

__all__ = [
    "create_session",
    "verify_webhook",
    "DiditSession",
    "DiditNotConfiguredError",
    "DiditSignatureError",
]
