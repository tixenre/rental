"""Tests de adjuntos en el envío de mail.

Verifica que `send_email(..., attachments=[...])` llega hasta el backend con el
adjunto intacto (caso de uso: el `.ics` de la reserva en la confirmación). Usa el
InMemoryBackend (`EMAIL_PROVIDER=test`), que registra los adjuntos recibidos.
"""
import pytest

from services.email import send_email
from services.email.base import EmailAttachment
from services.email.smtp_backend import _attach
from services.email.test_backend import SENT_MAILS

pytestmark = pytest.mark.unit


class FakeRow(dict):
    pass


class FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class FakeConn:
    def __init__(self, templates):
        self.templates = templates
        self.inserted_logs = []

    def execute(self, sql, params=()):
        s = sql.strip().upper()
        if s.startswith("SELECT SUBJECT, BODY_HTML, BODY_TEXT FROM EMAIL_TEMPLATES"):
            t = self.templates.get(params[0])
            return FakeCursor([FakeRow(subject=t[0], body_html=t[1], body_text=t[2])] if t else [])
        if s.startswith("SELECT VALUE FROM APP_SETTINGS"):
            return FakeCursor([])
        if s.startswith("SELECT ID FROM EMAILS_LOG"):
            return FakeCursor([])
        if s.startswith("INSERT INTO EMAILS_LOG"):
            self.inserted_logs.append(params)
            return FakeCursor([FakeRow(id=len(self.inserted_logs))])
        return FakeCursor([])

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


@pytest.fixture
def fake_db(monkeypatch):
    conn = FakeConn(templates={
        "pedido_confirmado_cliente": (
            "Confirmado #{{ numero_pedido }}",
            "<p>ok</p>", "ok",
        ),
    })
    monkeypatch.setattr("services.email.service.get_db", lambda: conn)
    return conn


@pytest.fixture(autouse=True)
def clear_sent():
    SENT_MAILS.clear()
    yield
    SENT_MAILS.clear()


def _ics_attachment():
    return EmailAttachment(
        filename="pedido-50.ics",
        content=b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n",
        content_type="text/calendar; method=PUBLISH; charset=utf-8",
    )


class TestSendEmailAttachments:
    def test_adjunto_llega_al_backend(self, fake_db, monkeypatch):
        monkeypatch.setenv("EMAIL_PROVIDER", "test")
        result = send_email(
            "pedido_confirmado_cliente", "cliente@x.com",
            {"numero_pedido": 50}, alquiler_id=50,
            attachments=[_ics_attachment()],
        )
        assert result["ok"] is True
        assert len(SENT_MAILS) == 1
        adjuntos = SENT_MAILS[0]["attachments"]
        assert len(adjuntos) == 1
        assert adjuntos[0].filename == "pedido-50.ics"
        assert adjuntos[0].content_type.startswith("text/calendar")
        assert b"BEGIN:VCALENDAR" in adjuntos[0].content

    def test_sin_adjuntos_funciona_igual(self, fake_db, monkeypatch):
        monkeypatch.setenv("EMAIL_PROVIDER", "test")
        result = send_email(
            "pedido_confirmado_cliente", "cliente@x.com",
            {"numero_pedido": 50}, alquiler_id=51,
        )
        assert result["ok"] is True
        assert SENT_MAILS[0]["attachments"] == []


class TestSmtpAttach:
    """El helper de SMTP arma la parte MIME con el content-type correcto."""

    def test_attach_ics_como_text_calendar(self):
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["From"] = "a@b.com"
        msg["To"] = "c@d.com"
        msg["Subject"] = "x"
        msg.set_content("body")
        _attach(msg, _ics_attachment())
        partes = list(msg.iter_attachments())
        assert len(partes) == 1
        adj = partes[0]
        assert adj.get_content_type() == "text/calendar"
        assert adj.get_filename() == "pedido-50.ics"
        # El parámetro method viaja en el Content-Type.
        assert adj.get_param("method") == "PUBLISH"
