"""Didit — motor único de verificación de identidad (DNI + selfie → RENAPER).

Se activa por configuración: si DIDIT_API_KEY / DIDIT_WEBHOOK_SECRET no están
seteadas, los llamadores reciben un error claro (fail-closed).

Exports públicos:
  create_session         — crea una sesión de verificación en Didit
  retrieve_decision      — recupera la decisión final por API (respaldo del webhook)
  extraer_datos_renaper  — parsea el `decision` v3 → DatosRenaper (identidad, puro)
  extraer_contactos      — parsea el `decision` v3 → ContactosVerificados (mail/tel, puro)
  verify_webhook         — verifica firma HMAC-SHA256 + freshness de un webhook
  recheck_cliente        — re-consulta el estado ACTUAL a Didit y lo aplica (admin,
                           self-service del cliente y el barrido de abandonadas)
  ClienteSinVerificacionError — el cliente no tiene ninguna sesión Didit conocida
  DatosRenaper           — datos del documento confirmados por RENAPER
  ContactoVerificado / ContactosVerificados — mail/tel verificados por Didit
  DiditNotConfiguredError — API key / secret no seteada
  DiditSignatureError     — firma inválida o timestamp viejo
"""

from services.didit.client import (
    DiditNotConfiguredError,
    DiditSession,
    create_session,
    retrieve_decision,
)
from services.didit.decision import (
    ContactoVerificado,
    ContactosVerificados,
    DatosRenaper,
    extraer_contactos,
    extraer_datos_renaper,
)
from services.didit.recheck import ClienteSinVerificacionError, recheck_cliente
from services.didit.webhook import DiditSignatureError, verify_webhook

__all__ = [
    "create_session",
    "retrieve_decision",
    "extraer_datos_renaper",
    "extraer_contactos",
    "verify_webhook",
    "recheck_cliente",
    "ClienteSinVerificacionError",
    "DatosRenaper",
    "ContactoVerificado",
    "ContactosVerificados",
    "DiditSession",
    "DiditNotConfiguredError",
    "DiditSignatureError",
]
