"""Backend abstracto para envío de email.

Cada implementación concreta (resend, smtp, test) hereda y debe definir
`send(...)`. La factory `get_backend()` en `__init__.py` decide cuál
instanciar según la env var `EMAIL_PROVIDER`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass
class EmailAttachment:
    """Un adjunto de mail. `content` son los bytes crudos; cada backend lo
    codifica según su transporte (Resend: base64 en el JSON; SMTP: parte MIME).

    Caso de uso inicial: el `.ics` de la reserva en el mail de confirmación
    (estilo "pasaje de avión") — ver `services/ical.py`."""
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"


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
        attachments: Optional[Sequence[EmailAttachment]] = None,
    ) -> SendResult:
        raise NotImplementedError
