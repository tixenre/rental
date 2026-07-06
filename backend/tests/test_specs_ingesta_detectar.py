"""Candado de regresión de `detect_categoria` (queries/detectar.py) — los 5
casos reales que F5 (#1176) arregló a mano contra el dataset de 277 HTMLs de
B&H/eBay (`/Users/tincho/Desktop/Paginas`, gitignored). Sin este test, un
cambio futuro al regex de detección podía reintroducir cualquiera de estos 5
sin que nada lo cazara — hasta ahora `detect_categoria` no tenía NINGÚN test
directo (solo se ejercitaba indirectamente vía `extract_from_html`)."""

import pytest

pytestmark = pytest.mark.unit

from services.specs_ingesta.queries.detectar import detect_categoria


@pytest.mark.parametrize(
    "titulo,esperada",
    [
        # RED KOMODO: "cinema"+"camera" en cualquier posición del título (no
        # exige adyacencia) — antes caía a Desconocido → genérico, 70 specs
        # de ruido de los accesorios del bundle.
        ("RED DIGITAL CINEMA KOMODO 6K Camera Production Pack", "Cámaras"),
        # "dome" es un modificador de difusión, no una cámara ni luz.
        ("Aputure Quick Dome 60/90", "Modificadores"),
        # Lente PARA una luz (le da forma al haz), no un lente fotográfico —
        # el título dice "lens" pero "fresnel lens" desambigua a Modificadores.
        ("Nanlite Fresnel Lens for Forza 300 and 500", "Modificadores"),
        # Co-ocurrencia spotlight+lens → Modificadores, no Lentes (mismo
        # motivo: accesorio óptico de luz, título ambiguo con "lens").
        ("amaran Spotlight SE 36° Lens Kit", "Modificadores"),
        # "mount adapter" a secas (sin "lens" antes) → Adaptadores. Antes
        # caía a Desconocido → genérico sin hint, que resolvía aliases
        # CONTRA TODAS las categorías (matcheaba modificador_subtipo).
        ("Canon Mount Adapter EF-EOS R 0.71x", "Adaptadores"),
    ],
)
def test_detect_categoria_casos_reales_f5(titulo, esperada):
    assert detect_categoria("", titulo) == esperada


def test_detect_categoria_lente_fotografico_normal_no_regresiona():
    """Control: un lente fotográfico común sigue yendo a Lentes — la
    reordenación que prioriza Modificadores (fresnel/spotlight+lens) antes
    que Lentes no debe capturar el caso general."""
    assert detect_categoria("", "Canon RF 50mm f/1.2L USM Lens") == "Lentes"


def test_detect_categoria_desconocido_sin_señales():
    assert detect_categoria("", "Some Random Accessory Kit") == "Desconocido"
