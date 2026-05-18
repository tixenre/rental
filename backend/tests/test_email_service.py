"""Tests del servicio de email.

Cubre:
- `get_backend()` resuelve el provider según env vars.
- `render_template()` renderiza con autoescape para HTML, sin para texto.
- `send_email()` loggea con status='sent' en éxito.
- `send_email()` loggea con status='failed' si el backend tira y no propaga.
- `send_email()` no propaga ni siquiera con `to` vacío/inválido.
"""
import pytest

from services.email import get_backend, send_email, render_template
from services.email.base import EmailBackendError
from services.email.test_backend import SENT_MAILS, InMemoryBackend
from services.email.resend_backend import ResendBackend
from services.email.smtp_backend import SmtpBackend


pytestmark = pytest.mark.unit


# ── DB mock ─────────────────────────────────────────────────────────────────

class FakeRow(dict):
    """dict-row con acceso por __getitem__ + .keys() (compat con row_to_dict)."""


class FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class FakeConn:
    """Conn que devuelve plantillas hardcoded y registra los INSERT a
    emails_log para inspección."""

    def __init__(self, templates):
        # templates: dict[key] = (subject, body_html, body_text)
        self.templates = templates
        self.inserted_logs = []
        self.committed = False

    def execute(self, sql, params=()):
        s = sql.strip().upper()
        if s.startswith("SELECT SUBJECT, BODY_HTML, BODY_TEXT FROM EMAIL_TEMPLATES"):
            key = params[0]
            t = self.templates.get(key)
            if not t:
                return FakeCursor([])
            return FakeCursor([
                FakeRow(subject=t[0], body_html=t[1], body_text=t[2]),
            ])
        if s.startswith("SELECT VALUE FROM APP_SETTINGS"):
            return FakeCursor([])  # sin override
        if s.startswith("INSERT INTO EMAILS_LOG"):
            self.inserted_logs.append({
                "to": params[0], "subject": params[1],
                "template_key": params[2], "alquiler_id": params[3],
                "status": params[4], "provider": params[5],
                "provider_id": params[6], "error": params[7],
            })
            return FakeCursor([FakeRow(id=len(self.inserted_logs))])
        return FakeCursor([])

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        pass


@pytest.fixture
def fake_db_with_templates(monkeypatch):
    conn = FakeConn(templates={
        "pedido_creado_cliente": (
            "Hola {{ cliente_nombre }}",
            "<p>Pedido {{ numero_pedido }} — {{ cliente_nombre }}</p>",
            "Pedido {{ numero_pedido }} — {{ cliente_nombre }}",
        ),
        "pedido_creado_admin": (
            "Nuevo #{{ numero_pedido }}",
            "<p>{{ cliente_email }}</p>",
            "{{ cliente_email }}",
        ),
    })
    monkeypatch.setattr("services.email.service.get_db", lambda: conn)
    return conn


@pytest.fixture(autouse=True)
def clear_sent_mails():
    SENT_MAILS.clear()
    yield
    SENT_MAILS.clear()


# ── get_backend() factory ──────────────────────────────────────────────────

class TestGetBackend:
    def test_explicit_test(self, monkeypatch):
        monkeypatch.setenv("EMAIL_PROVIDER", "test")
        b = get_backend()
        assert isinstance(b, InMemoryBackend)

    def test_explicit_resend(self, monkeypatch):
        monkeypatch.setenv("EMAIL_PROVIDER", "resend")
        monkeypatch.setenv("RESEND_API_KEY", "re_fake")
        b = get_backend()
        assert isinstance(b, ResendBackend)

    def test_explicit_smtp(self, monkeypatch):
        monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        b = get_backend()
        assert isinstance(b, SmtpBackend)

    def test_resend_inferred_from_api_key(self, monkeypatch):
        monkeypatch.delenv("EMAIL_PROVIDER", raising=False)
        monkeypatch.setenv("RESEND_API_KEY", "re_fake")
        monkeypatch.delenv("SMTP_HOST", raising=False)
        b = get_backend()
        assert isinstance(b, ResendBackend)

    def test_fallback_to_test(self, monkeypatch):
        monkeypatch.delenv("EMAIL_PROVIDER", raising=False)
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        monkeypatch.delenv("SMTP_HOST", raising=False)
        b = get_backend()
        assert isinstance(b, InMemoryBackend)


