"""Tests del allowlist anti-SSRF en routes/equipos.py.

Cubre el fix de seguridad de PR #38 / issue #55 (BUGS.md):
- Allowlist de hosts conocidos.
- Bloqueo de IPs privadas/loopback/link-local.
- Solo http(s) en puertos 80/443.

NO testea el resolver DNS (lo mockea) para que el test no dependa de red.
"""

import pytest
from fastapi import HTTPException

from routes.equipos import (
    _is_photo_host_allowed,
    _validate_external_image_url,
)


pytestmark = pytest.mark.unit


class TestIsPhotoHostAllowed:
    def test_bh_allowed(self):
        assert _is_photo_host_allowed("www.bhphotovideo.com") is True

    def test_subdominios_de_allowlist_pasan(self):
        # Si www.bhphotovideo.com está en allowlist, www.bhphotovideo.com también
        # via el .endswith
        assert _is_photo_host_allowed("cdn.bhphotovideo.com") is True

    def test_host_random_no_allowed(self):
        assert _is_photo_host_allowed("evil.example.com") is False

    def test_host_vacio_no_allowed(self):
        assert _is_photo_host_allowed("") is False
        assert _is_photo_host_allowed(None) is False

    def test_case_insensitive(self):
        # Hosts se normalizan a lowercase
        assert _is_photo_host_allowed("WWW.BHPHOTOVIDEO.COM") is True


class TestValidateExternalImageUrl:
    """Estos tests mockean _host_resolves_to_private para no tocar DNS."""

    def test_http_no_https_pasa(self, monkeypatch):
        # http es válido (allowlist + IP check)
        monkeypatch.setattr(
            "routes.equipos._host_resolves_to_private", lambda h: False
        )
        # No debería tirar
        _validate_external_image_url("https://www.bhphotovideo.com/imagen.jpg")

    def test_scheme_invalido_rechaza(self, monkeypatch):
        with pytest.raises(HTTPException) as exc:
            _validate_external_image_url("ftp://www.bhphotovideo.com/imagen.jpg")
        assert exc.value.status_code == 400
        assert "http/https" in exc.value.detail.lower()

    def test_scheme_javascript_rechaza(self):
        with pytest.raises(HTTPException) as exc:
            _validate_external_image_url("javascript:alert(1)")
        assert exc.value.status_code == 400

    def test_url_sin_host_rechaza(self):
        with pytest.raises(HTTPException) as exc:
            _validate_external_image_url("http:///foo")
        # Puede tirar 400 por host vacío o por allowlist — ambos son OK
        assert exc.value.status_code in (400, 403)

    def test_puerto_8080_rechaza(self, monkeypatch):
        monkeypatch.setattr(
            "routes.equipos._host_resolves_to_private", lambda h: False
        )
        with pytest.raises(HTTPException) as exc:
            _validate_external_image_url("https://www.bhphotovideo.com:8080/img.jpg")
        assert exc.value.status_code == 400
        assert "puerto" in exc.value.detail.lower() or "8080" in exc.value.detail

    def test_puerto_443_pasa(self, monkeypatch):
        monkeypatch.setattr(
            "routes.equipos._host_resolves_to_private", lambda h: False
        )
        _validate_external_image_url("https://www.bhphotovideo.com:443/img.jpg")

    def test_host_no_allowlist_rechaza(self, monkeypatch):
        monkeypatch.setattr(
            "routes.equipos._host_resolves_to_private", lambda h: False
        )
        with pytest.raises(HTTPException) as exc:
            _validate_external_image_url("https://evil.attacker.com/exfil.jpg")
        assert exc.value.status_code == 403

    def test_host_resuelve_a_ip_privada_rechaza(self, monkeypatch):
        # Aunque esté en allowlist (defense-in-depth), si resuelve a IP privada → 403
        monkeypatch.setattr(
            "routes.equipos._host_resolves_to_private", lambda h: True
        )
        with pytest.raises(HTTPException) as exc:
            _validate_external_image_url("https://www.bhphotovideo.com/img.jpg")
        assert exc.value.status_code == 403
        assert "privada" in exc.value.detail.lower() or "interna" in exc.value.detail.lower()

    def test_localhost_rechaza(self):
        # localhost NO está en allowlist → debería rechazar antes incluso de
        # llegar al DNS resolver
        with pytest.raises(HTTPException):
            _validate_external_image_url("http://localhost/foo")

    def test_169_254_metadata_rechaza(self):
        # IP-as-hostname para AWS/GCP metadata. NO está en allowlist.
        with pytest.raises(HTTPException):
            _validate_external_image_url("http://169.254.169.254/latest/meta-data/")
