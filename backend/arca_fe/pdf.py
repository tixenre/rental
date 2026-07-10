"""arca_fe.pdf — convierte el HTML de un comprobante (`arca_fe.render.renderizar_comprobante_html`)
a PDF o imagen, vía Chromium headless (Playwright). Requiere el extra `pdf`
(`pip install arca-fe[pdf]`, agrega `playwright` — el import es LAZY, no hace falta si tu
integración solo necesita el HTML).

Por qué esto vive en `arca_fe` y no queda como responsabilidad de cada consumidor: dos
consumidores reales convirtiendo el MISMO HTML con motores/versiones de Chromium distintas podían
producir PDFs sutilmente distintos (kerning, saltos de página) — mismo criterio de "cero drift"
que ya motivó el tema tipográfico compartido de `render.py`. Con un solo motor acá, cualquier
consumidor obtiene exactamente el mismo resultado.

API async-nativa (a diferencia del resto de `arca_fe`, que es sync-first con `asyncio_support`
como fachada opcional): Playwright se usa mejor vía su API async en un proceso de server de larga
vida — reusa un único Chromium compartido entre requests en vez de levantar uno por llamada. Un
wrapper sync (`asyncio.to_thread`) escondería ese costo real, no lo evitaría.

`renderizar_pdf`/`renderizar_imagen` son intercambiables sobre el MISMO `html` — no hay ningún
layout reservado para un formato en particular. Un consumidor le puede ofrecer al usuario PDF y
PNG/JPEG para los 3 layouts de `render.py` (oficial/detallada/simplificada) por igual; qué formato
mostrar es una decisión de UI de cada consumidor, no una restricción de esta librería.
"""
from __future__ import annotations

import asyncio

_playwright = None
_browser = None
_browser_lock = asyncio.Lock()


async def _get_browser(executable_path: str | None = None):
    global _playwright, _browser
    async with _browser_lock:
        if _browser is None or not _browser.is_connected():
            from playwright.async_api import async_playwright

            _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(
                headless=True, args=["--no-sandbox"], executable_path=executable_path
            )
    return _browser


async def cerrar_navegador() -> None:
    """Cierra el browser compartido — para tests o un shutdown prolijo del proceso. Sin llamar
    esto, el proceso de Chromium queda vivo hasta que el proceso Python termina (no es un leak con
    el propio proceso vivo, pero un test suite que lo instancia muchas veces sí lo nota)."""
    global _playwright, _browser
    async with _browser_lock:
        if _browser is not None:
            await _browser.close()
            _browser = None
        if _playwright is not None:
            await _playwright.stop()
            _playwright = None


async def renderizar_pdf(
    html: str,
    *,
    page_size: tuple[int, int | None] | None = None,
    executable_path: str | None = None,
) -> bytes:
    """Convierte `html` (típicamente el que devuelve `renderizar_comprobante_html`) a bytes de
    PDF. Reusa un único browser compartido entre llamadas — más rápido que levantar Chromium por
    request.

    `page_size`: `None` (default) → A4, para los layouts `'oficial'`/`'detallada'`.
    `(width_px, height_px)` fuerza un tamaño propio — usar
    `arca_fe.render.tamano_pagina_layout(layout)` para resolver el valor correcto según el layout
    (`(1080, 1350)` para `'simplificada'`, `None` para los otros dos). `height_px=None` dentro de
    la tupla mide el alto real del contenido (`document.body.scrollHeight`), para que la página no
    corte el comprobante ni le deje espacio en blanco de más.

    `executable_path`: solo hace falta en despliegues con un Chromium ya provisto por fuera del
    paquete pip de Playwright (serverless con un binario propio, un browser pre-instalado en un
    path fijo) — normalmente ni se pasa, Playwright resuelve el suyo solo. Solo aplica al PRIMER
    llamado que levanta el browser compartido; llamadas posteriores lo ignoran (reusan la
    instancia ya viva) — pensado para un valor fijo por proceso, no variable por request."""
    browser = await _get_browser(executable_path)
    page = await browser.new_page()
    try:
        await page.set_content(html, wait_until="networkidle")
        margin = {"top": "0", "bottom": "0", "left": "0", "right": "0"}
        if page_size:
            width_px, height_px = page_size
            if height_px is None:
                height_px = await page.evaluate("document.body.scrollHeight")
            return await page.pdf(
                width=f"{width_px}px",
                height=f"{height_px}px",
                margin=margin,
                print_background=True,
            )
        return await page.pdf(format="A4", margin=margin, print_background=True)
    finally:
        await page.close()


async def renderizar_imagen(
    html: str,
    *,
    page_size: tuple[int, int | None] | None = None,
    formato: str = "png",
    executable_path: str | None = None,
) -> bytes:
    """Screenshot de `html` — para compartir un comprobante como imagen en vez de PDF (el caso
    más común: la `'simplificada'`, pensada para WhatsApp — una imagen se ve inline en el chat, un
    PDF aparece como ícono de archivo genérico). Funciona con CUALQUIER layout, no solo
    `'simplificada'` — un consumidor puede ofrecerle al usuario PDF y PNG/JPEG para los 3 layouts
    por igual (`renderizar_pdf`/`renderizar_imagen` son intercambiables sobre el mismo `html`; la
    decisión de qué formato ofrecer es 100% del consumidor, no una restricción de la librería).
    Mismo contrato de `page_size`/`executable_path` que `renderizar_pdf`; sin especificar
    `page_size`, usa 794px de ancho (A4) con el alto real del contenido. `formato`: `"png"`
    (default, sin pérdida) o `"jpeg"`."""
    browser = await _get_browser(executable_path)
    page = await browser.new_page()
    try:
        await page.set_content(html, wait_until="networkidle")
        if page_size:
            width_px, height_px = page_size
            if height_px is None:
                height_px = await page.evaluate("document.body.scrollHeight")
        else:
            width_px = 794
            height_px = await page.evaluate("document.body.scrollHeight") or 1123
        await page.set_viewport_size({"width": width_px, "height": height_px})
        return await page.screenshot(type=formato)
    finally:
        await page.close()