# ── render_template ─────────────────────────────────────────────────────────

class TestRenderTemplate:
    def test_renders_subject_html_text(self, fake_db_with_templates):
        r = render_template("pedido_creado_cliente", {
            "cliente_nombre": "Juan", "numero_pedido": 42,
        })
        assert r["subject"] == "Hola Juan"
        assert r["text"] == "Pedido 42 — Juan"
        assert "<p>Pedido 42 — Juan</p>" in r["html"]

    def test_html_autoescape_protege_xss(self, fake_db_with_templates):
        r = render_template("pedido_creado_cliente", {
            "cliente_nombre": "<script>alert(1)</script>",
            "numero_pedido": 1,
        })
        # subject + text: sin autoescape (texto plano).
        assert r["subject"] == "Hola <script>alert(1)</script>"
        # html: autoescape activo — script queda escapado.
        assert "<script>" not in r["html"]
        assert "&lt;script&gt;" in r["html"]

    def test_template_inexistente_tira_ValueError(self, fake_db_with_templates):
        with pytest.raises(ValueError):
            render_template("no_existe", {})


# ── send_email — happy path con InMemoryBackend ────────────────────────────────

class TestSendEmailOk:
    def test_envia_y_loggea(self, fake_db_with_templates, monkeypatch):
        monkeypatch.setenv("EMAIL_PROVIDER", "test")
        result = send_email(
            "pedido_creado_cliente",
            "cliente@ejemplo.com",
            {"cliente_nombre": "Juan", "numero_pedido": 7},
            alquiler_id=42,
        )
        assert result["ok"] is True
        assert result["provider"] == "test"
        # Mail registrado en backend in-memory
        assert len(SENT_MAILS) == 1
        assert SENT_MAILS[0]["to"] == "cliente@ejemplo.com"
        assert SENT_MAILS[0]["subject"] == "Hola Juan"
        # Log en BD (mockeada)
        assert len(fake_db_with_templates.inserted_logs) == 1
        log = fake_db_with_templates.inserted_logs[0]
        assert log["status"] == "sent"
        assert log["template_key"] == "pedido_creado_cliente"
        assert log["alquiler_id"] == 42
        assert log["provider"] == "test"
        assert fake_db_with_templates.committed


# ── send_email — error handling ────────────────────────────────────────────

class TestSendEmailFailures:
    def test_to_invalido_no_propaga(self, fake_db_with_templates):
        result = send_email("pedido_creado_cliente", "", {})
        assert result["ok"] is False
        # No debe haber intentado enviar
        assert len(SENT_MAILS) == 0

    def test_template_inexistente_loggea_failed(self, fake_db_with_templates):
        result = send_email("no_existe", "x@y.com", {})
        assert result["ok"] is False
        # Loggea el fallo con prefijo de error
        assert len(fake_db_with_templates.inserted_logs) == 1
        log = fake_db_with_templates.inserted_logs[0]
        assert log["status"] == "failed"
        assert log["template_key"] == "no_existe"

    def test_backend_falla_loggea_failed_y_no_propaga(self, fake_db_with_templates, monkeypatch):
        # Forzamos InMemoryBackend con fail=True
        from services.email import test_backend as tb_mod
        monkeypatch.setattr(
            "services.email.get_backend",
            lambda: tb_mod.InMemoryBackend(fail=True),
        )
        result = send_email("pedido_creado_cliente", "x@y.com", {
            "cliente_nombre": "X", "numero_pedido": 1,
        })
        assert result["ok"] is False
        assert "forced failure" in (result.get("error") or "")
        # Loggeado como failed
        log = fake_db_with_templates.inserted_logs[0]
        assert log["status"] == "failed"
        assert log["error"]
