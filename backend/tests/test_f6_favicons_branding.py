"""Tests de F6: Favicons/PWA desde branding.

- /favicon.png, /apple-touch-icon.png, /icon-512.png redirigen a la URL de R2
  guardada en app_settings cuando existe
- Si no hay setting (o falla la BD), sirven el archivo estático del repo
"""
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

import main


def _make_client():
    return TestClient(main.app, follow_redirects=False)


def _mock_conn(setting_value: str | None):
    """Conn mock que devuelve el setting_value dado."""
    conn = MagicMock()
    row = {"value": setting_value} if setting_value else None
    conn.execute.return_value.fetchone.return_value = row
    conn.close = MagicMock()
    return conn


# ── /favicon.png ─────────────────────────────────────────────────────────────

def test_favicon_redirige_a_r2_cuando_hay_setting():
    """GET /favicon.png → 302 a la URL de R2 si favicon_url está configurada."""
    r2_url = "https://cdn.example/branding/favicon.png?v=12345"
    with patch("main.get_db", return_value=_mock_conn(r2_url)):
        resp = _make_client().get("/favicon.png")
    assert resp.status_code == 302
    assert resp.headers["location"] == r2_url


def test_favicon_fallback_sin_setting():
    """GET /favicon.png → sirve el estático del repo si no hay setting."""
    with patch("main.get_db", return_value=_mock_conn(None)):
        with patch("main._serve_frontend") as mock_serve:
            mock_serve.return_value = MagicMock(status_code=200)
            _make_client().get("/favicon.png")
    mock_serve.assert_called_once_with("favicon.png")


def test_favicon_fallback_ante_error_bd():
    """GET /favicon.png → sirve estático si la BD falla (no 500)."""
    conn = MagicMock()
    conn.execute.side_effect = RuntimeError("BD caída")
    conn.close = MagicMock()
    with patch("main.get_db", return_value=conn):
        with patch("main._serve_frontend") as mock_serve:
            mock_serve.return_value = MagicMock(status_code=200)
            resp = _make_client().get("/favicon.png")
    mock_serve.assert_called_once_with("favicon.png")


# ── /apple-touch-icon.png ────────────────────────────────────────────────────

def test_apple_touch_icon_redirige_a_r2():
    """GET /apple-touch-icon.png → 302 a R2 si apple_touch_icon_url configurada."""
    r2_url = "https://cdn.example/branding/apple-touch-icon.png?v=99"
    with patch("main.get_db", return_value=_mock_conn(r2_url)):
        resp = _make_client().get("/apple-touch-icon.png")
    assert resp.status_code == 302
    assert resp.headers["location"] == r2_url


def test_apple_touch_icon_fallback_sin_setting():
    """GET /apple-touch-icon.png → estático si no hay setting."""
    with patch("main.get_db", return_value=_mock_conn(None)):
        with patch("main._serve_frontend") as mock_serve:
            mock_serve.return_value = MagicMock(status_code=200)
            _make_client().get("/apple-touch-icon.png")
    mock_serve.assert_called_once_with("apple-touch-icon.png")


# ── /icon-512.png ─────────────────────────────────────────────────────────────

def test_icon_512_redirige_a_r2():
    """GET /icon-512.png → 302 a R2 si icon_512_url configurada."""
    r2_url = "https://cdn.example/branding/icon-512.png?v=55"
    with patch("main.get_db", return_value=_mock_conn(r2_url)):
        resp = _make_client().get("/icon-512.png")
    assert resp.status_code == 302
    assert resp.headers["location"] == r2_url


def test_icon_512_fallback_sin_setting():
    """GET /icon-512.png → estático si no hay setting."""
    with patch("main.get_db", return_value=_mock_conn(None)):
        with patch("main._serve_frontend") as mock_serve:
            mock_serve.return_value = MagicMock(status_code=200)
            _make_client().get("/icon-512.png")
    mock_serve.assert_called_once_with("icon-512.png")


def test_setting_no_http_no_redirige():
    """Si el valor guardado no empieza con 'http', NO redirige (evita valores corruptos)."""
    with patch("main.get_db", return_value=_mock_conn("/local/path.png")):
        with patch("main._serve_frontend") as mock_serve:
            mock_serve.return_value = MagicMock(status_code=200)
            resp = _make_client().get("/favicon.png")
    mock_serve.assert_called_once_with("favicon.png")
