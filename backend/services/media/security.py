"""Stack anti-SSRF del módulo media.

Movido VERBATIM de services/image_upload.py — único cambio mecánico:
    raise HTTPException(status, msg)  →  raise MediaError(status, msg)
Los códigos de estado y mensajes son idénticos al módulo legacy.
El código de seguridad es sagrado: se mueve, NO se reescribe.
"""
import logging

from .errors import MediaError

logger = logging.getLogger(__name__)


_ALLOWED_PHOTO_HOSTS = frozenset([
    # Retailers
    "bhphotovideo.com", "adorama.com", "amazon.com", "amazon.ca",
    "amazonaws.com",
    # Wikipedia / commons
    "wikimedia.org", "wikipedia.org",
    # Reviews / press
    "dpreview.com", "fstoppers.com", "petapixel.com", "cinema5d.com",
    # Manufacturer (cámaras, lentes, audio, video, iluminación, soportes)
    "sony.com", "sonycreativesoftware.com",
    "canon.com", "usa.canon.com", "canon-europe.com",
    "nikon.com", "nikonusa.com",
    "fujifilm.com", "fujifilm-x.com",
    "panasonic.com",
    "blackmagicdesign.com", "red.com", "atomos.com",
    "tilta.com", "smallrig.com", "manfrotto.com",
    "saramonic.com", "rode.com", "shure.com", "sennheiser.com",
    "sigmaphoto.com", "tamron.com", "samyangopticsamericas.com",
    "leofoto.com", "godox.com", "aputure.com", "nanlite.com",
    "zhiyun-tech.com", "dji.com", "insta360.com", "gopro.com",
    # CDNs comunes que sirven assets de los hosts de arriba
    "cloudfront.net", "akamaized.net", "akamaihd.net",
    "shopifycdn.com", "wp.com", "googleusercontent.com",
])


def _is_photo_host_allowed(host: str) -> bool:
    """True si `host` es un dominio del allowlist o subdominio de uno."""
    host = (host or "").lower().rstrip(".")
    return any(host == h or host.endswith("." + h) for h in _ALLOWED_PHOTO_HOSTS)


def _resolve_to_public_ip(host: str) -> str:
    """Resuelve `host` UNA vez y devuelve una IP pública para pinearla en la
    conexión (mata DNS rebinding). Eleva MediaError si no resuelve o si resuelve
    a algo interno."""
    import ipaddress as _ip
    import socket as _socket
    try:
        infos = _socket.getaddrinfo(host, None)
    except (_socket.gaierror, OSError):
        raise MediaError(403, f"No se pudo resolver el host '{host}'")
    public_ip: str | None = None
    for info in infos:
        addr = info[4][0]
        try:
            ip = _ip.ip_address(addr)
        except ValueError:
            continue
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
            raise MediaError(403, f"Host '{host}' resuelve a IP privada/interna")
        if public_ip is None:
            public_ip = addr
    if public_ip is None:
        raise MediaError(403, f"Host '{host}' no resolvió a ninguna IP válida")
    return public_ip


def _host_resolves_to_private(host: str) -> bool:
    """True si el host no resuelve o resuelve a alguna IP privada/interna."""
    try:
        _resolve_to_public_ip(host)
        return False
    except MediaError:
        return True


def _validate_ssrf_only(url: str) -> None:
    """Anti-SSRF sin whitelist de dominios. Para uploads manuales del admin."""
    from urllib.parse import urlparse as _urlparse
    if not url.lower().startswith(("http://", "https://")):
        raise MediaError(400, "URL inválida — sólo http/https")
    parsed = _urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        raise MediaError(400, "URL inválida — host vacío")
    port = parsed.port
    if port and port not in (80, 443):
        raise MediaError(400, f"Puerto no permitido: {port}")
    if _host_resolves_to_private(host):
        raise MediaError(403, f"Host '{host}' resuelve a IP privada/interna")


def _validate_image_url_static(url: str) -> None:
    """Checks estáticos anti-SSRF (scheme + host + puerto + allowlist), SIN
    resolver DNS."""
    from urllib.parse import urlparse as _urlparse
    if not url.lower().startswith(("http://", "https://")):
        raise MediaError(400, "URL inválida — sólo http/https")
    parsed = _urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        raise MediaError(400, "URL inválida — host vacío")
    port = parsed.port
    if port and port not in (80, 443):
        raise MediaError(400, f"Puerto no permitido: {port}")
    if not _is_photo_host_allowed(host):
        raise MediaError(
            403,
            f"Host no permitido para descarga: {host}. Si es un sitio "
            "legítimo, agregar a _ALLOWED_PHOTO_HOSTS.",
        )


