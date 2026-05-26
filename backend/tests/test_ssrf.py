"""Tests del allowlist anti-SSRF en routes/equipos.py.

Cubre el fix de seguridad de PR #38 / issue #55 (BUGS.md):
- Allowlist de hosts conocidos.
- Bloqueo de IPs privadas/loopback/link-local.
- Solo http(s) en puertos 80/443.

Y el endurecimiento pre-launch (#503):
- DNS pinning: resolución única validada (mata DNS-rebinding).
- Redirects re-validados salto a salto (no se llega a IPs internas/metadata).
- `bypass_whitelist` eliminado.

NO testea el resolver DNS contra red real (lo mockea).
"""

import socket

import pytest
from fastapi import HTTPException

from routes import equipos
from routes.equipos import (
    _is_photo_host_allowed,
    _validate_external_image_url,
    _validate_image_url_static,
    _resolve_to_public_ip,
    _download_with_redirects,
    UploadFotoFromUrlInput,
)


pytestmark = pytest.mark.unit


def _addrinfo(*ips):
    """Construye una respuesta de getaddrinfo con las IPs dadas."""
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0)) for ip in ips]


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


class TestResolveToPublicIp:
    """DNS pinning: resuelve una vez, valida que TODAS las IPs sean públicas,
    y devuelve la primera para pinearla en la conexión."""

    def test_host_publico_devuelve_ip(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _addrinfo("93.184.216.34"))
        assert _resolve_to_public_ip("example.com") == "93.184.216.34"

    def test_host_privado_rechaza(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _addrinfo("10.0.0.5"))
        with pytest.raises(HTTPException) as exc:
            _resolve_to_public_ip("interno.malo.com")
        assert exc.value.status_code == 403

    def test_metadata_ip_rechaza(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _addrinfo("169.254.169.254"))
        with pytest.raises(HTTPException) as exc:
            _resolve_to_public_ip("rebind.malo.com")
        assert exc.value.status_code == 403

    def test_mixto_publico_y_privado_rechaza(self, monkeypatch):
        # Si resuelve a pública Y privada → rechaza (no se queda con la pública).
        monkeypatch.setattr(
            socket, "getaddrinfo",
            lambda *a, **k: _addrinfo("93.184.216.34", "169.254.169.254"),
        )
        with pytest.raises(HTTPException):
            _resolve_to_public_ip("rebind.malo.com")

    def test_no_resuelve_rechaza(self, monkeypatch):
        def _boom(*a, **k):
            raise socket.gaierror("no such host")
        monkeypatch.setattr(socket, "getaddrinfo", _boom)
        with pytest.raises(HTTPException) as exc:
            _resolve_to_public_ip("noexiste.malo.com")
        assert exc.value.status_code == 403


class TestValidateStaticNoDns:
    """`_validate_image_url_static` no resuelve DNS — solo scheme/host/puerto/allowlist."""

    def test_host_allowlist_pasa_sin_dns(self):
        # No mockeamos getaddrinfo: si tocara DNS, el test sería flaky. No debe tirar.
        _validate_image_url_static("https://www.bhphotovideo.com/img.jpg")

    def test_host_no_allowlist_rechaza(self):
        with pytest.raises(HTTPException) as exc:
            _validate_image_url_static("https://evil.attacker.com/x.jpg")
        assert exc.value.status_code == 403

    def test_metadata_ip_no_allowlist_rechaza(self):
        with pytest.raises(HTTPException):
            _validate_image_url_static("http://169.254.169.254/latest/meta-data/")


class TestDownloadWithRedirects:
    """El loop de redirects re-valida cada salto y pinea el DNS en cada uno."""

    def test_200_directo_devuelve_body(self, monkeypatch):
        monkeypatch.setattr(equipos, "_resolve_to_public_ip", lambda h: "1.2.3.4")
        monkeypatch.setattr(
            equipos, "_http_get_pinned",
            lambda url, ip, headers, timeout=20.0: (200, {"content-type": "image/jpeg"}, b"x" * 2000),
        )
        status, headers, body = _download_with_redirects("https://www.bhphotovideo.com/a.jpg", {})
        assert status == 200
        assert body == b"x" * 2000

    def test_redirect_a_metadata_bloqueado(self, monkeypatch):
        # 1er salto: host OK → 302 hacia la IP de metadata. El 2do salto NO está
        # en allowlist → _validate_image_url_static rechaza con 403.
        monkeypatch.setattr(equipos, "_resolve_to_public_ip", lambda h: "1.2.3.4")
        monkeypatch.setattr(
            equipos, "_http_get_pinned",
            lambda url, ip, headers, timeout=20.0: (
                302, {"location": "http://169.254.169.254/latest/meta-data/"}, b"",
            ),
        )
        with pytest.raises(HTTPException) as exc:
            _download_with_redirects("https://www.bhphotovideo.com/a.jpg", {})
        assert exc.value.status_code == 403

    def test_redirect_a_host_allowlist_que_resuelve_privado_bloqueado(self, monkeypatch):
        # El redirect va a un host del allowlist, pero que resuelve a IP privada.
        # _resolve_to_public_ip del 2do salto lo bloquea (DNS rebinding defense).
        calls = {"n": 0}

        def _get(url, ip, headers, timeout=20.0):
            calls["n"] += 1
            if calls["n"] == 1:
                return (302, {"location": "https://cdn.bhphotovideo.com/evil.jpg"}, b"")
            return (200, {"content-type": "image/jpeg"}, b"x" * 2000)

        def _resolve(host):
            if host.startswith("cdn."):
                raise HTTPException(403, "Host resuelve a IP privada/interna")
            return "1.2.3.4"

        monkeypatch.setattr(equipos, "_http_get_pinned", _get)
        monkeypatch.setattr(equipos, "_resolve_to_public_ip", _resolve)
        with pytest.raises(HTTPException) as exc:
            _download_with_redirects("https://www.bhphotovideo.com/a.jpg", {})
        assert exc.value.status_code == 403

    def test_redirect_chain_legitimo_pasa(self, monkeypatch):
        monkeypatch.setattr(equipos, "_resolve_to_public_ip", lambda h: "1.2.3.4")
        calls = {"n": 0}

        def _get(url, ip, headers, timeout=20.0):
            calls["n"] += 1
            if calls["n"] <= 2:
                return (302, {"location": "https://www.bhphotovideo.com/next.jpg"}, b"")
            return (200, {"content-type": "image/jpeg"}, b"x" * 2000)

        monkeypatch.setattr(equipos, "_http_get_pinned", _get)
        status, _, body = _download_with_redirects("https://www.bhphotovideo.com/a.jpg", {})
        assert status == 200
        assert calls["n"] == 3

    def test_demasiados_redirects_corta(self, monkeypatch):
        monkeypatch.setattr(equipos, "_resolve_to_public_ip", lambda h: "1.2.3.4")
        monkeypatch.setattr(
            equipos, "_http_get_pinned",
            lambda url, ip, headers, timeout=20.0: (
                302, {"location": "https://www.bhphotovideo.com/loop.jpg"}, b"",
            ),
        )
        with pytest.raises(HTTPException) as exc:
            _download_with_redirects("https://www.bhphotovideo.com/a.jpg", {})
        assert exc.value.status_code == 502


class TestBypassWhitelistEliminado:
    def test_modelo_no_tiene_bypass_whitelist(self):
        # El flag que apagaba el allowlist desde el body fue eliminado (#503).
        assert "bypass_whitelist" not in UploadFotoFromUrlInput.model_fields
