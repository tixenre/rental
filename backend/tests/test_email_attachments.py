"""Infra de adjuntos de email (#725) — test puro del contrato.

Verifica que el param `attachments` se propaga al backend y que el backend de
test registra los nombres. La integración real (renderizar PDFs + enviar) se
valida en staging.
"""

from services.email.base import Attachment
from services.email.test_backend import InMemoryBackend, SENT_MAILS


def test_backend_registra_adjuntos():
    SENT_MAILS.clear()
    backend = InMemoryBackend()
    backend.send(
        to="cliente@example.com",
        subject="Tus documentos",
        html="<p>hola</p>",
        text="hola",
        from_addr="Rambla <noreply@rambla.com>",
        attachments=[
            Attachment(filename="cotizacion.pdf", content=b"%PDF-1.4 fake"),
            Attachment(filename="contrato.pdf", content=b"%PDF-1.4 fake2"),
        ],
    )
    assert len(SENT_MAILS) == 1
    assert SENT_MAILS[0]["attachments"] == ["cotizacion.pdf", "contrato.pdf"]


def test_backend_sin_adjuntos_no_rompe():
    SENT_MAILS.clear()
    InMemoryBackend().send(
        to="x@example.com", subject="s", html="<p>h</p>", text="h",
        from_addr="f@example.com",
    )
    assert SENT_MAILS[0]["attachments"] == []


def test_attachment_mimetype_default_pdf():
    a = Attachment(filename="x.pdf", content=b"x")
    assert a.mimetype == "application/pdf"
