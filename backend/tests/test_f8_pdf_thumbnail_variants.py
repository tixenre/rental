"""Tests de F8: PDFs usan variante display-sm/thumb del motor para thumbnails.

- _thumb() prioriza foto_url_thumb > foto_url_sm > foto_url
- Fallback a foto_url para ítems pre-motor (sin variantes)
- Items sin foto: muestra el placeholder SVG (no rompe el PDF)
"""
from unittest.mock import patch


# ── _thumb() prioriza variante pequeña ───────────────────────────────────────

def _make_item(**kwargs):
    """Item mínimo para pasar a _thumb()."""
    return {"nombre": "Equipo Test", "foto_url": None, **kwargs}


def test_thumb_usa_foto_url_thumb_si_existe():
    """Si foto_url_thumb existe, la prefiere sobre foto_url_sm y foto_url."""
    from pdf_templates import _thumb
    item = _make_item(
        foto_url="https://r2.example/full.jpg",
        foto_url_sm="https://r2.example/sm.jpg",
        foto_url_thumb="https://r2.example/thumb.jpg",
    )
    with patch("pdf._abs_image_url", side_effect=lambda x: x):
        html = _thumb(item)
    assert "thumb.jpg" in html
    assert "full.jpg" not in html
    assert "sm.jpg" not in html


def test_thumb_usa_foto_url_sm_si_no_hay_thumb():
    """Si no hay thumb, usa foto_url_sm."""
    from pdf_templates import _thumb
    item = _make_item(
        foto_url="https://r2.example/full.jpg",
        foto_url_sm="https://r2.example/sm.jpg",
        foto_url_thumb=None,
    )
    with patch("pdf._abs_image_url", side_effect=lambda x: x):
        html = _thumb(item)
    assert "sm.jpg" in html
    assert "full.jpg" not in html


def test_thumb_fallback_a_foto_url():
    """Items pre-motor sin variantes: usa foto_url (fallback)."""
    from pdf_templates import _thumb
    item = _make_item(
        foto_url="https://cdn.example/legacy.jpg",
        foto_url_sm=None,
        foto_url_thumb=None,
    )
    with patch("pdf._abs_image_url", side_effect=lambda x: x):
        html = _thumb(item)
    assert "legacy.jpg" in html


def test_thumb_sin_ninguna_foto_devuelve_placeholder():
    """Si no hay ninguna URL, devuelve el div placeholder con el SVG (no error)."""
    from pdf_templates import _thumb
    item = _make_item(foto_url=None, foto_url_sm=None, foto_url_thumb=None)
    with patch("pdf._abs_image_url", return_value=""):
        html = _thumb(item)
    # El placeholder tiene la clase eq-thumb y el SVG de cámara
    assert "eq-thumb" in html
    assert "<svg" in html
    assert "<img" not in html


def test_thumb_sm_flag_agrega_clase_sm():
    """El flag sm=True agrega la clase 'sm' al elemento."""
    from pdf_templates import _thumb
    item = _make_item(foto_url="https://r2.example/img.jpg")
    with patch("pdf._abs_image_url", side_effect=lambda x: x):
        html = _thumb(item, sm=True)
    assert 'class="eq-thumb sm"' in html


def test_thumb_strings_vacios_se_tratan_como_none():
    """Strings vacíos en foto_url_thumb/foto_url_sm se ignoran correctamente."""
    from pdf_templates import _thumb
    item = _make_item(
        foto_url="https://r2.example/full.jpg",
        foto_url_sm="",
        foto_url_thumb="",
    )
    with patch("pdf._abs_image_url", side_effect=lambda x: x):
        html = _thumb(item)
    assert "full.jpg" in html
