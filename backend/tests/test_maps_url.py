"""Tests del parser de Google Maps URL.

Cubre los 3 formatos que puede pegar el dueño:
- iframe HTML (caso "Compartir → Insertar mapa")
- URL larga (`google.com/maps/.../@lat,lng,zoom/...`)
- shortlink (`maps.app.goo.gl/...`) — resolución mockeada (no toca red real)

Además: rechazos por host no permitido (SSRF guard) y por input mal formado.
"""

import pytest

from services.maps_url import MapsParseError, parse_maps_input


def test_iframe_html_extrae_src():
    """El código que Google da en 'Compartir → Insertar mapa'."""
    html = (
        '<iframe src="https://www.google.com/maps/embed?pb=!1m18!1m12" '
        'width="600" height="450" style="border:0;" allowfullscreen="" '
        'loading="lazy"></iframe>'
    )
    result = parse_maps_input(html)
    assert result.embed_url == "https://www.google.com/maps/embed?pb=!1m18!1m12"
    assert result.raw_url == result.embed_url


def test_iframe_con_host_no_permitido_rechaza():
    html = '<iframe src="https://evil.com/maps/embed?pb=xx"></iframe>'
    with pytest.raises(MapsParseError, match="no permitido"):
        parse_maps_input(html)


def test_url_larga_con_coords_construye_embed():
    """URL larga con `@lat,lng,zoom` — extraemos coords y armamos embed OSM."""
    long_url = (
        "https://www.google.com/maps/place/Rambla+Rental/"
        "@-38.0011,-57.5500,17z/data=!3m1!4b1"
    )
    result = parse_maps_input(long_url)
    assert "openstreetmap.org" in result.embed_url
    assert "-38.0011" in result.embed_url
    assert "-57.55" in result.embed_url
    # raw_url queda el original (lo que pegó el dueño).
    assert result.raw_url == long_url


def test_url_sin_https_rechaza():
    with pytest.raises(MapsParseError, match="https://"):
        parse_maps_input("google.com/maps/place/x")


def test_host_no_google_rechaza():
    """SSRF guard — solo aceptamos hosts de Google."""
    with pytest.raises(MapsParseError, match="no permitido"):
        parse_maps_input("https://evil.com/redirect?to=http://internal-service")


def test_input_vacio_rechaza():
    with pytest.raises(MapsParseError, match="vac"):
        parse_maps_input("")
    with pytest.raises(MapsParseError):
        parse_maps_input("   ")


def test_shortlink_resuelve_con_mock(monkeypatch):
    """maps.app.goo.gl/xxx → seguimos redirects hasta URL larga de google.com.

    Mockeamos httpx.Client para no salir a la red real.
    """
    calls = {"i": 0}

    class FakeResp:
        def __init__(self, status, headers=None, url=""):
            self.status_code = status
            self.headers = headers or {}
            self.url = url

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            calls["i"] += 1
            if calls["i"] == 1:
                # primer salto: shortlink → google.com con coords
                return FakeResp(
                    302,
                    headers={
                        "location": "https://www.google.com/maps/place/X/@-38.5,-57.6,17z/"
                    },
                )
            # llegamos a destino — sin redirect
            return FakeResp(200, url=url)

    import services.maps_url as mod

    monkeypatch.setattr(mod.httpx, "Client", FakeClient)

    result = parse_maps_input("https://maps.app.goo.gl/abc123")
    assert "openstreetmap.org" in result.embed_url
    assert "-38.5" in result.embed_url
    assert "-57.6" in result.embed_url
    # El raw_url debe quedar el shortlink original (más corto, abre la app móvil).
    assert result.raw_url == "https://maps.app.goo.gl/abc123"


def test_shortlink_redirect_a_host_malo_rechaza(monkeypatch):
    """Si la cadena de redirects sale del allowlist, rechazamos."""

    class FakeResp:
        def __init__(self, status, headers=None):
            self.status_code = status
            self.headers = headers or {}
            self.url = ""

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            return FakeResp(302, headers={"location": "https://evil.com/leak"})

    import services.maps_url as mod

    monkeypatch.setattr(mod.httpx, "Client", FakeClient)

    with pytest.raises(MapsParseError, match="no permitido"):
        parse_maps_input("https://maps.app.goo.gl/xyz")