def _validate_external_image_url(url: str) -> None:
    """Anti-SSRF con whitelist de dominios (checks estáticos + resolución DNS)."""
    _validate_image_url_static(url)
    from urllib.parse import urlparse as _urlparse
    host = (_urlparse(url).hostname or "").lower()
    if _host_resolves_to_private(host):
        raise MediaError(403, f"Host '{host}' resuelve a IP privada/interna")


_MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20 MB


def _http_get_pinned(
    url: str, pinned_ip: str, headers: dict, timeout: float = 20.0,
) -> tuple[int, dict, bytes]:
    """GET de bajo nivel con la IP pineada. NO sigue redirects.
    Devuelve (status, headers_lower, body). Eleva MediaError(502) en error de red.
    """
    import http.client
    import socket
    import ssl
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.hostname or ""
    is_https = parsed.scheme == "https"
    port = parsed.port or (443 if is_https else 80)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    sock = None
    try:
        sock = socket.create_connection((pinned_ip, port), timeout=timeout)
        if is_https:
            ctx = ssl.create_default_context()
            sock = ctx.wrap_socket(sock, server_hostname=host)
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.sock = sock
        req_headers = dict(headers)
        req_headers["Accept-Encoding"] = "identity"
        req_headers.setdefault("Host", host)
        conn.request("GET", path, headers=req_headers)
        resp = conn.getresponse()
        body = resp.read(_MAX_IMAGE_BYTES + 1)
        if len(body) > _MAX_IMAGE_BYTES:
            raise MediaError(413, "La imagen supera el tamaño máximo permitido")
        resp_headers = {k.lower(): v for k, v in resp.getheaders()}
        return resp.status, resp_headers, body
    except (OSError, ssl.SSLError, http.client.HTTPException):
        raise MediaError(502, "No se pudo descargar la imagen")
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def _download_with_redirects(
    url: str, headers: dict, max_redirects: int = 3,
) -> tuple[int, dict, bytes]:
    """Descarga siguiendo hasta `max_redirects` saltos, RE-VALIDANDO cada salto."""
    from urllib.parse import urlparse, urljoin

    current = url
    for _ in range(max_redirects + 1):
        _validate_image_url_static(current)
        host = (urlparse(current).hostname or "").lower()
        pinned_ip = _resolve_to_public_ip(host)
        status, resp_headers, body = _http_get_pinned(current, pinned_ip, headers)
        if status in (301, 302, 303, 307, 308):
            location = resp_headers.get("location")
            if not location:
                raise MediaError(502, "Redirect sin destino")
            current = urljoin(current, location)
            continue
        return status, resp_headers, body
    raise MediaError(502, "Demasiados redirects")


def _download_image_bytes(url: str) -> tuple[bytes, str]:
    """Descarga una imagen externa con DNS pineado + redirects re-validados.
    Devuelve (bytes, content_type). Eleva MediaError si no se pudo.
    """
    from urllib.parse import urlparse

    _validate_external_image_url(url)
    host = (urlparse(url).hostname or "").lower()

    def _headers(referer: str | None) -> dict:
        h = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
            "Sec-Fetch-Dest": "image",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "cross-site",
            "Cache-Control": "no-cache",
        }
        if referer:
            h["Referer"] = referer
        return h

    referer_map = {
        "bhphotovideo.com": "https://www.bhphotovideo.com/",
        "www.bhphotovideo.com": "https://www.bhphotovideo.com/",
        "adorama.com": "https://www.adorama.com/",
        "www.adorama.com": "https://www.adorama.com/",
    }
    primary_referer = next(
        (v for k, v in referer_map.items() if host.endswith(k)),
        f"https://{host}/",
    )

    last_status = None
    for referer in (primary_referer, None, "https://www.google.com/"):
        status, resp_headers, body = _download_with_redirects(url, _headers(referer))
        last_status = status
        if status == 200:
            ctype = resp_headers.get("content-type", "image/jpeg")
            if not ctype.lower().startswith("image/"):
                raise MediaError(415, f"La URL no devolvió una imagen ({ctype})")
            if len(body) < 1024:
                raise MediaError(415, f"Imagen muy chica ({len(body)} bytes)")
            return body, ctype
        if status != 403:
            break

    # httpx fallback: algunos CDNs (B&H, Adorama) bloquean el cliente HTTP
    # de bajo nivel por TLS fingerprint pero aceptan httpx. Seguro: la URL
    # ya pasó _validate_external_image_url (allowlist + IP check) arriba.
    # follow_redirects=False para no seguir redirects no validados.
    if last_status == 403:
        try:
            import httpx as _httpx
            r = _httpx.get(
                url,
                headers=_headers(primary_referer),
                follow_redirects=False,
                timeout=20.0,
            )
            if r.status_code == 200:
                ctype = r.headers.get("content-type", "image/jpeg")
                if ctype.lower().startswith("image/") and len(r.content) >= 1024:
                    return r.content, ctype
        except Exception:
            pass

    raise MediaError(502, f"No se pudo descargar la imagen (error {last_status})")
