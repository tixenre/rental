"""Backend SMTP genérico — para Gmail Workspace, Outlook 365, Postmark,
Mailtrap o cualquier servidor que hable SMTP+TLS.

Para Gmail: `SMTP_PASS` debe ser un App Password de 16 chars
(https://myaccount.google.com/apppasswords), no la contraseña normal.
"""
from __future__ import annotations

import os
import smtplib
import uuid
from email.message import EmailMessage
from typing import Optional, Sequence

from .base import EmailAttachment, EmailBackend, EmailBackendError, SendResult


class SmtpBackend(EmailBackend):
    name = "smtp"

    def __init__(self):
        self.host = os.environ.get("SMTP_HOST", "")
        self.port = int(os.environ.get("SMTP_PORT", "587"))
        self.user = os.environ.get("SMTP_USER", "")
        self.password = os.environ.get("SMTP_PASS", "")
        self.use_tls = os.environ.get("SMTP_TLS", "true").lower() != "false"
        if not self.host:
            raise EmailBackendError("SMTP_HOST no configurado")

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
        msg = EmailMessage()
        msg["From"] = from_addr
        msg["To"] = to
        msg["Subject"] = subject
        # Generamos un Message-ID propio para devolverlo como provider_id
        # — facilita trazabilidad en el log aunque el servidor sobreescriba.
        message_id = f"<{uuid.uuid4()}@rambla>"
        msg["Message-ID"] = message_id
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")

        for a in attachments or ():
            _attach(msg, a)

        try:
            with smtplib.SMTP(self.host, self.port, timeout=20) as s:
                if self.use_tls:
                    s.starttls()
                if self.user and self.password:
                    s.login(self.user, self.password)
                s.send_message(msg)
        except (smtplib.SMTPException, OSError) as e:
            raise EmailBackendError(f"SMTP error: {e}") from e

        return SendResult(provider="smtp", provider_id=message_id)


def _attach(msg: EmailMessage, a: EmailAttachment) -> None:
    """Agrega un adjunto a un EmailMessage, respetando su content_type y los
    parámetros extra (ej. `method=PUBLISH` de un `.ics`)."""
    base_type = a.content_type.split(";")[0].strip() or "application/octet-stream"
    maintype, _, subtype = base_type.partition("/")
    subtype = subtype or "octet-stream"
    # Parámetros extra del Content-Type (method, etc.), excluyendo charset
    # (lo maneja add_attachment para partes de texto).
    params = {}
    for part in a.content_type.split(";")[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            k = k.strip().lower()
            if k != "charset":
                params[k] = v.strip()
    if maintype == "text":
        msg.add_attachment(
            a.content.decode("utf-8", "replace"),
            subtype=subtype, filename=a.filename, params=params or None,
        )
    else:
        msg.add_attachment(
            a.content, maintype=maintype, subtype=subtype,
            filename=a.filename, params=params or None,
        )
