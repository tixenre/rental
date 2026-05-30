"""Tests del Settings tipado (#511).

Verifican el parsing centralizado (sets/listas/bools derivados) que antes
estaba repartido en cada lector. Se pasan valores explícitos al construir
`Settings(...)` (tienen prioridad sobre env/.env), así el test es determinista.
"""

import pytest

from config import Settings

pytestmark = pytest.mark.unit


def test_admin_emails_parsing():
    s = Settings(ADMIN_EMAILS="A@B.com, c@d.com ,")
    assert s.admin_emails == {"a@b.com", "c@d.com"}


def test_admin_emails_default():
    assert "tinchosantini@gmail.com" in Settings(ADMIN_EMAILS="tinchosantini@gmail.com").admin_emails


def test_frontend_origins_parsing():
    s = Settings(FRONTEND_ORIGINS="http://a.com, http://b.com ,")
    assert s.frontend_origins == ["http://a.com", "http://b.com"]


def test_site_url_strips_trailing_slash():
    assert Settings(SITE_URL="https://x.com/").SITE_URL == "https://x.com"
    assert Settings(SITE_URL="https://x.com").SITE_URL == "https://x.com"


def test_is_railway_y_cookie_secure():
    ra = Settings(RAILWAY_ENVIRONMENT="production", COOKIE_SECURE="")
    assert ra.is_railway is True
    assert ra.cookie_secure is True  # en Railway, Secure aunque COOKIE_SECURE vacío

    local = Settings(RAILWAY_ENVIRONMENT=None, COOKIE_SECURE="")
    assert local.is_railway is False
    assert local.cookie_secure is False
    assert Settings(RAILWAY_ENVIRONMENT=None, COOKIE_SECURE="true").cookie_secure is True
