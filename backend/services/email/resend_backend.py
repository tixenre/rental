"""Backend de Resend (https://resend.com).

API HTTP simple: POST a /emails con Bearer token. Devuelve `{ id: "uuid" }`.
"""
from __future__ import annotations

import base64
import os
from typing import Optional, Sequence

import httpx

from .base import EmailAttachment, EmailBackend, EmailBackendError, SendResult


class ResendBackend(EmailBackend):
    name = "resend"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("RESEND_API_KEY", "")
        if not self.api_key:
            raise EmailBackendError("RESEND_API_KEY no configurado")

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
        payload = {
            "from": from_addr,
            "to": [to],
            "subject": subject,
            "html": html,
            "text": text,
        }
        if attachments:
            # Resend espera el contenido en base64 (string). Ver
            # https://resend.com/docs/api-reference/emails/send-email
            payload["attachments"] = [
                {
                    "filename": a.filename,
                    "content": base64.b64encode(a.content).decode("ascii"),
                    "content_type": a.content_type,
                }
                for a in attachments
            ]
        try:
            resp = httpx.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=15.0,
            )
        except httpx.HTTPError as e:
            raise EmailBackendError(f"Resend HTTP error: {e}") from e
        if resp.status_code >= 400:
            raise EmailBackendError(
                f"Resend devolvió {resp.status_code}: {resp.text[:300]}"
            )
        try:
            data = resp.json()
        except ValueError as e:
            raise EmailBackendError(f"Resend respuesta no-JSON: {resp.text[:200]}") from e
        provider_id = data.get("id") or ""
        return SendResult(provider="resend", provider_id=provider_id)
