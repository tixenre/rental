"""Regresión: el preview HTML de documentos del portal se embebe en un <iframe>.

Bug: el middleware global de seguridad pone `X-Frame-Options: DENY` en TODA
respuesta (anti-clickjacking, #503). El portal del cliente previsualiza
remito/contrato/albarán dentro de un <iframe> del mismo origen, y `DENY`
bloquea todo embedding —incluido el propio— dejando el preview en blanco.

El fix: la respuesta HTML de preview declara `X-Frame-Options: SAMEORIGIN`, y
el middleware usa `setdefault` para no pisarla. Acá fijamos ese contrato.
"""

import pytest
from starlette.responses import HTMLResponse

from routes.cliente_portal import _doc_response, _DOC_PREVIEW_HEADERS


pytestmark = pytest.mark.unit


def test_preview_html_permite_iframe_mismo_origen():
    """format=html → HTMLResponse con X-Frame-Options: SAMEORIGIN (embebible)."""
    resp = _doc_response("<html><body>doc</body></html>", "remito-1.pdf", "html")
    assert isinstance(resp, HTMLResponse)
    assert resp.headers["X-Frame-Options"] == "SAMEORIGIN"
    # Sigue sin cachear (el documento se genera al vuelo).
    assert resp.headers["Cache-Control"] == "no-store, max-age=0"


def test_pdf_no_es_preview():
    """format=pdf → None: el caller sigue con el render de PDF (no se embebe)."""
    assert _doc_response("<html></html>", "remito-1.pdf", "pdf") is None


def test_preview_headers_constante():
    """El default global es DENY; la excepción de framing es explícita y local."""
    assert _DOC_PREVIEW_HEADERS["X-Frame-Options"] == "SAMEORIGIN"
