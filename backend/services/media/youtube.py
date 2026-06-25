"""Soporte YouTube en el sistema de media (F0c).

Funciones:
  extract_video_id(url_or_id)  → extrae el video_id de cualquier forma de URL YouTube.
  youtube_nocookie_url(vid)    → embed URL con youtube-nocookie.com (privacidad).
  fetch_youtube_poster(vid)    → descarga la miniatura del video (maxresdefault → hqdefault).
  store_youtube_poster(vid, *, kind, conn) → almacena el poster en R2 vía store_upload.

Privacidad:
  - El embed usa youtube-nocookie.com: YouTube no deposita cookies hasta que
    el usuario hace clic en Play (no al cargar la página).
  - El poster se guarda en R2: la página puede mostrar la imagen de preview
    sin hacer ningún request a YouTube — mejora LCP y evita tracking previo al play.

Seguridad:
  - fetch_youtube_poster sólo descarga desde img.youtube.com (dominio allowlisteado);
    no admite URLs arbitrarias (sin SSRF).
  - Rechaza video_ids con caracteres inválidos (sólo [A-Za-z0-9_-], 11 chars).
"""
import logging
import re

from .errors import MediaError
from .models import MediaAsset
from . import specs as _specs

logger = logging.getLogger(__name__)

# YouTube video IDs son exactamente 11 chars: [A-Za-z0-9_-]
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

# Calidades en orden de preferencia (maxres primero)
_POSTER_QUALITIES = ("maxresdefault", "sddefault", "hqdefault")


def extract_video_id(url_or_id: str) -> str | None:
    """Extrae el video_id de una URL de YouTube o lo devuelve si ya es un ID.

    Soporta:
      https://youtu.be/dQw4w9WgXcQ
      https://www.youtube.com/watch?v=dQw4w9WgXcQ
      https://www.youtube.com/shorts/dQw4w9WgXcQ
      https://www.youtube.com/embed/dQw4w9WgXcQ
      dQw4w9WgXcQ  (ID directo)
    """
    s = (url_or_id or "").strip()
    if not s:
        return None

    # Si ya parece un ID directo (sin slashes ni :)
    if _VIDEO_ID_RE.match(s):
        return s

    try:
        from urllib.parse import urlparse, parse_qs
        u = urlparse(s)
        host = (u.hostname or "").lower().lstrip("www.")

        if host == "youtu.be":
            vid = u.path.lstrip("/")[:11]
            return vid if _VIDEO_ID_RE.match(vid) else None

        if "youtube.com" in host:
            # /watch?v=ID
            v = parse_qs(u.query).get("v", [None])[0]
            if v and _VIDEO_ID_RE.match(v):
                return v
            # /embed/ID  o  /shorts/ID
            m = re.match(r"/(?:embed|shorts|v)/([A-Za-z0-9_-]{11})", u.path)
            if m:
                return m.group(1)
    except Exception:
        pass
    return None


def youtube_nocookie_url(video_id: str) -> str:
    """URL de embed con youtube-nocookie.com.
    No deposita cookies hasta que el usuario hace click en Play.
    """
    return f"https://www.youtube-nocookie.com/embed/{video_id}"


def fetch_youtube_poster(video_id: str) -> bytes:
    """Descarga la miniatura de mayor calidad disponible.

    Intenta maxresdefault → sddefault → hqdefault.
    Solo descarga desde img.youtube.com (no SSRF).
    Eleva MediaError(502) si ninguna calidad responde.
    """
    if not _VIDEO_ID_RE.match(video_id or ""):
        raise MediaError(400, f"video_id inválido: {video_id!r}")

    try:
        import httpx
    except ImportError:
        raise MediaError(500, "httpx no instalado en el backend")

    last_err: Exception | None = None
    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        for quality in _POSTER_QUALITIES:
            url = f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"
            try:
                r = client.get(url)
                if r.status_code == 200 and r.content:
                    ct = r.headers.get("content-type", "")
                    if ct.startswith("image/") and len(r.content) > 1000:
                        logger.info("youtube poster: %s/%s (%d bytes)", video_id, quality, len(r.content))
                        return r.content
            except Exception as e:
                last_err = e

    raise MediaError(502, f"No se pudo obtener el poster de YouTube para '{video_id}': {last_err}")


def store_youtube_poster(
    video_id: str,
    *,
    kind: str,
    conn,
) -> MediaAsset:
    """Almacena el poster del video en R2 como media asset.

    Descarga la miniatura YouTube → strip EXIF → deriva variantes → guarda en R2.
    El asset resultante puede usarse como poster del embed (<YouTubeEmbed>).

    kind: el mismo kind del contexto (ej. "equipo") — determina el prefijo R2.
    conn: conexión DB sin commit (el caller hace commit junto con sus otras escrituras).
    """
    raw = fetch_youtube_poster(video_id)
    from .service import store_upload
    # Keep-aspect ratio: el poster es 16:9, no se recorta a cuadrado.
    return store_upload(
        raw,
        kind=kind,
        derive_specs=[_specs.DISPLAY_KEEP_ASPECT, _specs.DISPLAY_KEEP_ASPECT_SM],
        conn=conn,
    )
