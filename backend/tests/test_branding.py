"""Tests del motor de assets de marca (`services.branding`).

Cubre las piezas puras (sin browser): cálculo de aspect ratio del SVG y el
saneo de <script>. El rasterizado real (Chromium) y la derivación a R2 se
ejercitan en el flujo de PDFs / manualmente (necesitan browser + storage).
"""
from services.branding.rasterize import _sanitize, svg_aspect


class TestSvgAspect:
    def test_viewbox(self):
        svg = '<svg viewBox="0 0 3625.42 686.57" fill="currentColor"></svg>'
        assert abs(svg_aspect(svg) - 3625.42 / 686.57) < 1e-6

    def test_viewbox_cuadrado(self):
        assert svg_aspect('<svg viewBox="0 0 67 67"></svg>') == 1.0

    def test_width_height_fallback(self):
        assert svg_aspect('<svg width="200" height="100"></svg>') == 2.0

    def test_sin_dimensiones_devuelve_none(self):
        assert svg_aspect("<svg></svg>") is None

    def test_viewbox_invalido_no_explota(self):
        assert svg_aspect('<svg viewBox="0 0 0 0"></svg>') is None


class TestSanitize:
    def test_saca_script(self):
        out = _sanitize('<svg><script>alert(1)</script><path/></svg>')
        assert "<script" not in out
        assert "<path/>" in out

    def test_sin_script_intacto(self):
        svg = '<svg viewBox="0 0 10 10"><path d="M0 0"/></svg>'
        assert _sanitize(svg) == svg
