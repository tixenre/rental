"""Tests de `services/image_upload.py` — optimización de imágenes (sin red/R2).

Cubre las funciones puras de procesamiento que NO tenían tests antes de
extraerse de equipos.py (#501 Fase 3): `_optimize_image` (auto-orient + trim +
cuadrado + resize 1200 + WebP) y `_ext_from_ctype`. La descarga anti-SSRF y el
upload a R2 NO se testean acá (SSRF está en test_ssrf.py; R2 necesita red real).
"""
from io import BytesIO

import pytest
from PIL import Image

from services.image_upload import _ext_from_ctype, _optimize_image

pytestmark = pytest.mark.unit


def _png_bytes(w=400, h=300, color=(120, 30, 200)):
    img = Image.new("RGB", (w, h), color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── _ext_from_ctype ──────────────────────────────────────────────────────────

class TestExtFromCtype:
    @pytest.mark.parametrize("ct,ext", [
        ("image/webp", "webp"),
        ("image/png", "png"),
        ("image/jpeg", "jpg"),
        ("image/gif", "gif"),
        ("image/avif", "avif"),
    ])
    def test_mapea_conocidos(self, ct, ext):
        assert _ext_from_ctype(ct) == ext

    def test_ctype_con_charset(self):
        # Content-Type suele venir con sufijo; debe seguir mapeando.
        assert _ext_from_ctype("image/webp; charset=binary") == "webp"

    def test_desconocido_cae_a_default(self):
        # No revienta ante un ctype inesperado.
        out = _ext_from_ctype("application/octet-stream")
        assert isinstance(out, str) and out


# ── _optimize_image ──────────────────────────────────────────────────────────

class TestOptimizeImage:
    def test_devuelve_webp_cuadrado_sin_upscale(self):
        # Imagen chica (400x300): se normaliza a CUADRADO pero NO se agranda a
        # 1200 (TARGET_SIDE es un techo, no un objetivo: solo reduce si supera).
        content, ctype, w, h = _optimize_image(_png_bytes(400, 300))
        assert ctype == "image/webp"
        assert w == h, "el resultado debe ser cuadrado"
        assert w <= 1200, "no debe superar el techo de 1200"
        assert isinstance(content, bytes) and len(content) > 0
        out = Image.open(BytesIO(content))
        assert out.format == "WEBP"
        assert out.size == (w, h)

    def test_imagen_grande_baja_a_1200(self):
        # Imagen que supera el techo: se reduce a 1200x1200.
        content, ctype, w, h = _optimize_image(_png_bytes(2000, 1500))
        assert (w, h) == (1200, 1200)
        assert ctype == "image/webp"

    def test_imagen_ya_cuadrada_se_conserva(self):
        content, ctype, w, h = _optimize_image(_png_bytes(800, 800))
        assert w == h and w <= 1200
        assert ctype == "image/webp"

    def test_contenido_basura_no_revienta(self):
        # Fallback: si no puede optimizar, no debe explotar la request.
        # (la función captura y cae al original o maneja el error)
        try:
            content, ctype, w, h = _optimize_image(b"no soy una imagen")
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"_optimize_image reventó con basura en vez de degradar: {e}")
        assert isinstance(content, bytes)
