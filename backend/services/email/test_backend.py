"""Backend in-memory para tests y dev. NO envía mails reales — guarda cada
envío en `SENT_MAILS` para inspección desde los tests.

Activado con `EMAIL_PROVIDER=test`. También se usa cuando ningún provider
real está configurado (no RESEND_API_KEY ni SMTP_HOST) para que dev local
no rompa.
"""
from __future__ import annotations

import uuid
from typing import List, Optional, Sequence

from .base import EmailAttachment, EmailBackend, SendResult

# Lista compartida — tests la pueden inspeccionar y limpiar con .clear().
SENT_MAILS: List[dict] = []


class InMemoryBackend(EmailBackend):
    name = "test"

    def __init__(self, *, fail: bool = False):
        # `fail=True` se usa en tests específicos para forzar EmailBackendError.
        self.fail = fail

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
        if self.fail:
            from .base import EmailBackendError
            raise EmailBackendError("test backend forced failure")
        message_id = f"test-{uuid.uuid4()}"
        SENT_MAILS.append({
            "to": to,
            "subject": subject,
            "html": html,
            "text": text,
            "from_addr": from_addr,
            "attachments": list(attachments or ()),
            "provider_id": message_id,
        })
        return SendResult(provider="test", provider_id=message_id)
