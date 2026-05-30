"""Procesamiento y upload de imágenes — descarga segura (anti-SSRF), optimización
(PIL) y subida a Cloudflare R2 / Supabase Storage.

Extraído verbatim de `routes/equipos.py` (issue #501, Fase 3): era ~480 líneas
mezcladas con el CRUD de equipos, y ya lo importaban cross-módulo `routes/marcas`,
`routes/estudio` y `routes/settings` (señal de que debía ser un módulo común).

Incluye la validación anti-SSRF completa (allowlist de hosts, DNS pinning contra
rebinding, rechazo de IPs privadas) usada por la descarga de imágenes externas.

NOTA: las funciones lanzan `fastapi.HTTPException` directamente (igual que en su
hogar original) — el acople a FastAPI se preserva para que el move sea verbatim,
sin cambio de conducta. `_foto_path` NO se movió (depende de `get_db` para el
nombre del equipo): vive en `routes/equipos.py`.
"""
import logging

from fastapi import HTTPException

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
    conexión (mata DNS rebinding: validación y request usan la MISMA IP).

    Valida que TODAS las IPs resueltas sean públicas — si alguna es
    privada/loopback/link-local/multicast/reserved, rechaza (un host del
    allowlist podría apuntar a IPs internas). Eleva HTTPException si no resuelve
    o si resuelve a algo interno.
    """
    import ipaddress as _ip
    import socket as _socket
    try:
        infos = _socket.getaddrinfo(host, None)
    except (_socket.gaierror, OSError):
        raise HTTPException(403, f"No se pudo resolver el host '{host}'")
    public_ip: str | None = None
    for info in infos:
        addr = info[4][0]
        try:
            ip = _ip.ip_address(addr)
        except ValueError:
            continue
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
            raise HTTPException(403, f"Host '{host}' resuelve a IP privada/interna")
        if public_ip is None:
            public_ip = addr
    if public_ip is None:
        raise HTTPException(403, f"Host '{host}' no resolvió a ninguna IP válida")
    return public_ip


def _host_resolves_to_private(host: str) -> bool:
    """True si el host no resuelve o resuelve a alguna IP privada/interna.
    Wrapper booleano sobre `_resolve_to_public_ip` (fuente única de la lógica).
    """
    try:
        _resolve_to_public_ip(host)
        return False
    except HTTPException:
        return True


def _validate_ssrf_only(url: str) -> None:
    """Anti-SSRF sin whitelist de dominios. Usado cuando el admin selecciona
    manualmente una URL (no batch import). Protege contra IPs privadas/loopback
    pero no restringe el dominio."""
    from urllib.parse import urlparse as _urlparse
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "URL inválida — sólo http/https")
    parsed = _urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        raise HTTPException(400, "URL inválida — host vacío")
    port = parsed.port
    if port and port not in (80, 443):
        raise HTTPException(400, f"Puerto no permitido: {port}")
    if _host_resolves_to_private(host):
        raise HTTPException(403, f"Host '{host}' resuelve a IP privada/interna")


def _validate_image_url_static(url: str) -> None:
    """Checks estáticos anti-SSRF (scheme + host + puerto + allowlist), SIN
    resolver DNS. Separado de la resolución para que el path de descarga
    resuelva una sola vez y pinee esa IP (ver `_download_with_redirects`)."""
    from urllib.parse import urlparse as _urlparse
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "URL inválida — sólo http/https")
    parsed = _urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        raise HTTPException(400, "URL inválida — host vacío")
    port = parsed.port
    if port and port not in (80, 443):
        raise HTTPException(400, f"Puerto no permitido: {port}")
    if not _is_photo_host_allowed(host):
        raise HTTPException(
            403,
            f"Host no permitido para descarga: {host}. Si es un sitio "
            "legítimo, agregar a _ALLOWED_PHOTO_HOSTS.",
        )


def _validate_external_image_url(url: str) -> None:
    """Anti-SSRF con whitelist de dominios (checks estáticos + resolución DNS).
    Eleva HTTPException si la URL no es segura. Para el path de descarga real
    usar `_download_with_redirects`, que pinea la IP resuelta."""
    _validate_image_url_static(url)
    from urllib.parse import urlparse as _urlparse
    host = (_urlparse(url).hostname or "").lower()
    if _host_resolves_to_private(host):
        raise HTTPException(403, f"Host '{host}' resuelve a IP privada/interna")


# Tope de tamaño de descarga: una imagen de equipo nunca pesa esto. Evita que un
# host del allowlist comprometido agote la memoria del server con un body gigante.
_MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20 MB


def _http_get_pinned(
    url: str, pinned_ip: str, headers: dict, timeout: float = 20.0,
) -> tuple[int, dict, bytes]:
    """GET de bajo nivel con la IP pineada: el TCP va a `pinned_ip`, pero el TLS
    usa el hostname original como SNI (cert válido). NO sigue redirects.
    Devuelve (status, headers_lower, body). Eleva HTTPException(502) en error de red.

    Pinear la IP mata el DNS rebinding: la IP que se validó es exactamente la que
    se conecta (no hay segunda resolución entre validar y conectar).
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
            sock = ctx.wrap_socket(sock, server_hostname=host)  # SNI = hostname real
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.sock = sock  # socket ya conectado (y con TLS) → no re-resuelve DNS
        req_headers = dict(headers)
        # http.client no descomprime; pedimos identity para leer el body crudo.
        req_headers["Accept-Encoding"] = "identity"
        req_headers.setdefault("Host", host)
        conn.request("GET", path, headers=req_headers)
        resp = conn.getresponse()
        # Leemos hasta el tope + 1 para detectar overflow sin tragarnos todo.
        body = resp.read(_MAX_IMAGE_BYTES + 1)
        if len(body) > _MAX_IMAGE_BYTES:
            raise HTTPException(413, "La imagen supera el tamaño máximo permitido")
        resp_headers = {k.lower(): v for k, v in resp.getheaders()}
        return resp.status, resp_headers, body
    except (OSError, ssl.SSLError, http.client.HTTPException):
        raise HTTPException(502, "No se pudo descargar la imagen")
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def _download_with_redirects(
    url: str, headers: dict, max_redirects: int = 3,
) -> tuple[int, dict, bytes]:
    """Descarga siguiendo hasta `max_redirects` saltos, RE-VALIDANDO cada salto
    contra el guard (allowlist + IP pública) y pineando el DNS en cada uno.
    Así un 302 → http://169.254.169.254/... o a la red interna queda bloqueado.
    Devuelve (status, headers, body) del primer response no-redirect.
    """
    from urllib.parse import urlparse, urljoin

    current = url
    for _ in range(max_redirects + 1):
        _validate_image_url_static(current)               # scheme + allowlist + puerto
        host = (urlparse(current).hostname or "").lower()
        pinned_ip = _resolve_to_public_ip(host)            # resuelve UNA vez → IP pineada
        status, resp_headers, body = _http_get_pinned(current, pinned_ip, headers)
        if status in (301, 302, 303, 307, 308):
            location = resp_headers.get("location")
            if not location:
                raise HTTPException(502, "Redirect sin destino")
            current = urljoin(current, location)           # resolver Location relativo
            continue
        return status, resp_headers, body
    raise HTTPException(502, "Demasiados redirects")


