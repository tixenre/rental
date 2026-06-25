"""El helper `_inject_hero_preload` inyecta preconnect + preload del hero LCP.

Regresión del LCP mobile clavado en ~21s: el preload del hero tiene que apuntar
EXACTO a la imagen que renderiza el carrusel (misma foto + misma variante srcset),
si no el navegador no la descubre en el HTML inicial ("LCP discoverable in initial
document" falla) y el LCP se dispara. El orden de la query del hero en `root()` ya
espeja `useHeroPhotos` (es_principal DESC, orden ASC); acá fijamos el contrato del
tag inyectado:
- preconnect al ORIGEN del bucket R2 (derivado de la URL, SIN crossorigin),
  porque las imágenes no usan CORS — crossorigin genera "Unused preconnect" en
  PageSpeed y desperdicia la conexión (310ms de ahorro al quitarlo).
- cuando hay AVIF: preload type="image/avif" con imagesrcset/imagesizes —
  browsers que soportan AVIF usan el preload; los demás lo ignoran y descubren
  el webp desde el <picture> element normalmente.
- sin AVIF, con sm: preload webp con imagesrcset/imagesizes.
- fallback a href simple cuando no hay variante sm ni avif (legacy).
"""

import main


_HTML = "<html><head><title>x</title></head><body></body></html>"
_URL = "https://pub-abc123.r2.dev/estudio/1780399247332.webp"
_SM = "https://pub-abc123.r2.dev/media/estudio/12/display-sm.webp"
_AVIF = "https://pub-abc123.r2.dev/media/estudio/12/display.avif"
_SM_AVIF = "https://pub-abc123.r2.dev/media/estudio/12/display-sm.avif"


def _head(html: str) -> str:
    return html[html.index("<head>") + 6 : html.index("</head>")]


def test_preload_avif_cuando_hay_variante_avif():
    head = _head(main._inject_hero_preload(_HTML, _URL, _SM, _AVIF, _SM_AVIF))
    # preconnect sigue presente
    assert '<link rel="preconnect" href="https://pub-abc123.r2.dev">' in head
    # preload AVIF con type="image/avif" y el srcset correcto
    assert 'type="image/avif"' in head
    assert f'imagesrcset="{_SM_AVIF} 800w, {_AVIF} 1600w"' in head
    assert 'imagesizes="(max-width: 768px) 100vw, 42vw"' in head
    assert 'fetchpriority="high"' in head
    # NO preloadea el webp cuando hay AVIF (no generar dos preloads)
    assert _URL not in head.replace(_AVIF, "")


def test_preload_avif_sin_sm_avif_usa_href_simple():
    head = _head(main._inject_hero_preload(_HTML, _URL, _SM, _AVIF, None))
    assert 'type="image/avif"' in head
    assert f'href="{_AVIF}"' in head
    assert "imagesrcset" not in head


def test_preload_con_variante_sm_usa_imagesrcset_y_preconnect():
    # Sin AVIF — comportamiento webp original
    head = _head(main._inject_hero_preload(_HTML, _URL, _SM))
    assert '<link rel="preconnect" href="https://pub-abc123.r2.dev">' in head
    assert f'imagesrcset="{_SM} 800w, {_URL} 1600w"' in head
    assert 'imagesizes="(max-width: 768px) 100vw, 42vw"' in head
    assert 'fetchpriority="high"' in head
    assert 'type="image/avif"' not in head


def test_preload_sin_variante_sm_cae_a_href_simple():
    head = _head(main._inject_hero_preload(_HTML, _URL, None))
    assert f'<link rel="preload" as="image" fetchpriority="high" href="{_URL}">' in head
    assert "imagesrcset" not in head
    assert '<link rel="preconnect" href="https://pub-abc123.r2.dev">' in head


def test_origen_se_deriva_de_la_url_no_se_hardcodea():
    url = "https://cdn.rambla.house/estudio/foo.webp"
    sm = "https://cdn.rambla.house/media/estudio/1/display-sm.webp"
    head = _head(main._inject_hero_preload(_HTML, url, sm))
    assert '<link rel="preconnect" href="https://cdn.rambla.house">' in head


def test_inyecta_una_sola_vez_antes_de_head_cierre():
    out = main._inject_hero_preload(_HTML, _URL, _SM, _AVIF, _SM_AVIF)
    assert out.count("</head>") == 1
    assert out.count('rel="preload"') == 1
    assert out.count('rel="preconnect"') == 1
