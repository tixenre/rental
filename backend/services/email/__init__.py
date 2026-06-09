"""Servicio de envío de email.

Entry points:
- `send_email(template_key, to, context, alquiler_id=None)`: renderiza una
  plantilla, envía y loggea en `emails_log`. Nunca propaga errores —
  cualquier fallo queda registrado con status='failed'.
- `get_backend()`: factory que devuelve el backend según `EMAIL_PROVIDER`.

Backends disponibles: resend, smtp, test.
"""
from __future__ import annotations

from config import settings

from .base import Attachment, EmailBackend, EmailBackendError, SendResult
from .service import send_email, send_raw_email, render_template, wrap_preview

__all__ = [
    "Attachment",
    "EmailBackend",
    "EmailBackendError",
    "SendResult",
    "send_email",
    "send_raw_email",
    "render_template",
    "wrap_preview",
    "get_backend",
    "resolve_provider",
]


def resolve_provider() -> str:
    """Nombre del backend que se usaría hoy ('resend' | 'smtp' | 'test'),
    según el entorno, **sin instanciarlo** (instanciar Resend/SMTP valida
    credenciales y puede tirar). Fuente única de la resolución: la usan tanto
    `get_backend()` como el indicador de estado del canal.

    Orden: EMAIL_PROVIDER explícito → RESEND_API_KEY → SMTP_HOST → test.
    """
    provider = settings.EMAIL_PROVIDER.lower().strip()
    if provider in ("resend", "smtp", "test"):
        return provider
    if settings.RESEND_API_KEY:
        return "resend"
    if settings.SMTP_HOST:
        return "smtp"
    return "test"


def get_backend() -> EmailBackend:
    """Factory. Devuelve la instancia del backend activo (ver `resolve_provider`).

    Backend `test` no envía: solo loggea en memoria (dev/CI/sin configurar).
    """
    provider = resolve_provider()

    if provider == "resend":
        from .resend_backend import ResendBackend
        return ResendBackend()
    if provider == "smtp":
        from .smtp_backend import SmtpBackend
        return SmtpBackend()

    from .test_backend import InMemoryBackend
    return InMemoryBackend()
