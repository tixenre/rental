"""Tests del motor de assets de marca (`services.branding`).

Cubre las piezas puras (sin browser): cálculo de aspect ratio del SVG y el
saneo de <script>. El rasterizado real (Chromium) y la derivación a R2 se
ejercitan en el flujo de PDFs / manualmente (necesitan browser + storage).
"""
from services.branding.rasterize import _sanitize, sanitize_svg, svg_aspect


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


class TestSanitizeSvgInline:
    """`sanitize_svg` higieniza para inyección inline (web + PDF)."""

    def test_saca_on_handlers(self):
        out = sanitize_svg('<svg onload="x()"><path onclick="y()" d="M0 0"/></svg>')
        assert "onload" not in out
        assert "onclick" not in out
        assert "<path" in out

    def test_saca_javascript_href(self):
        out = sanitize_svg('<svg><a href="javascript:alert(1)"><path/></a></svg>')
        assert "javascript:" not in out

    def test_saca_script(self):
        out = sanitize_svg('<svg><script>x</script><path d="M0 0"/></svg>')
        assert "<script" not in out

    def test_preserva_fill_y_currentcolor(self):
        svg = '<svg viewBox="0 0 10 10" fill="currentColor"><path fill="#FAB428" d="M0 0"/></svg>'
        out = sanitize_svg(svg)
        assert 'fill="currentColor"' in out
        assert 'fill="#FAB428"' in out
