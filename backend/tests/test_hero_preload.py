"""El helper `_inject_hero_preload` inyecta preconnect + preload del hero LCP.

Regresión del LCP mobile clavado en ~21s: el preload del hero tiene que apuntar
EXACTO a la imagen que renderiza el hero, si no el navegador no la descubre en el
HTML inicial ("LCP discoverable in initial document" falla) y el LCP se dispara.

El hero se renderiza con `<img src=avif>` DIRECTO (no `<picture>`), porque un
preload `type=image/avif` matchea de forma determinista solo contra un `<img>`
directo. Contrato fijado acá:
- preconnect al ORIGEN del bucket R2 (derivado de la URL, SIN crossorigin) —
  crossorigin genera "Unused preconnect" porque las imágenes no usan CORS.
- con AVIF: preload `type=image/avif` + `imagesrcset` de URLs .avif + `imagesizes=100vw`
  (matchea el `sizes=100vw` del `<img>` del hero; Lighthouse mide el LCP mobile).
- sin AVIF (NULL): preload webp (el front también cae a webp en ese caso).
- el orden de la query del hero espeja `useHeroPhotos` (es_principal DESC, orden ASC)
  → preload y `<img>` apuntan al mismo recurso, una sola descarga.
"""

import main


_HTML = "<html><head><title>x</title></head><body></body></html>"
_URL = "https://pub-abc123.r2.dev/estudio/1780399247332.webp"
_SM = "https://pub-abc123.r2.dev/media/estudio/12/display-sm.webp"
_AVIF = "https://pub-abc123.r2.dev/media/estudio/12/display.avif"
_SM_AVIF = "https://pub-abc123.r2.dev/media/estudio/12/display-sm.avif"


def _head(html: str) -> str:
    return html[html.index("<head>") + 6 : html.index("</head>")]


def test_con_avif_preloadea_avif_con_type_y_100vw():
    head = _head(main._inject_hero_preload(_HTML, _URL, _SM, _AVIF, _SM_AVIF))
    assert '<link rel="preconnect" href="https://pub-abc123.r2.dev">' in head
    # preload AVIF: type obligatorio + srcset de URLs .avif + imagesizes 100vw
    assert 'type="image/avif"' in head
    assert f'imagesrcset="{_SM_AVIF} 800w, {_AVIF} 1600w"' in head
    assert 'imagesizes="100vw"' in head
    assert 'fetchpriority="high"' in head
    # NO debe preloadear el webp (una sola descarga del LCP)
    assert _URL not in head
    assert _SM not in head


def test_avif_sin_sm_cae_a_href_simple_con_type():
    head = _head(main._inject_hero_preload(_HTML, _URL, _SM, _AVIF, None))
    assert 'type="image/avif"' in head
    assert f'href="{_AVIF}"' in head
    assert "imagesrcset" not in head


def test_sin_avif_preloadea_webp_con_100vw():
    head = _head(main._inject_hero_preload(_HTML, _URL, _SM))
    assert '<link rel="preconnect" href="https://pub-abc123.r2.dev">' in head
    assert f'imagesrcset="{_SM} 800w, {_URL} 1600w"' in head
    assert 'imagesizes="100vw"' in head
    assert 'fetchpriority="high"' in head
    # sin AVIF no hay type avif
    assert 'type="image/avif"' not in head


def test_sin_avif_ni_sm_cae_a_href_webp_simple():
    head = _head(main._inject_hero_preload(_HTML, _URL, None))
    assert f'<link rel="preload" as="image" fetchpriority="high" href="{_URL}">' in head
    assert "imagesrcset" not in head
    assert '<link rel="preconnect" href="https://pub-abc123.r2.dev">' in head


def test_origen_se_deriva_de_la_url_no_se_hardcodea():
    url = "https://cdn.rambla.house/estudio/foo.webp"
    sm = "https://cdn.rambla.house/media/estudio/1/display-sm.webp"
    head = _head(main._inject_hero_preload(_HTML, url, sm))
    assert '<link rel="preconnect" href="https://cdn.rambla.house">' in head


def test_inyecta_un_solo_preload_y_preconnect():
    out = main._inject_hero_preload(_HTML, _URL, _SM, _AVIF, _SM_AVIF)
    assert out.count("</head>") == 1
    assert out.count('rel="preload"') == 1
    assert out.count('rel="preconnect"') == 1
