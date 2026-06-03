"""Tests de procesamiento de imágenes — optimización sin red/R2.

Las funciones viven en services/media/processing.py y services/media/storage.py
(movidas de services/image_upload.py en F2 del pipeline de media).
"""
from io import BytesIO

import pytest
from PIL import Image

from services.media.processing import _ext_from_ctype, _optimize_image
from services.media.storage import delete_object as _delete_from_r2

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


class TestDeleteFromR2:
    """_delete_from_r2 es best-effort: nunca eleva, devuelve bool. El borrado de
    la foto en la base no debe quedar trabado si R2 falla."""

    def test_path_vacio_devuelve_false(self):
        assert _delete_from_r2("") is False

    def test_r2_sin_configurar_no_revienta(self, monkeypatch):
        # Sin env vars de R2, _r2_config eleva 500 adentro; el helper debe
        # capturarlo y degradar a False (no propagar la excepción).
        for var in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
            monkeypatch.delenv(var, raising=False)
        try:
            result = _delete_from_r2("estudio/123.webp")
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"_delete_from_r2 propagó en vez de degradar: {e}")
        assert result is False


class TestOptimizeImageBranding:
    """square=False → fotos de branding/estudio (hero): mantienen aspect ratio,
    sin cuadrado-con-fondo-blanco. Regresión del marco crema en el hero mobile."""

    def test_mantiene_aspect_ratio_apaisado(self):
        # Una foto 3:2 apaisada NO debe volverse cuadrada.
        content, ctype, w, h = _optimize_image(_png_bytes(3000, 2000), square=False)
        assert ctype == "image/webp"
        assert w != h, "branding NO debe ser cuadrado"
        assert abs((w / h) - 1.5) < 0.01, "debe preservar el ratio 3:2 original"

    def test_limita_lado_mas_largo_a_1600(self):
        content, ctype, w, h = _optimize_image(_png_bytes(4050, 2700), square=False)
        assert max(w, h) == 1600
        assert abs((w / h) - 1.5) < 0.01

    def test_no_upscale(self):
        # Una imagen chica no se agranda.
        content, ctype, w, h = _optimize_image(_png_bytes(800, 600), square=False)
        assert (w, h) == (800, 600)

    def test_sin_marco_blanco_en_los_bordes(self):
        # El bug: cuadrar con fondo blanco metía píxeles blancos en las esquinas.
        # Con square=False, una foto de color sólido no debe tener esquinas blancas.
        content, ctype, w, h = _optimize_image(
            _png_bytes(1500, 1000, color=(30, 60, 90)), square=False
        )
        img = Image.open(BytesIO(content)).convert("RGB")
        px = img.load()
        for x, y in [(2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)]:
            r, g, b = px[x, y]
            assert min(r, g, b) < 230, f"esquina ({x},{y}) quedó blanca: {(r, g, b)}"
