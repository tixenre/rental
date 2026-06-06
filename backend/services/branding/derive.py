"""Matriz de assets de marca: de los SVG master (wordmark + isologo) deriva los
PNG que consume el sistema y los sube a R2, devolviendo las URLs (versionadas
con cache-buster) para guardar en `app_settings`.

Un solo origen → derivados consistentes (barra de calidad: modularidad). Reusa
el rasterizador (`rasterize.render_svg_png`, Chromium de los PDFs) y el storage
R2 (`services.media.storage.put`). No inventa colores: usa los tokens del DS y
el par de inversión sancionado **ink ↔ amber** (`docs/DESIGN_SYSTEM.md`).

Colores (hex de mail = fuente única en `services/email/branding`):
- email (header = celda amber sólida): wordmark **blanco sobre transparente** →
  el hueco de las letras muestra el amber de la celda (dark-mode safe).
- íconos cuadrados (favicon / apple-touch / icon-512): **tile amber + isologo
  ink** (par sancionado del DS). NOTA: `icon_512_url` es el ícono cuadrado; el
  preview social (`og_image_url`, que leen los crawlers del <head> estático) NO
  se alimenta acá — es un follow-up aparte (requiere prerender/SSR).
"""
from __future__ import annotations

import time

from .rasterize import render_svg_png, svg_aspect

AMBER = "#FAB428"   # --amber (token exacto)
INK = "#1f1a14"     # ink de mail (warm near-black legible)
WHITE = "#ffffff"

# Altura raster del wordmark (≈3× del display de ~34px en el header del mail).
_WM_H = 132
# Padding del isologo dentro del tile cuadrado (aire alrededor de la marca).
_ICON_PAD_PCT = 0.18


def _put_versioned(path: str, content: bytes, ctype: str) -> str:
    """Sube a R2 (path fijo → sobreescribe) y devuelve la URL con cache-buster."""
    from services.media.storage import put as _r2_put
    from services.media_fastapi import media_http

    with media_http():
        url = _r2_put(path, content, ctype)
    return f"{url}?v={int(time.time())}"


async def derive_from_wordmark(svg: str) -> dict[str, str]:
    """Del wordmark deriva el logo del mail (blanco sobre transparente).

    Devuelve {setting_key: url}.
    """
    aspect = svg_aspect(svg) or 4.0
    h = _WM_H
    w = round(h * aspect)
    png = await render_svg_png(svg, width=w, height=h, fg=WHITE, bg=None)
    return {"email_logo_url": _put_versioned("branding/email-wordmark-white.png", png, "image/png")}


async def derive_from_isologo(svg: str) -> dict[str, str]:
    """Del isologo deriva favicon + apple-touch + icon-512 (tile amber + isologo ink).

    Devuelve {setting_key: url}.
    """
    async def _icon(size: int) -> bytes:
        return await render_svg_png(
            svg, width=size, height=size, fg=INK, bg=AMBER, pad_pct=_ICON_PAD_PCT
        )

    return {
        "favicon_url": _put_versioned("branding/favicon.png", await _icon(128), "image/png"),
        "apple_touch_icon_url": _put_versioned(
            "branding/apple-touch-icon.png", await _icon(180), "image/png"
        ),
        "icon_512_url": _put_versioned("branding/icon-512.png", await _icon(512), "image/png"),
    }
