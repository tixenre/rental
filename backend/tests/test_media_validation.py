"""Validación de seguridad de uploads de imagen (services/media/validation.py).

Cubre los dos vectores que defiende: rechazo de no-imágenes (magic-bytes, no confiar
en extensión) y el tope anti decompression-bomb. Antes el detector caía a jpeg ante
cualquier cosa — ahora rechaza con 400.
"""
from io import BytesIO

import pytest
from PIL import Image

from services.media.validation import validate_and_detect, MAX_PIXELS
from services.media.errors import MediaError


def _png_bytes(w: int = 10, h: int = 10) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), (200, 100, 50)).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(w: int = 10, h: int = 10) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), (10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def test_acepta_png_y_devuelve_ct_ext():
    assert validate_and_detect(_png_bytes()) == ("image/png", "png")


def test_acepta_jpeg():
    assert validate_and_detect(_jpeg_bytes()) == ("image/jpeg", "jpg")


def test_rechaza_vacio():
    with pytest.raises(MediaError) as e:
        validate_and_detect(b"")
    assert e.value.status == 400


def test_rechaza_no_imagen():
    # Bytes de texto plano — antes caía a jpeg, ahora rechaza.
    with pytest.raises(MediaError) as e:
        validate_and_detect(b"esto no es una imagen, soy un .txt renombrado a .jpg")
    assert e.value.status == 400


def test_rechaza_polyglot_basura_con_header_falso():
    # Header que finge PNG pero el resto es basura → PIL no lo valida.
    with pytest.raises(MediaError) as e:
        validate_and_detect(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    assert e.value.status == 400


def test_cap_de_pixeles_esta_seteado():
    # El cap global de PIL quedó fijado al importar validation (anti-bomb).
    assert Image.MAX_IMAGE_PIXELS == MAX_PIXELS
