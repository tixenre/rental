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

    def __init__(self, templates, disabled=None):
        # templates: dict[key] = (subject, body_html, body_text)
        self.templates = templates
        self.disabled = set(disabled or ())  # keys con enabled=False
        self.inserted_logs = []
        self.committed = False

    def execute(self, sql, params=()):
        s = sql.strip().upper()
        if s.startswith("SELECT ENABLED FROM EMAIL_TEMPLATES"):
            key = params[0]
            if key not in self.templates:
                return FakeCursor([])
            return FakeCursor([FakeRow(enabled=key not in self.disabled)])
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
        if s.startswith("SELECT ID FROM EMAILS_LOG"):
            # idempotency check: ¿ya hay sent para (template_key, alquiler_id)?
            tpl, aid = params[0], params[1]
            for i, log in enumerate(self.inserted_logs, 1):
                if (
                    log["template_key"] == tpl
                    and log["alquiler_id"] == aid
                    and log["status"] == "sent"
                ):
                    return FakeCursor([FakeRow(id=i)])
            return FakeCursor([])
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


class TestBrandedLayout:
    """El html se envuelve en el shell branded común; el text queda plano."""

    def test_html_envuelto_en_layout(self, fake_db_with_templates):
        r = render_template(
            "pedido_creado_cliente", {"cliente_nombre": "Juan", "numero_pedido": 7}
        )
        html = r["html"]
        assert "<!DOCTYPE html>" in html
        assert "Rambla Rental" in html  # footer / marca
        assert "#FAB428" in html  # barra de acento amber
        assert "<img" in html  # logo
        # El contenido del body sigue presente dentro del shell.
        assert "Pedido 7 — Juan" in html

    def test_text_no_se_envuelve(self, fake_db_with_templates):
        r = render_template(
            "pedido_creado_cliente", {"cliente_nombre": "Juan", "numero_pedido": 7}
        )
        assert "<!DOCTYPE" not in r["text"]
        assert "Pedido 7 — Juan" in r["text"]


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


# ── send_email — idempotency ──────────────────────────────────────────────────

class TestSendEmailIdempotency:
    """Templates transaccionales (pedido_creado_cliente, pedido_confirmado_cliente)
    no se envían dos veces para el mismo pedido aunque se invoque dos veces."""

    def test_segunda_llamada_misma_alquiler_id_es_skip(
        self, fake_db_with_templates, monkeypatch
    ):
        monkeypatch.setenv("EMAIL_PROVIDER", "test")
        ctx = {"cliente_nombre": "Ana", "numero_pedido": 99}
        r1 = send_email("pedido_creado_cliente", "a@b.com", ctx, alquiler_id=99)
        r2 = send_email("pedido_creado_cliente", "a@b.com", ctx, alquiler_id=99)
        assert r1["ok"] is True
        assert r2["ok"] is True
        assert r2.get("skipped") is True
        # Solo se envió 1 mail aunque se llamó 2 veces
        assert len(SENT_MAILS) == 1
        # Solo se loggeó 1 fila
        assert len(fake_db_with_templates.inserted_logs) == 1

    def test_alquiler_distinto_si_envia(
        self, fake_db_with_templates, monkeypatch
    ):
        monkeypatch.setenv("EMAIL_PROVIDER", "test")
        ctx = {"cliente_nombre": "Ana", "numero_pedido": 1}
        send_email("pedido_creado_cliente", "a@b.com", ctx, alquiler_id=1)
        send_email("pedido_creado_cliente", "a@b.com", ctx, alquiler_id=2)
        # Dos alquileres distintos → dos envíos
        assert len(SENT_MAILS) == 2
        assert len(fake_db_with_templates.inserted_logs) == 2

    def test_sin_alquiler_id_no_se_aplica_idempotency(
        self, fake_db_with_templates, monkeypatch
    ):
        # Sin alquiler_id no podemos chequear (test de admin, etc) → envía igual
        monkeypatch.setenv("EMAIL_PROVIDER", "test")
        ctx = {"cliente_nombre": "Ana", "numero_pedido": 1}
        send_email("pedido_creado_cliente", "a@b.com", ctx, alquiler_id=None)
        send_email("pedido_creado_cliente", "a@b.com", ctx, alquiler_id=None)
        assert len(SENT_MAILS) == 2

    def test_template_no_idempotente_pasa_dos_veces(
        self, fake_db_with_templates, monkeypatch
    ):
        # pedido_creado_admin no está en el whitelist de idempotency
        monkeypatch.setenv("EMAIL_PROVIDER", "test")
        ctx = {"cliente_email": "a@b.com", "numero_pedido": 1}
        send_email("pedido_creado_admin", "admin@x.com", ctx, alquiler_id=5)
        send_email("pedido_creado_admin", "admin@x.com", ctx, alquiler_id=5)
        assert len(SENT_MAILS) == 2


# ── On/off por plantilla (enabled) ───────────────────────────────────────────

class TestEnabledGate:
    def test_template_apagado_no_envia_ni_loggea(self, monkeypatch):
        monkeypatch.setenv("EMAIL_PROVIDER", "test")
        conn = FakeConn(
            templates={"pedido_creado_cliente": ("S", "<p>{{ numero_pedido }}</p>", "x")},
            disabled={"pedido_creado_cliente"},
        )
        monkeypatch.setattr("services.email.service.get_db", lambda: conn)
        res = send_email("pedido_creado_cliente", "a@b.com", {"numero_pedido": 1})
        assert res["ok"] is True and res.get("skipped") is True
        assert res.get("reason") == "disabled"
        assert SENT_MAILS == []
        assert conn.inserted_logs == []  # no ensucia el log

    def test_respect_enabled_false_ignora_el_apagado(self, monkeypatch):
        # El envío de prueba del admin (respect_enabled=False) manda igual.
        monkeypatch.setenv("EMAIL_PROVIDER", "test")
        conn = FakeConn(
            templates={"pedido_creado_cliente": ("S", "<p>{{ numero_pedido }}</p>", "x")},
            disabled={"pedido_creado_cliente"},
        )
        monkeypatch.setattr("services.email.service.get_db", lambda: conn)
        res = send_email(
            "pedido_creado_cliente", "a@b.com", {"numero_pedido": 1},
            respect_enabled=False,
        )
        assert res["ok"] is True and not res.get("skipped")
        assert len(SENT_MAILS) == 1

    def test_template_prendido_envia_normal(self, monkeypatch):
        monkeypatch.setenv("EMAIL_PROVIDER", "test")
        conn = FakeConn(
            templates={"pedido_creado_cliente": ("S", "<p>{{ numero_pedido }}</p>", "x")},
        )  # sin disabled → enabled
        monkeypatch.setattr("services.email.service.get_db", lambda: conn)
        res = send_email("pedido_creado_cliente", "a@b.com", {"numero_pedido": 1})
        assert res["ok"] is True and not res.get("skipped")
        assert len(SENT_MAILS) == 1
