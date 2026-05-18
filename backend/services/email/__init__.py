"""Servicio de envío de email.

Entry points:
- `send_email(template_key, to, context, alquiler_id=None)`: renderiza una
  plantilla, envía y loggea en `emails_log`. Nunca propaga errores —
  cualquier fallo queda registrado con status='failed'.
- `get_backend()`: factory que devuelve el backend según `EMAIL_PROVIDER`.

Backends disponibles: resend, smtp, test.
"""
from __future__ import annotations

import os

from .base import EmailBackend, EmailBackendError, SendResult
from .service import send_email, render_template

__all__ = [
    "EmailBackend",
    "EmailBackendError",
    "SendResult",
    "send_email",
    "render_template",
    "get_backend",
]


def get_backend() -> EmailBackend:
    """Factory. Lee EMAIL_PROVIDER y devuelve la instancia adecuada.

    Orden de resolución:
    1. EMAIL_PROVIDER explícito ('resend' | 'smtp' | 'test').
    2. Si RESEND_API_KEY está seteado → resend.
    3. Si SMTP_HOST está seteado → smtp.
    4. Fallback → test (no envía, solo loggea en memoria; útil en dev/CI).
    """
    provider = (os.environ.get("EMAIL_PROVIDER") or "").lower().strip()

    if provider == "resend":
        from .resend_backend import ResendBackend
        return ResendBackend()
    if provider == "smtp":
        from .smtp_backend import SmtpBackend
        return SmtpBackend()
    if provider == "test":
        from .test_backend import InMemoryBackend
        return InMemoryBackend()

    if os.environ.get("RESEND_API_KEY"):
        from .resend_backend import ResendBackend
        return ResendBackend()
    if os.environ.get("SMTP_HOST"):
        from .smtp_backend import SmtpBackend
        return SmtpBackend()

    from .test_backend import InMemoryBackend
    return InMemoryBackend()
