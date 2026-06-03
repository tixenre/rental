"""Tests del núcleo puro del módulo media (sin FastAPI, sin red, sin R2).

Cubre:
- processing: _optimize_image (square=True y square=False), _ext_from_ctype
- security: paridad de allowlist + status codes con el módulo legacy image_upload
- errors: MediaError es correctamente instanciable
- storage: delete_object best-effort (sin R2 configurado → False, nunca eleva)
"""
from io import BytesIO

import pytest
from PIL import Image

pytestmark = pytest.mark.unit


# ── helpers ──────────────────────────────────────────────────────────────────

def _png_bytes(w=400, h=300, color=(120, 30, 200)):
    img = Image.new("RGB", (w, h), color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── MediaError ────────────────────────────────────────────────────────────────

class TestMediaError:
    def test_instanciable(self):
        from services.media.errors import MediaError
        e = MediaError(404, "no encontrado")
        assert e.status == 404
        assert e.detail == "no encontrado"
        assert isinstance(e, Exception)

    def test_mensaje_propagado(self):
        from services.media.errors import MediaError
        e = MediaError(500, "algo falló")
        assert str(e) == "algo falló"


# ── processing._ext_from_ctype ───────────────────────────────────────────────

class TestExtFromCtypeMedia:
    @pytest.mark.parametrize("ct,ext", [
        ("image/webp", "webp"),
        ("image/png", "png"),
        ("image/jpeg", "jpg"),
        ("image/gif", "gif"),
        ("image/avif", "avif"),
    ])
    def test_mapea_conocidos(self, ct, ext):
        from services.media.processing import _ext_from_ctype
        assert _ext_from_ctype(ct) == ext

    def test_desconocido_cae_a_default(self):
        from services.media.processing import _ext_from_ctype
        out = _ext_from_ctype("application/octet-stream")
        assert isinstance(out, str) and out


# ── processing._optimize_image (square=True) ─────────────────────────────────

class TestOptimizeImageSquare:
    def test_devuelve_webp_cuadrado(self):
        from services.media.processing import _optimize_image
        content, ctype, w, h = _optimize_image(_png_bytes(400, 300), square=True)
        assert ctype == "image/webp"
        assert w == h, "debe ser cuadrado"
        assert w <= 1200

    def test_imagen_grande_baja_a_1200(self):
        from services.media.processing import _optimize_image
        content, ctype, w, h = _optimize_image(_png_bytes(2000, 1500), square=True)
        assert (w, h) == (1200, 1200)

    def test_basura_no_revienta(self):
        from services.media.processing import _optimize_image
        try:
            content, ctype, w, h = _optimize_image(b"no soy imagen", square=True)
        except Exception as e:
            pytest.fail(f"_optimize_image reventó con basura: {e}")
        assert isinstance(content, bytes)


# ── processing._optimize_image (square=False) ────────────────────────────────

class TestOptimizeImageAspecto:
    def test_mantiene_aspect_ratio_apaisado(self):
        from services.media.processing import _optimize_image
        content, ctype, w, h = _optimize_image(_png_bytes(3000, 2000), square=False)
        assert ctype == "image/webp"
        assert w != h, "branding NO debe ser cuadrado"
        assert abs((w / h) - 1.5) < 0.01

    def test_limita_lado_mas_largo_a_1600(self):
        from services.media.processing import _optimize_image
        content, ctype, w, h = _optimize_image(_png_bytes(4050, 2700), square=False)
        assert max(w, h) == 1600
        assert abs((w / h) - 1.5) < 0.01

    def test_no_upscale(self):
        from services.media.processing import _optimize_image
        content, ctype, w, h = _optimize_image(_png_bytes(800, 600), square=False)
        assert (w, h) == (800, 600)

    def test_sin_marco_blanco(self):
        from services.media.processing import _optimize_image
        content, ctype, w, h = _optimize_image(
            _png_bytes(1500, 1000, color=(30, 60, 90)), square=False,
        )
        img = Image.open(BytesIO(content)).convert("RGB")
        px = img.load()
        for x, y in [(2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)]:
            r, g, b = px[x, y]
            assert min(r, g, b) < 230, f"esquina ({x},{y}) quedó blanca: {(r, g, b)}"


# ── security: allowlist canónico (vive en services/media/security.py) ────────

class TestSecurityParidad:
    @pytest.mark.parametrize("host,expected", [
        ("bhphotovideo.com", True),
        ("cdn.bhphotovideo.com", True),
        ("dji.com", True),
        ("malicious.com", False),
        ("169.254.169.254", False),
    ])
    def test_is_photo_host_allowed(self, host, expected):
        from services.media.security import _is_photo_host_allowed
        assert _is_photo_host_allowed(host) == expected

    def test_validate_ssrf_only_rechaza_ip_loopback(self):
        from services.media.errors import MediaError
        from services.media.security import _validate_ssrf_only
        with pytest.raises(MediaError) as exc:
            _validate_ssrf_only("http://127.0.0.1/secreto")
        assert exc.value.status == 403

    def test_validate_ssrf_only_rechaza_scheme_ftp(self):
        from services.media.errors import MediaError
        from services.media.security import _validate_ssrf_only
        with pytest.raises(MediaError) as exc:
            _validate_ssrf_only("ftp://example.com/foto.jpg")
        assert exc.value.status == 400

    def test_validate_ssrf_only_rechaza_puerto_inusual(self):
        from services.media.errors import MediaError
        from services.media.security import _validate_ssrf_only
        with pytest.raises(MediaError) as exc:
            _validate_ssrf_only("http://example.com:8080/foto.jpg")
        assert exc.value.status == 400

    def test_validate_image_url_static_rechaza_host_no_permitido(self):
        from services.media.errors import MediaError
        from services.media.security import _validate_image_url_static
        with pytest.raises(MediaError) as exc:
            _validate_image_url_static("https://notallowed.example.com/foto.jpg")
        assert exc.value.status == 403

    def test_validate_image_url_static_acepta_host_permitido(self):
        from services.media.security import _validate_image_url_static
        # No debe lanzar (es solo validación estática, sin DNS)
        _validate_image_url_static("https://www.dji.com/foto.jpg")


# ── storage.delete_object best-effort ────────────────────────────────────────

class TestStorageDeleteObject:
    def test_key_vacia_devuelve_false(self):
        from services.media.storage import delete_object
        assert delete_object("") is False

    def test_r2_sin_configurar_no_revienta(self, monkeypatch):
        for var in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
            monkeypatch.delenv(var, raising=False)
        from services.media.storage import delete_object
        try:
            result = delete_object("media/estudio/1/original.jpg")
        except Exception as e:
            pytest.fail(f"delete_object propagó en vez de degradar: {e}")
        assert result is False
