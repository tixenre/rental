"""Test del indicador de estado del canal de mail (`channel_status`).

Verifica la resolución del backend activo según el entorno (fuente única
`resolve_provider`) y que el resumen no exponga secretos.
"""
import pytest

import services.email as email_pkg
from config import settings
from services.email.service import channel_status

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("EMAIL_PROVIDER", "RESEND_API_KEY", "SMTP_HOST", "EMAIL_FROM", "EMAIL_ADMIN_TO"):
        monkeypatch.setattr(settings, k, "")
    # channel_status() lee from/admin_to de la DB → stubear la conexión.
    class _Cur:
        def fetchone(self):
            return None

    class _Conn:
        def execute(self, *a, **k):
            return _Cur()

        def close(self):
            pass

    monkeypatch.setattr("services.email.service.get_db", lambda: _Conn())


class TestResolveProvider:
    def test_default_es_test(self):
        assert email_pkg.resolve_provider() == "test"

    def test_resend_api_key_autodetecta(self, monkeypatch):
        monkeypatch.setattr(settings, "RESEND_API_KEY", "re_x")
        assert email_pkg.resolve_provider() == "resend"

    def test_smtp_host_autodetecta(self, monkeypatch):
        monkeypatch.setattr(settings, "SMTP_HOST", "smtp.x.com")
        assert email_pkg.resolve_provider() == "smtp"

    def test_provider_explicito_gana(self, monkeypatch):
        monkeypatch.setattr(settings, "RESEND_API_KEY", "re_x")
        monkeypatch.setattr(settings, "EMAIL_PROVIDER", "test")
        assert email_pkg.resolve_provider() == "test"


class TestChannelStatus:
    def test_apagado_por_default(self):
        st = channel_status()
        assert st["provider"] == "test"
        assert st["activo"] is False

    def test_activo_con_resend(self, monkeypatch):
        monkeypatch.setattr(settings, "RESEND_API_KEY", "re_x")
        monkeypatch.setattr(settings, "EMAIL_FROM", "Rambla <pedidos@rambla.com>")
        st = channel_status()
        assert st["provider"] == "resend"
        assert st["activo"] is True
        assert st["from_addr"] == "Rambla <pedidos@rambla.com>"

    def test_no_expone_api_key(self, monkeypatch):
        monkeypatch.setattr(settings, "RESEND_API_KEY", "re_supersecreto")
        st = channel_status()
        assert "re_supersecreto" not in str(st)
