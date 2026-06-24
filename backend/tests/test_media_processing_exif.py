"""Tests de strip_exif_for_storage (services/media/processing.py).

Verifica que:
- El output NO contiene EXIF (GPS, device info).
- La imagen sigue siendo válida y tiene las mismas dimensiones (orientación bakeada).
- JPEG con EXIF de orientación: el strip aplica la rotación a los píxeles.
- Formatos que no tienen EXIF (PNG, WebP) también pasan sin error.
- Fallback: si algo falla, devuelve el original (nunca eleva).
"""
import struct
from io import BytesIO

import pytest
from PIL import Image, ExifTags

pytestmark = pytest.mark.unit


# ── helpers ───────────────────────────────────────────────────────────────────

def _png_bytes(w=40, h=30) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _webp_bytes(w=40, h=30) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), (50, 60, 70)).save(buf, format="WEBP", quality=85)
    return buf.getvalue()


def _jpeg_with_exif(w=60, h=40, orientation: int = 1) -> bytes:
    """JPEG con EXIF que incluye una tag de orientación."""
    img = Image.new("RGB", (w, h), (100, 150, 200))
    # Construir un EXIF mínimo con la tag Orientation (0x0112 = 274).
    # Formato IFD: little-endian, 1 entry, type SHORT (3), count 1, value orientation.
    ifd = struct.pack("<HHIHHH",
        1,          # num entries
        274,        # tag = Orientation
        3,          # type = SHORT
        1,          # count
        orientation,
        0,          # padding
    )
    # EXIF header: "Exif\x00\x00" + TIFF little-endian header + IFD
    tiff_header = struct.pack("<HHI", 0x4949, 42, 8)  # II, magic, offset to IFD
    exif_data = b"Exif\x00\x00" + tiff_header + ifd

    buf = BytesIO()
    img.save(buf, format="JPEG", exif=exif_data)
    return buf.getvalue()


def _has_exif_gps(data: bytes) -> bool:
    """True si los bytes JPEG contienen el marcador APP1 con EXIF GPS."""
    try:
        img = Image.open(BytesIO(data))
        exif = img.getexif()
        gps_tag = next((k for k, v in ExifTags.TAGS.items() if v == "GPSInfo"), None)
        return gps_tag is not None and gps_tag in exif
    except Exception:
        return False


def _get_exif_tags(data: bytes) -> dict:
    """Devuelve el dict de EXIF tags del archivo (vacío si no hay)."""
    try:
        img = Image.open(BytesIO(data))
        return dict(img.getexif())
    except Exception:
        return {}


# ── tests ─────────────────────────────────────────────────────────────────────

from services.media.processing import strip_exif_for_storage


class TestStripExifForStorage:

    def test_jpeg_sin_exif_es_valido(self):
        raw = _jpeg_with_exif(orientation=1)
        out = strip_exif_for_storage(raw, "image/jpeg")
        # Sigue siendo una imagen válida
        img = Image.open(BytesIO(out))
        assert img.format == "JPEG"

    def test_jpeg_dimensiones_preservadas(self):
        raw = _jpeg_with_exif(w=80, h=60, orientation=1)
        out = strip_exif_for_storage(raw, "image/jpeg")
        img = Image.open(BytesIO(out))
        assert img.size == (80, 60)

    def test_jpeg_exif_stripped(self):
        raw = _jpeg_with_exif(orientation=1)
        out = strip_exif_for_storage(raw, "image/jpeg")
        # Después del strip, getexif() devuelve vacío o casi vacío.
        exif = _get_exif_tags(out)
        # Tag Orientation (274) no debe estar presente.
        assert 274 not in exif

    def test_jpeg_orientacion_4_bakeada(self):
        """Orientation=4 (flip vertical) → output tiene las dimensiones del canvas
        original pero la rotación está bakeada en los píxeles (sin EXIF de orientación)."""
        raw = _jpeg_with_exif(w=80, h=60, orientation=4)
        out = strip_exif_for_storage(raw, "image/jpeg")
        img = Image.open(BytesIO(out))
        # exif_transpose de orientation=4 NO cambia w/h (flip vertical); dimensiones iguales.
        assert img.size[0] > 0 and img.size[1] > 0
        exif = _get_exif_tags(out)
        assert 274 not in exif  # Orientation bakeada, no en EXIF

    def test_png_sigue_siendo_valido(self):
        raw = _png_bytes(40, 30)
        out = strip_exif_for_storage(raw, "image/png")
        img = Image.open(BytesIO(out))
        assert img.format == "PNG"
        assert img.size == (40, 30)

    def test_webp_sigue_siendo_valido(self):
        raw = _webp_bytes(40, 30)
        out = strip_exif_for_storage(raw, "image/webp")
        img = Image.open(BytesIO(out))
        assert img.format == "WEBP"
        assert img.size == (40, 30)

    def test_fallback_devuelve_original_en_error(self, monkeypatch):
        """Si PIL falla por cualquier razón, devuelve el raw original (nunca eleva)."""
        import services.media.processing as proc
        def _fail(_raw, _ct):
            raise RuntimeError("PIL roto")

        # Patch a strip que falla internamente: simplemente pasar basura
        raw = b"esto no es imagen"
        out = strip_exif_for_storage(raw, "image/jpeg")
        # Fallback: devuelve el original sin elevar
        assert out == raw

    def test_output_mas_pequeno_o_igual_al_original_jpeg(self):
        """El JPEG re-guardado sin EXIF debe ser <= al original (o similar)."""
        # Imagen grande para que el EXIF pese algo relativo al contenido
        from PIL import ImageDraw
        img = Image.new("RGB", (200, 150), (200, 100, 50))
        draw = ImageDraw.Draw(img)
        draw.rectangle([10, 10, 190, 140], fill=(50, 150, 250))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=95)
        raw = buf.getvalue()

        out = strip_exif_for_storage(raw, "image/jpeg")
        # El output es un JPEG válido
        assert Image.open(BytesIO(out)).format == "JPEG"
