"""Backend abstracto para envío de email.

Cada implementación concreta (resend, smtp, test) hereda y debe definir
`send(...)`. La factory `get_backend()` en `__init__.py` decide cuál
instanciar según la env var `EMAIL_PROVIDER`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Attachment:
    """Un adjunto de email. `content` son los bytes crudos del archivo."""
    filename: str
    content: bytes
    mimetype: str = "application/pdf"


@dataclass
class SendResult:
    """Resultado de un envío exitoso. `provider_id` es lo que devuelve el
    provider (Resend: UUID del mensaje; SMTP: Message-ID header) para poder
    cruzar con su dashboard."""
    provider: str
    provider_id: str


class EmailBackendError(Exception):
    """El backend no pudo enviar el mail. El service la captura y loggea
    `status='failed'` en `emails_log` — no propaga al caller."""


class EmailBackend:
    """Interfaz que toda implementación de backend debe cumplir."""

    name: str = "abstract"

    def send(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        text: str,
        from_addr: str,
        attachments: list[Attachment] | None = None,
    ) -> SendResult:
        raise NotImplementedError
