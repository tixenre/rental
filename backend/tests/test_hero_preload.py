"""El helper `_inject_hero_preload` inyecta preconnect + preload del hero LCP.

Regresión del LCP mobile clavado en ~21s: el preload del hero tiene que apuntar
EXACTO a la imagen que renderiza el carrusel (misma foto + misma variante srcset),
si no el navegador no la descubre en el HTML inicial ("LCP discoverable in initial
document" falla) y el LCP se dispara. El orden de la query del hero en `root()` ya
espeja `useHeroPhotos` (es_principal DESC, orden ASC); acá fijamos el contrato del
tag inyectado:
- preconnect al ORIGEN del bucket R2 (derivado de la URL, sin hardcodear bucket),
- preload con imagesrcset/imagesizes que matchea `srcSet="{sm} 800w, {url} 1600w"`
  + `sizes=100vw` del carrusel cuando hay variante sm,
- fallback a href simple cuando no hay variante sm (legacy / sin backfill).
"""

import main


_HTML = "<html><head><title>x</title></head><body></body></html>"
_URL = "https://pub-abc123.r2.dev/estudio/1780399247332.webp"
_SM = "https://pub-abc123.r2.dev/media/estudio/12/display-sm.webp"


def _head(html: str) -> str:
    return html[html.index("<head>") + 6 : html.index("</head>")]


def test_preload_con_variante_sm_usa_imagesrcset_y_preconnect():
    head = _head(main._inject_hero_preload(_HTML, _URL, _SM))
    # preconnect al origen R2 (esquema://host), sin path ni bucket hardcodeado
    assert '<link rel="preconnect" href="https://pub-abc123.r2.dev" crossorigin>' in head
    # preload con el MISMO srcset + sizes que renderiza el carrusel
    assert f'imagesrcset="{_SM} 800w, {_URL} 1600w"' in head
    assert 'imagesizes="100vw"' in head
    assert 'fetchpriority="high"' in head


def test_preload_sin_variante_sm_cae_a_href_simple():
    head = _head(main._inject_hero_preload(_HTML, _URL, None))
    assert f'<link rel="preload" as="image" fetchpriority="high" href="{_URL}">' in head
    # sin variante sm no hay imagesrcset
    assert "imagesrcset" not in head
    # pero el preconnect al origen sigue
    assert '<link rel="preconnect" href="https://pub-abc123.r2.dev" crossorigin>' in head


def test_origen_se_deriva_de_la_url_no_se_hardcodea():
    # Otro host (dominio propio) → el preconnect debe seguir al origen correcto.
    url = "https://cdn.rambla.house/estudio/foo.webp"
    sm = "https://cdn.rambla.house/media/estudio/1/display-sm.webp"
    head = _head(main._inject_hero_preload(_HTML, url, sm))
    assert '<link rel="preconnect" href="https://cdn.rambla.house" crossorigin>' in head


def test_inyecta_una_sola_vez_antes_de_head_cierre():
    out = main._inject_hero_preload(_HTML, _URL, _SM)
    assert out.count("</head>") == 1
    assert out.count('rel="preload"') == 1
    assert out.count('rel="preconnect"') == 1
