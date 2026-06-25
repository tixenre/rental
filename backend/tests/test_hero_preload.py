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
- preload SIEMPRE webp (el <img> srcset que Lighthouse chequea para "discoverable").
  NO preloadeamos AVIF aunque esté disponible: un preload type="image/avif" no
  matchea el <img src=webp> que Chrome reporta como LCP → descarga doble + LCP peor.
  El preconnect pre-calienta la conexión R2 para que el AVIF descargue rápido cuando
  React renderiza el <picture>.
- preload con imagesrcset/imagesizes que matchea `srcSet="{sm} 800w, {url} 1600w"`
  + `sizes=(max-width: 768px) 100vw, 42vw` del carrusel cuando hay variante sm.
- fallback a href simple cuando no hay variante sm (legacy / sin backfill).
"""

import main


_HTML = "<html><head><title>x</title></head><body></body></html>"
_URL = "https://pub-abc123.r2.dev/estudio/1780399247332.webp"
_SM = "https://pub-abc123.r2.dev/media/estudio/12/display-sm.webp"
_AVIF = "https://pub-abc123.r2.dev/media/estudio/12/display.avif"
_SM_AVIF = "https://pub-abc123.r2.dev/media/estudio/12/display-sm.avif"


def _head(html: str) -> str:
    return html[html.index("<head>") + 6 : html.index("</head>")]


def test_preload_con_variante_sm_usa_imagesrcset_y_preconnect():
    head = _head(main._inject_hero_preload(_HTML, _URL, _SM))
    assert '<link rel="preconnect" href="https://pub-abc123.r2.dev">' in head
    assert f'imagesrcset="{_SM} 800w, {_URL} 1600w"' in head
    assert 'imagesizes="(max-width: 768px) 100vw, 42vw"' in head
    assert 'fetchpriority="high"' in head
    # Siempre webp — sin AVIF preload
    assert 'type="image/avif"' not in head


def test_preload_sin_variante_sm_cae_a_href_simple():
    head = _head(main._inject_hero_preload(_HTML, _URL, None))
    assert f'<link rel="preload" as="image" fetchpriority="high" href="{_URL}">' in head
    assert "imagesrcset" not in head
    assert '<link rel="preconnect" href="https://pub-abc123.r2.dev">' in head


def test_avif_disponible_igual_preloadea_webp():
    # Aunque haya variantes AVIF, preloadeamos webp (el <img> srcset que Chrome reporta
    # como LCP). Un preload type="image/avif" no matchea y causa doble descarga.
    head = _head(main._inject_hero_preload(_HTML, _URL, _SM, _AVIF, _SM_AVIF))
    # Preload webp (no avif)
    assert f'imagesrcset="{_SM} 800w, {_URL} 1600w"' in head
    assert 'type="image/avif"' not in head
    # Preconnect sigue presente (pre-calienta R2 para que AVIF descargue rápido después)
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
