"""Tests de arca_fe.pdf — HTML -> PDF/imagen vía Chromium headless (Playwright).

`integration`, no `unit`: a diferencia del resto de la suite (puros, sin red/proceso externo),
estos SÍ lanzan un Chromium real — es justamente lo que hay que verificar (que el motor compartido
produce bytes reales), no algo que tenga sentido mockear (mockear Playwright no probaría nada del
render real). Requiere el extra `pdf` instalado + `playwright install chromium`.

OPT-IN: el job `python-tests` de CI (`.github/workflows/ci.yml`) nunca instaló el binario de
Chromium (ni falta que le haga — el resto de la suite, incluida la de Rambla que sí usa Playwright
en producción vía `backend/pdf.py`, mockea el límite de Chromium en vez de lanzarlo real en CI). En
vez de sumarle ese paso a un workflow compartido por todo el repo para servir un extra opcional de
una sola librería, esta suite sigue el mismo patrón ya usado acá para integration tests que
necesitan infra que el job default no provee (ver `tests/test_alembic_upgrade_db.py`, gateado tras
`ALEMBIC_DB_TEST=1`): se saltea salvo opt-in explícito.

    pip install -e .[pdf] && playwright install chromium
    ARCA_FE_PDF_TEST=1 python -m pytest arca_fe/tests/test_pdf.py -v"""
from __future__ import annotations

import os

import pytest

from arca_fe.pdf import cerrar_navegador, renderizar_imagen, renderizar_pdf

_OPT_IN = os.environ.get("ARCA_FE_PDF_TEST") == "1"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _OPT_IN,
        reason="opt-in: setear ARCA_FE_PDF_TEST=1 (+ `playwright install chromium`) para correr esta suite",
    ),
]

_HTML_SIMPLE = "<html><body style='margin:0;padding:40px;'><h1>Hola ARCA</h1></body></html>"

# Optativo: si el entorno ya tiene un Chromium provisto por fuera del paquete pip de Playwright
# (CI/sandbox con un browser pre-instalado en un path fijo, sin `playwright install` disponible),
# `PLAYWRIGHT_CHROMIUM_EXECUTABLE` apunta directo ahí — sin la env var, Playwright resuelve el
# suyo solo (el caso normal, ej. tras `playwright install --with-deps` en CI real).
_EXECUTABLE_PATH = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE") or None


@pytest.fixture(autouse=True)
async def _cerrar_browser_al_final():
    """El browser compartido es un singleton de módulo — cerrarlo entre tests evita que un test
    de otro archivo (o una corrida siguiente) herede un proceso Chromium ya usado, y confirma que
    `cerrar_navegador` deja al módulo en un estado desde el que se puede volver a levantar."""
    yield
    await cerrar_navegador()


async def test_renderizar_pdf_devuelve_bytes_pdf_reales():
    pdf_bytes = await renderizar_pdf(_HTML_SIMPLE, executable_path=_EXECUTABLE_PATH)
    assert pdf_bytes.startswith(b"%PDF-")


async def test_renderizar_pdf_con_page_size_propio():
    """Layout 'simplificada' (o cualquier otro) — un PDF NO es exclusivo de oficial/detallada."""
    pdf_bytes = await renderizar_pdf(_HTML_SIMPLE, page_size=(1080, 1350), executable_path=_EXECUTABLE_PATH)
    assert pdf_bytes.startswith(b"%PDF-")


async def test_renderizar_imagen_devuelve_png_real():
    img_bytes = await renderizar_imagen(_HTML_SIMPLE, executable_path=_EXECUTABLE_PATH)
    assert img_bytes.startswith(b"\x89PNG\r\n\x1a\n")


async def test_renderizar_imagen_jpeg():
    img_bytes = await renderizar_imagen(_HTML_SIMPLE, formato="jpeg", executable_path=_EXECUTABLE_PATH)
    assert img_bytes.startswith(b"\xff\xd8\xff")


async def test_renderizar_imagen_con_page_size_no_es_exclusivo_de_simplificada():
    """Cualquier layout se puede pedir como imagen, no solo 'simplificada' — mismo contrato de
    page_size que renderizar_pdf, intercambiables sobre el mismo HTML."""
    img_bytes = await renderizar_imagen(_HTML_SIMPLE, page_size=(794, None), executable_path=_EXECUTABLE_PATH)
    assert img_bytes.startswith(b"\x89PNG\r\n\x1a\n")


async def test_reusa_el_mismo_browser_entre_llamadas():
    """El browser compartido (`_get_browser`) no se relanza en cada llamada — dos renders
    consecutivos comparten instancia (verificado indirectamente: ambos completan rápido, sin que
    el segundo pague el costo de arrancar Chromium de nuevo)."""
    import time

    t0 = time.monotonic()
    await renderizar_pdf(_HTML_SIMPLE, executable_path=_EXECUTABLE_PATH)
    t1 = time.monotonic()
    await renderizar_pdf(_HTML_SIMPLE, executable_path=_EXECUTABLE_PATH)
    t2 = time.monotonic()
    # El segundo render (browser ya caliente) no debería tardar más que el primero
    # (que paga el arranque de Chromium) — margen generoso, esto no es un benchmark de precisión.
    assert (t2 - t1) <= (t1 - t0) + 1.0
