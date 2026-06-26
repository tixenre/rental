"""Parsea y normaliza un link de Google Maps a una URL embebible.

El dueño puede pegar en el admin tres formatos distintos:

1. **iframe HTML** — el código que da Google en "Compartir → Insertar mapa":
   `<iframe src="https://www.google.com/maps/embed?pb=..." ...></iframe>`
   → extraemos el `src` y lo usamos como embed URL.

2. **Shortlink** — `https://maps.app.goo.gl/xxxxx` (lo que da el botón compartir
   en la app móvil). Lo resolvemos siguiendo los redirects hasta la URL final
   de Google Maps; de ahí sacamos las coordenadas para armar el embed.

3. **URL larga** — `https://www.google.com/maps/place/.../@-38.0,-57.5,17z/...`
   directamente. Extraemos coords o pasamos a embed con `output=embed`.

Salida:
- `embed_url`: URL que va dentro de `<iframe src="...">` en la página pública.
- (`mapa_url` original lo guarda el caller, para el botón "Ver en Google Maps".)

Seguridad: solo seguimos redirects a hosts en allowlist de Google. Timeout corto.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import httpx

# Hosts permitidos en la cadena de redirects + URL final.
_ALLOWED_HOSTS = {
    "maps.app.goo.gl",
    "goo.gl",
    "share.google",
    "consent.google.com",
    "consent.youtube.com",  # raros pero pueden aparecer
    "google.com",
    "www.google.com",
    "maps.google.com",
    "www.google.com.ar",
    "google.com.ar",
}

# Hosts cuyo iframe src aceptamos (subset estricto: solo google.com).
_ALLOWED_EMBED_HOSTS = {
    "google.com",
    "www.google.com",
    "maps.google.com",
}

_IFRAME_SRC_RE = re.compile(r'<iframe[^>]*\bsrc=["\']([^"\']+)["\']', re.IGNORECASE)
# Coords con `@lat,lng` (URL larga típica de Google Maps).
_COORDS_AT_RE = re.compile(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)(?:,(\d+(?:\.\d+)?)z)?")
# Coords en query `q=lat,lng` o `ll=lat,lng`.
_COORDS_Q_RE = re.compile(r"[?&](?:q|ll)=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)")


class MapsParseError(ValueError):
    """El input no se pudo interpretar como mapa válido."""


@dataclass(frozen=True)
class ParsedMaps:
    embed_url: str  # va al iframe
    raw_url: str    # link "Ver en Google Maps" — preferimos el original del dueño


def _host_of(url: str) -> str:
    try:
        # urlparse es overkill; basta con cortar por '/' después del esquema.
        m = re.match(r"^https?://([^/?#]+)", url, re.IGNORECASE)
        host = (m.group(1) if m else "").lower()
        return host.removeprefix("www.")
    except Exception:
        return ""


def _is_allowed_host(url: str, allowed: set[str]) -> bool:
    host = _host_of(url)
    # Aceptamos host exacto o variantes con "www." removida.
    return host in allowed or any(host.endswith("." + h) for h in allowed)


def _coords_from_url(url: str) -> Optional[tuple[float, float]]:
    m = _COORDS_AT_RE.search(url)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = _COORDS_Q_RE.search(url)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None


def _embed_from_long_url(long_url: str) -> str:
    """Convierte una URL larga de google.com/maps a una URL embebible via OpenStreetMap.

    El formato legacy `output=embed` de Google ya no funciona sin API key.
    Cuando la URL tiene coords extraemos bbox y marker para OSM.
    Sin coords levantamos error: el admin debe pegar el código iframe directamente.
    """
    coords = _coords_from_url(long_url)
    if coords:
        lat, lng = coords
        margin = 0.006  # ~600 m de margen alrededor del punto
        bbox = f"{lng - margin},{lat - margin},{lng + margin},{lat + margin}"
        return f"https://www.openstreetmap.org/export/embed.html?bbox={bbox}&layer=mapnik&marker={lat},{lng}"
    raise MapsParseError(
        "no pude extraer coordenadas del link. "
        "Usá 'Compartir → Insertar mapa' en Google Maps y pegá el código <iframe> completo."
    )


def _resolve_shortlink(url: str, *, max_redirects: int = 5, timeout: float = 4.0) -> str:
    """Sigue los redirects de un shortlink hasta llegar a la URL final.

    Restringido a hosts de Google (SSRF-safe). Si se sale del allowlist o
    excede `max_redirects`, levanta MapsParseError.
    """
    current = url
    for _ in range(max_redirects):
        if not _is_allowed_host(current, _ALLOWED_HOSTS):
            raise MapsParseError(f"host no permitido en la cadena de redirects: {_host_of(current)}")
        try:
            # follow_redirects=False para inspeccionar cada salto.
            with httpx.Client(follow_redirects=False, timeout=timeout) as client:
                resp = client.get(current)
        except httpx.HTTPError as e:
            raise MapsParseError(f"no se pudo resolver el link: {e}") from e
        if resp.status_code in (301, 302, 303, 307, 308):
            loc = resp.headers.get("location")
            if not loc:
                raise MapsParseError("redirect sin Location")
            # Algunos servers devuelven URL relativa — esto no debería pasar con
            # Google pero por las dudas:
            if loc.startswith("/"):
                host = _host_of(current)
                loc = f"https://{host}{loc}"
            current = loc
            continue
        # No es redirect: terminamos.
        return str(resp.url)
    raise MapsParseError("demasiados redirects")


def parse_maps_input(raw: str) -> ParsedMaps:
    """Recibe lo que pegó el dueño y devuelve embed_url + raw_url.

    Levanta MapsParseError si no se puede interpretar. El caller decide qué
    hacer (devolver 400 al cliente, o aceptar sin embed).
    """
    s = (raw or "").strip()
    if not s:
        raise MapsParseError("link vacío")

    # 1. Si pegó un iframe HTML, extraemos el src.
    if "<iframe" in s.lower():
        m = _IFRAME_SRC_RE.search(s)
        if not m:
            raise MapsParseError("no encontré el src en el código iframe")
        src = m.group(1).strip()
        if not _is_allowed_host(src, _ALLOWED_EMBED_HOSTS):
            raise MapsParseError(f"el iframe apunta a un host no permitido: {_host_of(src)}")
        return ParsedMaps(embed_url=src, raw_url=src)

    # 2. Si pegó una URL: validar host y resolver shortlinks.
    if not (s.startswith("http://") or s.startswith("https://")):
        raise MapsParseError("tiene que arrancar con https://")
    if not _is_allowed_host(s, _ALLOWED_HOSTS):
        raise MapsParseError(f"host no permitido: {_host_of(s)}")

    final_url = s
    host = _host_of(s)
    if host in {"maps.app.goo.gl", "goo.gl", "share.google"} or host.endswith(".goo.gl"):
        final_url = _resolve_shortlink(s)
        if not _is_allowed_host(final_url, _ALLOWED_HOSTS):
            raise MapsParseError(f"el link resuelve a un host no permitido: {_host_of(final_url)}")

    embed = _embed_from_long_url(final_url)
    # Para el botón "Ver en Google Maps" preferimos el link original del dueño
    # (más corto, abre la app móvil). El resuelto se reserva para el iframe.
    return ParsedMaps(embed_url=embed, raw_url=s)
