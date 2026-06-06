"""Rasterizador de SVG → PNG reutilizando el Chromium headless de los PDFs.

No agrega dependencias: el browser ya vive en `pdf.py` (un único proceso
compartido, lanzado para los documentos). Acá lo usamos para rasterizar los
SVG de marca a PNG nítidos en cualquier tamaño / color / fondo. Es la pieza de
bajo nivel del motor de assets de marca — `derive.py` arma la matriz de assets
encima de ésta.

El recoloreo se hace por CSS (`color:<fg>` + forzar `fill:currentColor` sobre
los paths con relleno): los SVG de marca del repo son **monocromáticos themables**
(ver `packages/design-system/src/assets/brand`), así que tiñen a un solo color
sin tocar los paths. Los huecos (`fill="none"`) se preservan.
"""
from __future__ import annotations

import re

_VIEWBOX_RE = re.compile(
    r'viewBox\s*=\s*["\']\s*[-\d.]+\s+[-\d.]+\s+([-\d.]+)\s+([-\d.]+)', re.I
)
_SVG_W_RE = re.compile(r'<svg\b[^>]*\bwidth\s*=\s*["\']([\d.]+)', re.I)
_SVG_H_RE = re.compile(r'<svg\b[^>]*\bheight\s*=\s*["\']([\d.]+)', re.I)
_SCRIPT_RE = re.compile(r"<script\b.*?</script\s*>", re.I | re.S)
_ON_ATTR_RE = re.compile(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I)
_JS_HREF_RE = re.compile(r"(href|xlink:href)\s*=\s*(\"|')\s*javascript:[^\"']*\2", re.I)


def svg_aspect(svg_text: str) -> float | None:
    """Relación ancho/alto del SVG (de viewBox; si no, de width/height). None si no se puede."""
    m = _VIEWBOX_RE.search(svg_text)
    if m:
        w, h = float(m.group(1)), float(m.group(2))
        if w > 0 and h > 0:
            return w / h
    mw, mh = _SVG_W_RE.search(svg_text), _SVG_H_RE.search(svg_text)
    if mw and mh:
        w, h = float(mw.group(1)), float(mh.group(1))
        if w > 0 and h > 0:
            return w / h
    return None


def _sanitize(svg_text: str) -> str:
    """Saca <script> del SVG (defensa básica; el upload ya es admin-only)."""
    return _SCRIPT_RE.sub("", svg_text)


def sanitize_svg(svg_text: str) -> str:
    """Sanea un SVG para inyectarlo inline en el DOM / en el HTML de un PDF.

    Saca `<script>`, atributos de evento (`onload`, `onclick`, …) y hrefs
    `javascript:`. El upload es admin-only (riesgo = self-XSS), pero igual se
    higieniza porque el SVG se inyecta como markup (inline), no vía `<img>`.
    """
    out = _SCRIPT_RE.sub("", svg_text)
    out = _ON_ATTR_RE.sub("", out)
    out = _JS_HREF_RE.sub("", out)
    return out.strip()


async def render_svg_png(
    svg_text: str,
    *,
    width: int,
    height: int,
    fg: str,
    bg: str | None,
    pad_pct: float = 0.0,
) -> bytes:
    """Rasteriza `svg_text` a un PNG de `width`×`height`.

    - `fg`: color de la marca (resuelve `currentColor` y fuerza el fill de la
      marca monocromática).
    - `bg`: color de fondo sólido, o `None` para fondo transparente.
    - `pad_pct`: padding interno como fracción del lado menor (aire alrededor).
    """
    from pdf import _get_browser

    svg = _sanitize(svg_text)
    transparent = bg is None
    page_bg = bg or "transparent"
    pad = round(min(width, height) * pad_pct)

    doc = (
        '<!doctype html><html><head><meta charset="utf-8"><style>'
        "html,body{margin:0;padding:0}"
        f"#stage{{width:{width}px;height:{height}px;box-sizing:border-box;padding:{pad}px;"
        "display:flex;align-items:center;justify-content:center;"
        f"background:{page_bg};color:{fg}}}"
        "#stage svg{max-width:100%;max-height:100%;width:auto;height:auto;display:block}"
        # Marca monocromática: todo fill sólido toma el color de marca (currentColor),
        # preservando los huecos (fill="none"/"transparent").
        '#stage svg [fill]:not([fill="none"]):not([fill="transparent"]){fill:currentColor}'
        "#stage svg path:not([fill]){fill:currentColor}"
        f"</style></head><body><div id=\"stage\">{svg}</div></body></html>"
    )

    browser = await _get_browser()
    page = await browser.new_page(viewport={"width": width, "height": height})
    try:
        await page.set_content(doc, wait_until="networkidle")
        el = await page.query_selector("#stage")
        png = await el.screenshot(omit_background=transparent, type="png")
    finally:
        await page.close()
    return png