def _download_image_bytes(url: str) -> tuple[bytes, str]:
    """Descarga una imagen externa con DNS pineado + redirects re-validados.
    Reintenta con distintos Referer si el origen responde 403 (anti-hotlink).
    Devuelve (bytes, content_type). Eleva HTTPException si no se pudo.

    Seguridad: TCP a la IP resuelta y validada (pin), TLS con SNI al hostname,
    cada redirect re-validado contra el allowlist. Sin proxies de terceros.
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

    # Reintentos de Referer ante 403 (hotlink protection). Los redirects y el
    # pin de DNS los maneja `_download_with_redirects`. Un 403 del guard (IP
    # privada / host no permitido) se eleva como excepción y corta el loop.
    last_status = None
    for referer in (primary_referer, None, "https://www.google.com/"):
        status, resp_headers, body = _download_with_redirects(url, _headers(referer))
        last_status = status
        if status == 200:
            ctype = resp_headers.get("content-type", "image/jpeg")
            if not ctype.lower().startswith("image/"):
                raise HTTPException(415, f"La URL no devolvió una imagen ({ctype})")
            if len(body) < 1024:
                raise HTTPException(415, f"Imagen muy chica ({len(body)} bytes)")
            return body, ctype
        if status != 403:
            break  # solo reintentamos Referer ante 403

    raise HTTPException(502, f"No se pudo descargar la imagen (error {last_status})")


def _ext_from_ctype(ct: str) -> str:
    ct = (ct or "").lower()
    if "png" in ct:  return "png"
    if "webp" in ct: return "webp"
    if "avif" in ct: return "avif"
    if "gif" in ct:  return "gif"
    return "jpg"


def _trim_and_square(img, padding_pct: float = 0.06):
    """Recorta bordes (transparentes o casi blancos) y empareja a cuadrado
    con fondo blanco + padding. Sirve para que productos con mucho whitespace
    queden visualmente del mismo tamaño que productos con poco whitespace.

    Args:
        img: PIL.Image (RGB o RGBA)
        padding_pct: porcentaje de padding alrededor del bbox encontrado.
                     0.06 = 6% del lado más largo.
    Returns:
        PIL.Image en modo RGB cuadrado con fondo blanco.
    """
    from PIL import Image, ImageChops

    # 1) Encontrar el bbox del contenido
    if img.mode == "RGBA":
        # Bbox por canal alpha — funciona perfecto con PNG transparente
        bbox = img.split()[-1].getbbox()
        if bbox:
            img = img.crop(bbox)
        img_rgb = Image.new("RGB", img.size, (255, 255, 255))
        img_rgb.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = img_rgb
    else:
        img = img.convert("RGB")
        # Bbox por diferencia con un fondo blanco — captura productos sobre fondo blanco
        bg = Image.new("RGB", img.size, (255, 255, 255))
        diff = ImageChops.difference(img, bg)
        # Reducir ruido (compresión JPEG deja píxeles "casi blancos")
        diff = ImageChops.add(diff, diff, 2.0, -30)
        bbox = diff.getbbox()
        if bbox:
            img = img.crop(bbox)

    # 2) Hacer cuadrado: pegar centrado en un canvas blanco más grande
    w, h = img.size
    side = max(w, h)
    pad = int(side * padding_pct)
    canvas_side = side + 2 * pad
    canvas = Image.new("RGB", (canvas_side, canvas_side), (255, 255, 255))
    offset = ((canvas_side - w) // 2, (canvas_side - h) // 2)
    canvas.paste(img, offset)
    return canvas


def _optimize_image(content: bytes) -> tuple[bytes, str, int, int]:
    """Optimiza la imagen: auto-orient + trim de bordes + cuadrado con fondo
    blanco + resize a 1200x1200 + WebP q=85. Devuelve (bytes, ct, w, h).
    Si algo falla, devuelve el contenido original como fallback.

    El trim+cuadrado normaliza el tamaño visual de los productos en el grid:
    sin esto, los PNG con mucho whitespace alrededor se ven chicos comparados
    con los que llenan el frame.
    """
    try:
        from PIL import Image, ImageOps
        from io import BytesIO
    except ImportError:
        return content, "image/jpeg", 0, 0

    try:
        img = Image.open(BytesIO(content))
        img = ImageOps.exif_transpose(img)  # auto-orient

        # Normalizar a RGBA o RGB según corresponda (preservamos transparencia en PNG)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.mode else "RGB")

        # Trim + cuadrado con fondo blanco (#8 — tamaños inconsistentes)
        try:
            img = _trim_and_square(img, padding_pct=0.06)
        except Exception as e:
            logger.warning("optimize_image: trim_and_square falló, sigo sin trim: %s", e)

        # Resize a 1200x1200 (cuadrado) si excede
        TARGET_SIDE = 1200
        if img.width > TARGET_SIDE:
            img = img.resize((TARGET_SIDE, TARGET_SIDE), Image.Resampling.LANCZOS)

        out = BytesIO()
        img.save(out, format="WEBP", quality=85, method=6)
        return out.getvalue(), "image/webp", img.width, img.height
    except Exception as e:
        logger.warning("optimize_image: fallback (no se pudo optimizar): %s", e, exc_info=True)
        return content, "image/jpeg", 0, 0


def _r2_config() -> dict:
    """Lee la configuración de Cloudflare R2 desde env. Eleva 500 si falta algo."""
    import os
    cfg = {
        "account_id":      os.getenv("R2_ACCOUNT_ID") or "",
        "access_key_id":   os.getenv("R2_ACCESS_KEY_ID") or "",
        "secret_key":      os.getenv("R2_SECRET_ACCESS_KEY") or "",
        "bucket":          os.getenv("R2_BUCKET") or "equipos-fotos",
        "public_base":     (os.getenv("R2_PUBLIC_BASE") or "").rstrip("/"),
    }
    missing = [k for k in ("account_id", "access_key_id", "secret_key") if not cfg[k]]
    if missing:
        raise HTTPException(
            500,
            f"R2 no configurado: faltan env vars {', '.join('R2_'+m.upper() for m in missing)}. "
            "Configurá en Railway: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, "
            "R2_BUCKET, R2_PUBLIC_BASE.",
        )
    if not cfg["public_base"]:
        # Default al endpoint público de R2 (sin custom domain) — válido si activaste public bucket
        cfg["public_base"] = f"https://pub-{cfg['account_id']}.r2.dev"
    return cfg


# Cliente boto3 singleton: crearlo cuesta ~50ms (parse config, init session,
# resolver endpoint) y antes lo creabamos en cada upload. Con singleton, el
# costo es one-time. Cacheamos la tupla (config, client) y la invalidamos
# si cambia la config (ej. rotación de credenciales en runtime).
_r2_client_cache: tuple[tuple, object] | None = None


def _get_r2_client(cfg: dict) -> object:
    """Devuelve un cliente boto3 reutilizable para el bucket R2."""
    global _r2_client_cache
    cfg_key = (cfg["account_id"], cfg["access_key_id"], cfg["secret_key"])
    if _r2_client_cache is not None and _r2_client_cache[0] == cfg_key:
        return _r2_client_cache[1]
    try:
        import boto3
        from botocore.config import Config as BotoConfig
    except ImportError:
        raise HTTPException(500, "boto3 no instalado en el backend")
    client = boto3.client(
        "s3",
        endpoint_url=f"https://{cfg['account_id']}.r2.cloudflarestorage.com",
        aws_access_key_id=cfg["access_key_id"],
        aws_secret_access_key=cfg["secret_key"],
        region_name="auto",
        config=BotoConfig(signature_version="s3v4"),
    )
    _r2_client_cache = (cfg_key, client)
    return client



def _upload_to_r2(path: str, content: bytes, content_type: str) -> str:
    """Sube `content` al bucket R2 vía S3 API (boto3). Devuelve la URL pública."""
    cfg = _r2_config()
    client = _get_r2_client(cfg)
    try:
        client.put_object(
            Bucket=cfg["bucket"],
            Key=path,
            Body=content,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )
    except Exception as e:
        raise HTTPException(502, f"R2 upload falló: {e}")

    return f"{cfg['public_base']}/{path}"


def _upload_to_supabase_storage(path: str, content: bytes, content_type: str) -> str:
    """Sube `content` al bucket equipos-fotos vía REST API usando service role.
    Devuelve la URL pública. Eleva HTTPException si falla.
    """
    import os
    import httpx

    base = (
        os.getenv("SUPABASE_URL")
        or os.getenv("SUPABASE_PROJECT_URL")
        or "https://ytujjqoffcdsdowfqaex.supabase.co"
    ).rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not service_key:
        raise HTTPException(
            500,
            "Falta SUPABASE_SERVICE_ROLE_KEY en el backend. "
            "Configurala como env var en Railway.",
        )

    bucket = "equipos-fotos"
    upload_url = f"{base}/storage/v1/object/{bucket}/{path}"
    headers = {
        "Authorization": f"Bearer {service_key}",
        "apikey": service_key,
        "Content-Type": content_type,
        "x-upsert": "false",
        "Cache-Control": "3600",
    }
    try:
        with httpx.Client(timeout=30.0) as c:
            r = c.post(upload_url, headers=headers, content=content)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"No se pudo subir a Storage: {e}")

    if r.status_code not in (200, 201):
        snippet = (r.text or "")[:300]
        raise HTTPException(
            r.status_code if r.status_code >= 400 else 502,
            f"Storage devolvió {r.status_code}: {snippet}",
        )

    return f"{base}/storage/v1/object/public/{bucket}/{path}"
