"""Motor único de assets de marca.

De los SVG master (wordmark + isologo) subidos desde el back-office deriva los
PNG que consume el resto del sistema (logo del mail, favicon, íconos, preview
social). Un solo origen → derivados consistentes (barra de calidad: modularidad
a prueba de balas — `docs/MEMORIA.md`).

- `rasterize.render_svg_png`: pieza de bajo nivel; rasteriza un SVG a PNG
  reusando el Chromium headless de los PDFs (`pdf.py`). Cero dependencias nuevas.
- `derive_from_wordmark` / `derive_from_isologo`: arman la matriz de assets con
  los colores sancionados del Design System (par de inversión ink ↔ amber).
"""

from .derive import derive_from_isologo, derive_from_wordmark
from .rasterize import render_svg_png, sanitize_svg, svg_aspect

__all__ = [
    "render_svg_png",
    "svg_aspect",
    "sanitize_svg",
    "derive_from_wordmark",
    "derive_from_isologo",
]
