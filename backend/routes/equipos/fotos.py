"""Fotos / media de un equipo (#501 fase a — extraído de `core`).

Cubre la superficie de medios del equipo: subida de fotos (archivo / URL), listado
/ borrado / reordenamiento, búsqueda-scraping de fotos, subida del HTML fuente y
diagnóstico de storage. Registra sus rutas en el router compartido del paquete
`routes.equipos`. Los helpers de R2 vienen de `services.media.storage` (no de
`core`); `core` mantiene su propio import de `_r2_config`/`_delete_from_r2` porque
`delete_equipo` también limpia el blob scrapeado. `UploadFotoFromUrlInput` lo
re-exporta el `__init__` del paquete (lo consume `test_ssrf`).
"""
import logging
import os
import re
import unicodedata
from typing import Optional

from fastapi import File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from admin_guard import require_admin
from database import get_db
from routes.equipos.core import router

logger = logging.getLogger(__name__)

# /buscar-fotos: cuántos validamos y cuántos devolvemos. Este flow inspecciona
# más fuentes (Wikipedia, reviews, manufacturer) por eso el límite es mayor.
MAX_PHOTO_CANDIDATES_BUSCAR_VALIDATE = 24
MAX_PHOTO_CANDIDATES_BUSCAR_RETURN   = 16


@router.post("/admin/equipos/{id}/upload-html-source")
async def admin_upload_html_source(
    id: int,
    request: Request,
    file: UploadFile = File(...),
    categoria_hint: Optional[str] = None,
) -> dict:
    """Sube y persiste el HTML guardado de B&H, extrae specs y los devuelve.

    Guarda el blob en R2 (equipos/{id}/source.html), actualiza html_source_url
    en la BD y devuelve AutocompletarResult con los specs extraídos. Una segunda
    llamada sobreescribe el blob anterior (path determinístico sin timestamp).

    Args:
        id: ID del equipo al que se asocia el HTML.
        file: HTML guardado (Cmd+S → Webpage Complete).
        categoria_hint: categoría opcional para saltear auto-detección.

    Returns: {html_source_url, ...AutocompletarResult}
    """
    require_admin(request)

    with get_db() as conn:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")

    content = await file.read()
    if not content:
        raise HTTPException(400, "Archivo vacío")
    if len(content) > 5_000_000:
        raise HTTPException(400, "HTML demasiado grande (máx 5MB)")

    try:
        html_content = content.decode("utf-8", errors="replace")
    except Exception:
        raise HTTPException(400, "HTML inválido (no es UTF-8)")

    path = f"equipos/{id}/source.html"
    with media_http():
        html_source_url = _put_r2(path, content, "text/html; charset=utf-8")

    with get_db() as conn:
        try:
            conn.execute(
                "UPDATE equipos SET html_source_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id=?",
                (html_source_url, id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    try:
        from services.equipo_html_extractor import extract_from_html
        result = extract_from_html(html_content, categoria_hint=categoria_hint)
    except Exception:
        logger.exception("Error extrayendo specs del HTML (equipo %d)", id)
        raise HTTPException(500, "No se pudo procesar el HTML")

    return {"html_source_url": html_source_url, **result}



# ── Admin: búsqueda dedicada de fotos (separada del enriquecimiento) ─────────
#
# El enriquecedor general usa B&H/Adorama (mejor para specs) pero esos sitios
# bloquean hotlinking de fotos. Este endpoint busca específicamente en sitios
# con imágenes confiables (Wikipedia, manufacturer, sitios de review).

class BuscarFotosInput(BaseModel):
    nombre: Optional[str]      = None
    marca:  Optional[str]      = None
    modelo: Optional[str]      = None
    url:    Optional[str]      = None
    exclude: Optional[list[str]] = None  # URLs ya conocidas (para "buscar más")


@router.post("/admin/equipos/buscar-fotos")
def admin_buscar_fotos(payload: BuscarFotosInput, request: Request):
    """Busca fotos del equipo en fuentes optimizadas para imágenes (Wikipedia,
    manufacturer oficial, review sites). Devuelve lista validada de candidatos."""
    require_admin(request)

    import httpx
    import re

    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
    if not FIRECRAWL_API_KEY:
        raise HTTPException(500, "FIRECRAWL_API_KEY no configurado")

    direct_url = (payload.url or "").strip() or None
    if direct_url and not direct_url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "URL inválida")

    query = " ".join(x for x in [payload.marca, payload.nombre, payload.modelo] if x).strip()
    if not direct_url and not query:
        raise HTTPException(400, "Falta nombre/marca o url")

    exclude_lc: set[str] = {(u or "").strip().lower() for u in (payload.exclude or [])}

    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type":  "application/json",
    }

    # Queries optimizados para fotos de producto con fondo blanco/neutro,
    # bien iluminadas — ideal para equipos audiovisuales de renta.
    # B&H primero: hero shots standarizados sobre fondo gris/blanco.
    PHOTO_QUERIES = [
        # 1. B&H Photo: fotos hero de producto, alta resolución, fondo neutro
        f"{query} product photo site:bhphotovideo.com",
        # 2. Adorama / KEH: misma categoría de retailers
        f"{query} product image (site:adorama.com OR site:keh.com)",
        # 3. Manufacturer oficial — página de producto
        f"{query} product page (site:canon.com OR site:usa.canon.com OR site:sony.com OR site:nikon.com OR "
        f"site:fujifilm.com OR site:panasonic.com OR site:blackmagicdesign.com OR site:aputure.com OR "
        f"site:godox.com OR site:rode.com OR site:sennheiser.com OR site:dji.com OR site:atomos.com OR "
        f"site:tilta.com OR site:smallrig.com OR site:saramonic.com OR site:zoom-na.com)",
        # 4. Wikipedia: fallback con imágenes limpias y sin paywall
        f"{query} (site:en.wikipedia.org OR site:commons.wikimedia.org OR site:es.wikipedia.org)",
    ]

    def _fc_search(q: str, client) -> list[str]:
        try:
            r = client.post(
                "https://api.firecrawl.dev/v2/search",
                headers=headers,
                json={"query": q, "limit": 3},
            )
        except httpx.HTTPError:
            return []
        if r.status_code != 200:
            return []
        data = r.json().get("data")
        rows = data if isinstance(data, list) else (data.get("web") if isinstance(data, dict) else None) or []
        urls = []
        for row in rows:
            u = (row.get("url") or "").strip() if isinstance(row, dict) else ""
            if u.lower().startswith(("http://", "https://")) and not u.lower().endswith(".pdf"):
                urls.append(u)
        return urls

    def _extract_images_from_page(url: str, client, trust_url: bool = False) -> list[str]:
        """Scrapea una página y extrae URLs de imagen (meta + markdown img tags).
        Si trust_url=True (cuando el usuario pega el link explícitamente), no
        descarta candidatos por dimensiones pequeñas en la URL — solo filtra
        patrones obvios de basura (thumbs, iconos, logos)."""
        try:
            r = client.post(
                "https://api.firecrawl.dev/v2/scrape",
                headers=headers,
                json={"url": url, "formats": ["markdown"], "onlyMainContent": False},
            )
        except httpx.HTTPError:
            return []
        if r.status_code != 200:
            return []
        sd = r.json().get("data") or {}
        meta = sd.get("metadata") or {}
        markdown = sd.get("markdown") or ""

        cands: list[str] = []
        seen: set[str] = set()

        def push(u: str | None) -> None:
            if not u or not isinstance(u, str):
                return
            u = u.strip()
            if not u.lower().startswith(("http://", "https://")):
                return
            # Filtrar tracking pixels y svgs decorativos
            if u.lower().endswith(".svg"):
                return
            lo = u.lower()
            # Filtrar thumbnails, iconos, logos y dimensiones pequeñas en la URL.
            # Patrones comunes que indican imagen de baja calidad:
            #   _thumb, -thumb, /thumbs/, _small, _sm, /icons/, /logos/,
            #   width=NN (≤200), w=NN (≤200), -100x100, _50x50, etc.
            LOW_QUALITY_PATTERNS = (
                "/thumb", "_thumb", "-thumb", "/thumbs/", "thumbnail",
                "/icon", "_icon", "-icon",
                "/logo", "_logo", "-logo", "favicon",
                "/avatar", "_avatar", "-avatar",
                "/sprite", "spacer.gif", "pixel.gif",
                "_sm.", "-sm.", "_small.", "-small.",
                # Ads, banners, promos, campaign creatives (B&H/Sony/etc.
                # incrustan estos en las páginas de producto; no son la
                # foto del equipo en sí).
                "/banner", "_banner", "-banner",
                "/promo", "_promo", "-promo",
                "/campaign", "_campaign", "-campaign",
                "/ads/", "/ad-", "_ad-", "adservice",
                "/marketing", "_marketing",
                "doubleclick", "googleads", "googlesyndication",
                "amazon-adsystem", "scorecardresearch",
                "/billboard", "_billboard",
                "/hero-banner", "homepage-banner",
                "watch-now", "/events/", "/event-",
                "in-residence", "panel-",
                "newsroom", "press-release", "press/",
            )
            if any(p in lo for p in LOW_QUALITY_PATTERNS):
                return
            if not trust_url:
                # Dimensiones pequeñas en URL: -100x100, _50x50, 200x150
                import re as _re
                m = _re.search(r"[-_/](\d{2,4})x(\d{2,4})", lo)
                if m:
                    w, h = int(m.group(1)), int(m.group(2))
                    if w < 800 or h < 800:
                        return
                # width=NN o w=NN <= 300 en query string
                m = _re.search(r"[?&](?:width|w|size)=(\d+)", lo)
                if m and int(m.group(1)) < 800:
                    return
            k = lo
            if k in seen or k in exclude_lc:
                return
            seen.add(k)
            cands.append(u)

        push(meta.get("ogImage") or meta.get("og:image"))
        push(meta.get("twitterImage") or meta.get("twitter:image"))
        # ![alt](url) en markdown
        for m in re.finditer(r"!\[[^\]]*\]\(([^)\s]+)", markdown):
            push(m.group(1))
        # <img src="..."> en HTML embebido
        for m in re.finditer(r'<img[^>]+src=["\']?([^"\'>\s]+)', markdown):
            push(m.group(1))

        # Ordenar: primero URLs con indicadores de foto de producto (fondo blanco/hero)
        PRODUCT_INDICATORS = (
            "/product/", "_hero", "-hero", "_main", "-main",
            "-product-", "/images/", "bhphotovideo.com",
            "_front", "-front", "_top", "-top",
        )
        def _product_score(u: str) -> int:
            lo = u.lower()
            return sum(1 for p in PRODUCT_INDICATORS if p in lo)

        cands.sort(key=_product_score, reverse=True)
        return cands[:10]

    # Validación rápida: HEAD/GET parcial, descarta lo que no sea imagen real
    def _is_valid_image(url: str, client) -> bool:
        try:
            from urllib.parse import urlparse as _up
            host = (_up(url).hostname or "").lower()
            hdrs = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
                "Referer": f"https://{host}/" if host else "",
            }
            # Bajamos los primeros 16KB para chequear:
            #   1. Que sea una imagen (content-type)
            #   2. Que las dimensiones no sean de banner (relación ancho/alto
            #      muy extrema descarta banners promo tipo 728x90, 970x250).
            hdrs["Range"] = "bytes=0-16384"
            rg = client.get(url, headers=hdrs, follow_redirects=True, timeout=8.0)
            if rg.status_code not in (200, 206):
                return False
            ct = rg.headers.get("content-type", "")
            if not ct.startswith("image/"):
                return False
            # Intentar parsear el header para sacar dimensiones (PIL solo
            # necesita la cabecera). Si falla, asumimos válida.
            try:
                from PIL import Image as _PILImage
                from io import BytesIO as _BIO
                img = _PILImage.open(_BIO(rg.content))
                w, h = img.size
                if w > 0 and h > 0:
                    ratio = max(w, h) / max(1, min(w, h))
                    # Banners típicos: 8:1+ (728x90 ≈ 8.1, 970x250 ≈ 3.88).
                    # Cualquier cosa > 3.5:1 muy probable que sea banner/strip.
                    if ratio > 3.5:
                        return False
                    # Imágenes muy chicas no sirven como hero del producto.
                    if min(w, h) < 240:
                        return False
            except Exception:
                pass
            return True
        except httpx.HTTPError:
            pass
        return False

    def _og_images_from_html(url: str, client) -> list[str]:
        """Extrae og:image y twitter:image directamente del HTML sin Firecrawl.
        Más rápido y confiable para páginas de producto de B&H y similares."""
        try:
            r = client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=15.0,
                follow_redirects=True,
            )
        except httpx.HTTPError:
            return []
        if r.status_code != 200:
            return []
        html = r.text[:100_000]
        imgs: list[str] = []
        seen: set[str] = set()
        def _push_og(u: str | None) -> None:
            if not u:
                return
            u = u.strip()
            if u.lower().startswith(("http://", "https://")) and u.lower() not in seen:
                seen.add(u.lower())
                imgs.append(u)
        # og:image (dos posibles órdenes de atributos)
        for pat in [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'og:image["\'][^>]*content=["\']([^"\']+)["\']',
        ]:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                _push_og(m.group(1))
                break
        # twitter:image
        for pat in [
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
        ]:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                _push_og(m.group(1))
                break
        return imgs

    all_cands: list[str] = []
    seen_lc: set[str] = set()
    # Cuando el usuario pegó una URL directa, marcamos las fotos obtenidas para
    # saltear la validación HEAD (B&H CDN puede rechazar HEADs cross-origin).
    direct_url_cands: set[str] = set()

    with httpx.Client(timeout=45.0) as client:
        if direct_url:
            # 1) Si la URL es directamente una imagen, usarla tal cual.
            if direct_url.lower().rsplit(".", 1)[-1] in ("jpg", "jpeg", "png", "webp", "avif", "gif"):
                all_cands.append(direct_url)
                seen_lc.add(direct_url.lower())
                direct_url_cands.add(direct_url.lower())

            # 2) Extraer og:image directamente del HTML (rápido, sin Firecrawl).
            #    Más confiable para B&H y sitios JS-pesados.
            for u in _og_images_from_html(direct_url, client):
                if u.lower() not in seen_lc:
                    seen_lc.add(u.lower())
                    all_cands.append(u)
                    direct_url_cands.add(u.lower())

            # 2b) B&H carrusel: si algún candidato sigue el patrón del CDN de B&H
            #     (static.bhphotovideo.com/c/product/{SKU}-{ANGLE}/{slug}), derivar
            #     los demás ángulos del carrusel sin hacer HEAD requests extra
            #     (el CDN bloquea cross-origin; los ángulos son de confianza).
            _BH_CDN_RE = re.compile(
                r"(https://static\.bhphotovideo\.com/c/product/\d+)-[A-Z0-9]+/([^?]+)",
                re.IGNORECASE,
            )
            for base_cand in list(all_cands):
                m_bh = _BH_CDN_RE.match(base_cand)
                if not m_bh:
                    continue
                base_prefix, slug = m_bh.group(1), m_bh.group(2)
                for angle in ("MAIN", "REAR", "SL01", "SL02", "SL03", "SL04", "SL05", "SL06", "SL07"):
                    u = f"{base_prefix}-{angle}/{slug}"
                    if u.lower() not in seen_lc:
                        seen_lc.add(u.lower())
                        all_cands.append(u)
                        direct_url_cands.add(u.lower())
                break  # solo necesitamos un candidato base para el patrón

            # 3) Firecrawl para más candidatos (especialmente imgs del body).
            for u in _extract_images_from_page(direct_url, client, trust_url=True):
                if u.lower() not in seen_lc:
                    seen_lc.add(u.lower())
                    all_cands.append(u)
        else:
            for q in PHOTO_QUERIES:
                if len(all_cands) >= 18:
                    break
                for top in _fc_search(q, client)[:2]:
                    for u in _extract_images_from_page(top, client):
                        if u.lower() not in seen_lc:
                            seen_lc.add(u.lower())
                            all_cands.append(u)

        # Validar candidatos — los que vienen de URL directa se saltan la
        # validación (B&H CDN rechaza HEADs cross-origin; el og:image del propio
        # sitio es confiable sin necesidad de un round-trip extra).
        with httpx.Client(timeout=10.0) as vc:
            validated = [
                u for u in all_cands[:MAX_PHOTO_CANDIDATES_BUSCAR_VALIDATE]
                if u.lower() in direct_url_cands or _is_valid_image(u, vc)
            ][:MAX_PHOTO_CANDIDATES_BUSCAR_RETURN]

    return {"foto_candidates": validated, "total_inspeccionadas": len(all_cands)}



# ── Admin: descargar imagen externa y subirla a Cloudflare R2 ────────────────
#
# El frontend NO sube directamente al bucket porque eso requeriría exponer
# credenciales de R2 al browser. Acá lo hacemos en el backend con el secret
# guardado en env vars.
#
# SSRF guard
# ----------
# El admin autenticado puede pedir descargar cualquier URL externa. Sin
# allowlist, esto sería SSRF: un admin malicioso/comprometido podría hacer
# que el backend descargue http://localhost:5432/, http://169.254.169.254/
# (metadata cloud), o cualquier IP de la VPC interna de Railway. Filtramos:
# (1) sólo http(s) en puerto estándar (80/443), (2) host en allowlist de
# dominios conocidos, (3) la IP resuelta del host no es privada/loopback.


from services.media.security import _download_image_bytes, _validate_external_image_url
from services.media.storage import delete_object as _delete_from_r2, put as _put_r2
from services.media import (
    EQUIPO_DERIVE_SPECS,
    collect_asset_keys,
    purge_r2,
    store_upload,
)
from services.media_fastapi import media_http


def _foto_path(equipo_id: int, ext: str) -> str:
    """Genera path R2: equipos/{id}_{slug}/{id}_{slug}-{ts}.{ext}

    El timestamp en el nombre del archivo evita el problema del cache
    inmutable: R2 sirve los assets con Cache-Control: max-age=1año
    immutable, así que dos uploads al mismo path harían que el navegador
    siga mostrando el viejo durante un año. Con timestamp cada upload
    tiene URL nueva. El archivo anterior queda como huérfano en R2.
    """
    import time as _time
    try:
        with get_db() as conn:
            row = conn.execute("SELECT nombre FROM equipos WHERE id = %s", (equipo_id,)).fetchone()
        nombre = row[0] if row else ""
    except Exception:
        nombre = ""

    if nombre:
        slug = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
        slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")[:50]
    else:
        slug = ""

    ts = int(_time.time())
    if slug:
        folder   = f"{equipo_id}_{slug}"
        filename = f"{equipo_id}_{slug}-{ts}.{ext}"
    else:
        folder   = f"{equipo_id}"
        filename = f"{equipo_id}-{ts}.{ext}"
    return f"equipos/{folder}/{filename}"


class UploadFotoFromUrlInput(BaseModel):
    url: str


@router.post("/admin/equipos/{equipo_id}/upload-foto-from-url")
def admin_upload_foto_from_url(
    equipo_id: int,
    payload: UploadFotoFromUrlInput,
    request: Request,
):
    """Descarga imagen externa, la optimiza y la sube a Cloudflare R2.
    Crea una fila en equipo_fotos y sincroniza equipos.foto_url con la principal.
    Devuelve {public_url, path, size, content_type}.
    """
    require_admin(request)

    url = (payload.url or "").strip()
    if not url:
        raise HTTPException(400, "URL vacía")

    cfg_pub = (os.getenv("R2_PUBLIC_BASE") or "").rstrip("/")
    if cfg_pub and url.startswith(cfg_pub + "/"):
        return {"public_url": url, "path": None, "skipped": True}

    with media_http():
        _validate_external_image_url(url)
        raw_content, _raw_ctype = _download_image_bytes(url)

    with get_db() as conn:
        try:
            with media_http():
                asset = store_upload(raw_content, kind="equipo", derive_specs=EQUIPO_DERIVE_SPECS, conn=conn)
            display = asset.variant("display")
            _insert_equipo_foto(conn, equipo_id, display.url, display.key, asset.id)
        except Exception:
            conn.rollback()
            raise

    return {
        "public_url": display.url,
        "path": display.key,
        "size": display.bytes,
        "size_original": len(raw_content),
        "content_type": display.content_type,
        "width": display.width or None,
        "height": display.height or None,
    }


# ── Admin: subir bytes de un archivo (multipart) directo a R2 ─────────────

@router.post("/admin/equipos/{equipo_id}/upload-foto")
async def admin_upload_foto_file(
    equipo_id: int,
    request: Request,
):
    """Sube un archivo (multipart/form-data, campo `file`) a R2 con pipeline
    no-destructivo: guarda el original + variante cuadrada 1200×1200.
    Crea una fila en equipo_fotos y sincroniza equipos.foto_url.
    """
    require_admin(request)

    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(400, "Falta el campo 'file' en el form-data")

    raw_content = await file.read()
    if not raw_content:
        raise HTTPException(400, "Archivo vacío")
    if len(raw_content) > 20 * 1024 * 1024:
        raise HTTPException(413, "Archivo muy grande (máx 20MB)")

    with get_db() as conn:
        try:
            with media_http():
                asset = store_upload(raw_content, kind="equipo", derive_specs=EQUIPO_DERIVE_SPECS, conn=conn)
            display = asset.variant("display")
            _insert_equipo_foto(conn, equipo_id, display.url, display.key, asset.id)
        except Exception:
            conn.rollback()
            raise

    return {
        "public_url": display.url,
        "path": display.key,
        "size": display.bytes,
        "size_original": len(raw_content),
        "content_type": display.content_type,
        "width": display.width or None,
        "height": display.height or None,
    }


# ── Galería multi-foto de equipos (F2) ───────────────────────────────────────


def _get_equipo_fotos(conn, equipo_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id, url, path, media_id, orden, es_principal, created_at "
        "FROM equipo_fotos WHERE equipo_id = ? ORDER BY orden, id",
        (equipo_id,),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "url": r["url"],
            "path": r["path"],
            "media_id": r["media_id"],
            "orden": r["orden"],
            "es_principal": bool(r["es_principal"]),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


def _principal_sm_url(conn, equipo_id: int) -> str | None:
    """URL de la variante 'display-sm' (600px) de la foto PRINCIPAL del equipo,
    para srcset. None si la principal no tiene esa variante (foto legacy sin
    media_id, o aún sin backfill) → el front cae a foto_url (sin srcset, cero rotura).
    """
    row = conn.execute(
        "SELECT media_id FROM equipo_fotos WHERE equipo_id = ? AND es_principal = TRUE LIMIT 1",
        (equipo_id,),
    ).fetchone()
    if not row or not row["media_id"]:
        return None
    v = conn.execute(
        "SELECT url FROM media_variants WHERE asset_id = ? AND name = 'display-sm' LIMIT 1",
        (row["media_id"],),
    ).fetchone()
    return v["url"] if v else None


def _principal_thumb_url(conn, equipo_id: int) -> str | None:
    """URL de la variante 'display-thumb' (160px) de la foto PRINCIPAL del equipo,
    para srcset en slots de ~48px. None si no existe (foto pre-backfill) → fallback seguro."""
    row = conn.execute(
        "SELECT media_id FROM equipo_fotos WHERE equipo_id = ? AND es_principal = TRUE LIMIT 1",
        (equipo_id,),
    ).fetchone()
    if not row or not row["media_id"]:
        return None
    v = conn.execute(
        "SELECT url FROM media_variants WHERE asset_id = ? AND name = 'display-thumb' LIMIT 1",
        (row["media_id"],),
    ).fetchone()
    return v["url"] if v else None


def _sync_principal_denorm(conn, equipo_id: int) -> None:
    """Sincroniza TODAS las columnas denormalizadas de la foto principal del equipo.

    Una sola UPDATE reemplaza los 3 sitios que antes actualizaban (url/sm/thumb) por separado.
    No commitea — el caller lo hace.
    """
    row = conn.execute(
        "SELECT url, media_id FROM equipo_fotos WHERE equipo_id = ? AND es_principal = TRUE LIMIT 1",
        (equipo_id,),
    ).fetchone()
    if not row:
        conn.execute(
            "UPDATE equipos SET foto_url = NULL, foto_url_sm = NULL, foto_url_thumb = NULL, "
            "foto_url_avif = NULL, foto_url_sm_avif = NULL, foto_url_thumb_avif = NULL, "
            "foto_lqip = NULL WHERE id = ?",
            (equipo_id,),
        )
        return

    principal_url = row["url"]
    media_id = row["media_id"]
    sm = thumb = avif = sm_avif = thumb_avif = lqip = None

    if media_id:
        for v in conn.execute(
            "SELECT name, url FROM media_variants WHERE asset_id = ? "
            "AND name IN ('display-sm','display-thumb','display-avif','display-sm-avif','display-thumb-avif')",
            (media_id,),
        ).fetchall():
            if v["name"] == "display-sm":
                sm = v["url"]
            elif v["name"] == "display-thumb":
                thumb = v["url"]
            elif v["name"] == "display-avif":
                avif = v["url"]
            elif v["name"] == "display-sm-avif":
                sm_avif = v["url"]
            elif v["name"] == "display-thumb-avif":
                thumb_avif = v["url"]
        lqip_row = conn.execute(
            "SELECT lqip FROM media_assets WHERE id = ?", (media_id,)
        ).fetchone()
        lqip = lqip_row["lqip"] if lqip_row else None

    conn.execute(
        "UPDATE equipos SET foto_url = ?, foto_url_sm = ?, foto_url_thumb = ?, "
        "foto_url_avif = ?, foto_url_sm_avif = ?, foto_url_thumb_avif = ?, foto_lqip = ? "
        "WHERE id = ?",
        (principal_url, sm, thumb, avif, sm_avif, thumb_avif, lqip, equipo_id),
    )


def _insert_equipo_foto(conn, equipo_id: int, url: str, path: str, media_id: int | None = None) -> dict:
    """Inserta una fila en equipo_fotos y sincroniza equipos.foto_url con la principal.
    La primera foto del equipo se marca como principal automáticamente.
    """
    cur = conn.execute(
        "SELECT COALESCE(MAX(orden), -1) + 1 AS next_orden FROM equipo_fotos WHERE equipo_id = ?",
        (equipo_id,),
    )
    orden = cur.fetchone()["next_orden"]

    cur2 = conn.execute("SELECT COUNT(*) AS cnt FROM equipo_fotos WHERE equipo_id = ?", (equipo_id,))
    is_first = cur2.fetchone()["cnt"] == 0

    conn.execute(
        "INSERT INTO equipo_fotos (equipo_id, url, path, media_id, orden, es_principal) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (equipo_id, url, path, media_id, orden, is_first),
    )

    if is_first:
        _sync_principal_denorm(conn, equipo_id)

    conn.commit()

    cur3 = conn.execute(
        "SELECT id, url, path, media_id, orden, es_principal, created_at "
        "FROM equipo_fotos WHERE equipo_id = ? ORDER BY id DESC LIMIT 1",
        (equipo_id,),
    )
    r = cur3.fetchone()
    return {
        "id": r["id"],
        "url": r["url"],
        "path": r["path"],
        "media_id": r["media_id"],
        "orden": r["orden"],
        "es_principal": bool(r["es_principal"]),
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
    }


@router.get("/admin/equipos/{equipo_id}/fotos")
def get_equipo_fotos(equipo_id: int, request: Request):
    require_admin(request)
    with get_db() as conn:
        eq = conn.execute("SELECT id FROM equipos WHERE id = ?", (equipo_id,)).fetchone()
        if not eq:
            raise HTTPException(404, "Equipo no encontrado")
        return {"fotos": _get_equipo_fotos(conn, equipo_id)}


@router.post("/admin/equipos/{equipo_id}/fotos", status_code=201)
async def upload_equipo_foto(equipo_id: int, request: Request):
    """Sube una foto (multipart, campo 'file') al equipo. Guarda original + variante cuadrada."""
    require_admin(request)

    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(400, "Falta el campo 'file'")

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Archivo vacío")
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(413, "Archivo muy grande (máx 20 MB)")

    with get_db() as conn:
        try:
            eq = conn.execute("SELECT id FROM equipos WHERE id = ?", (equipo_id,)).fetchone()
            if not eq:
                raise HTTPException(404, "Equipo no encontrado")
            with media_http():
                asset = store_upload(raw, kind="equipo", derive_specs=EQUIPO_DERIVE_SPECS, conn=conn)
            display = asset.variant("display")
            foto = _insert_equipo_foto(conn, equipo_id, display.url, display.key, asset.id)
        except Exception:
            conn.rollback()
            raise

    return foto


class EquipoFotoFromUrlBody(BaseModel):
    url: str


@router.post("/admin/equipos/{equipo_id}/fotos/from-url", status_code=201)
def upload_equipo_foto_from_url(equipo_id: int, body: EquipoFotoFromUrlBody, request: Request):
    """Descarga URL externa y la agrega a la galería del equipo."""
    require_admin(request)

    url = (body.url or "").strip()
    if not url:
        raise HTTPException(400, "URL vacía")

    cfg_pub = (os.getenv("R2_PUBLIC_BASE") or "").rstrip("/")
    if cfg_pub and url.startswith(cfg_pub + "/"):
        raise HTTPException(400, "La URL ya está en el bucket — subí el archivo directamente")

    with media_http():
        _validate_external_image_url(url)
        raw, _raw_ctype = _download_image_bytes(url)

    with get_db() as conn:
        try:
            eq = conn.execute("SELECT id FROM equipos WHERE id = ?", (equipo_id,)).fetchone()
            if not eq:
                raise HTTPException(404, "Equipo no encontrado")
            with media_http():
                asset = store_upload(raw, kind="equipo", derive_specs=EQUIPO_DERIVE_SPECS, conn=conn)
            display = asset.variant("display")
            foto = _insert_equipo_foto(conn, equipo_id, display.url, display.key, asset.id)
        except Exception:
            conn.rollback()
            raise

    return foto


@router.delete("/admin/equipos/{equipo_id}/fotos/{foto_id}")
def delete_equipo_foto(equipo_id: int, foto_id: int, request: Request):
    require_admin(request)

    with get_db() as conn:
        cur = conn.execute(
            "SELECT url, path, media_id, es_principal FROM equipo_fotos "
            "WHERE id = ? AND equipo_id = ?",
            (foto_id, equipo_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Foto no encontrada")

        media_id = row["media_id"]
        path = row["path"]
        was_principal = bool(row["es_principal"])

        r2_keys: list[str] = []
        if media_id:
            r2_keys = collect_asset_keys(conn, media_id)

        conn.execute("DELETE FROM equipo_fotos WHERE id = ?", (foto_id,))
        if media_id:
            conn.execute("DELETE FROM media_assets WHERE id = ?", (media_id,))

        # Si era la principal, promover la siguiente en orden
        if was_principal:
            next_foto = conn.execute(
                "SELECT id, url FROM equipo_fotos WHERE equipo_id = ? ORDER BY orden, id LIMIT 1",
                (equipo_id,),
            ).fetchone()
            if next_foto:
                conn.execute(
                    "UPDATE equipo_fotos SET es_principal = TRUE WHERE id = ?", (next_foto["id"],)
                )
            _sync_principal_denorm(conn, equipo_id)

        conn.commit()

    if r2_keys:
        purge_r2(r2_keys)
    elif path:
        _delete_from_r2(path)

    return {"ok": True}


class EquipoFotoOrdenItem(BaseModel):
    id: int
    orden: int
    es_principal: bool


class EquipoFotoReorderBody(BaseModel):
    fotos: list[EquipoFotoOrdenItem]


@router.patch("/admin/equipos/{equipo_id}/fotos/orden")
def reorder_equipo_fotos(equipo_id: int, body: EquipoFotoReorderBody, request: Request):
    require_admin(request)

    with get_db() as conn:
        principal_url: str | None = None
        for f in body.fotos:
            conn.execute(
                "UPDATE equipo_fotos SET orden = ?, es_principal = ? "
                "WHERE id = ? AND equipo_id = ?",
                (f.orden, f.es_principal, f.id, equipo_id),
            )
            if f.es_principal:
                row = conn.execute(
                    "SELECT url FROM equipo_fotos WHERE id = ?", (f.id,)
                ).fetchone()
                if row:
                    principal_url = row["url"]

        if principal_url is not None:
            _sync_principal_denorm(conn, equipo_id)

        conn.commit()
        fotos = _get_equipo_fotos(conn, equipo_id)

    return {"fotos": fotos}


# ── Admin: diagnóstico de R2 (sin exponer secretos) ─────────────────────────

@router.get("/admin/storage/diag")
def admin_storage_diag(request: Request):
    """Verifica que R2 esté configurado correctamente. Sólo dice si las vars
    están presentes y si el upload+read end-to-end funciona. NUNCA devuelve
    el contenido del secret."""
    require_admin(request)

    import time as _time
    import httpx

    vars_status = {
        "R2_ACCOUNT_ID":         bool(os.getenv("R2_ACCOUNT_ID")),
        "R2_ACCESS_KEY_ID":      bool(os.getenv("R2_ACCESS_KEY_ID")),
        "R2_SECRET_ACCESS_KEY":  bool(os.getenv("R2_SECRET_ACCESS_KEY")),
        "R2_BUCKET":             os.getenv("R2_BUCKET") or "equipos-fotos",
        "R2_PUBLIC_BASE":        os.getenv("R2_PUBLIC_BASE") or None,
    }
    missing = [k for k, v in vars_status.items() if v is False]
    if missing:
        return {"ok": False, "vars": vars_status, "missing": missing, "tested": False}

    # Smoke test: subir un blob chico y leerlo
    try:
        sample = b"R2 smoke test " + str(int(_time.time())).encode()
        path = f"diag/smoke-{int(_time.time())}.txt"
        with media_http():
            public_url = _put_r2(path, sample, "text/plain")
        verify = httpx.get(public_url, timeout=10.0)
        ok = verify.status_code == 200 and verify.content == sample
        return {
            "ok":         ok,
            "vars":       vars_status,
            "tested":     True,
            "public_url": public_url,
            "verify":     verify.status_code,
        }
    except HTTPException as e:
        return {"ok": False, "vars": vars_status, "tested": True, "error": e.detail}
    except Exception as e:
        return {"ok": False, "vars": vars_status, "tested": True, "error": str(e)}


# ── Stream B: enriquecer-from-html (hermano JSON de upload-html-source) ──────
#
# Acepta el HTML crudo como string en el body (JSON). No guarda nada en R2
# ni en la BD — solo corre el extractor y devuelve AutocompletarResult.
# El admin pega la URL de B&H en el form, Chrome MCP obtiene el rawHTML
# y lo envía acá; el form muestra las specs para aplicar.

class EnriquecerFromHtmlBody(BaseModel):
    html: str
    categoria_hint: Optional[str] = None
    bh_url: Optional[str] = None  # si se pasa, se guarda en equipos.bh_url


@router.post("/admin/equipos/{id}/enriquecer-from-html")
def admin_enriquecer_from_html(
    id: int,
    body: EnriquecerFromHtmlBody,
    request: Request,
) -> dict:
    """Extrae specs + foto de un HTML de B&H sin guardar nada en R2.

    Hermano JSON de `upload-html-source` (mismo extractor, sin file upload).
    El frontend pasa el rawHTML obtenido por Chrome MCP o fetch del admin;
    el servidor corre extract_from_html y devuelve AutocompletarResult.

    Si `bh_url` está presente, actualiza `equipos.bh_url` como efecto
    secundario (datos de seguro/inventario).
    """
    require_admin(request)

    html_content = (body.html or "").strip()
    if not html_content:
        raise HTTPException(400, "HTML vacío")
    if len(html_content) > 5_000_000:
        raise HTTPException(400, "HTML demasiado grande (máx 5MB)")

    with get_db() as conn:
        if not conn.execute("SELECT id FROM equipos WHERE id = %s", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")

        if body.bh_url:
            try:
                conn.execute(
                    "UPDATE equipos SET bh_url = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (body.bh_url.strip(), id),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    try:
        from services.equipo_html_extractor import extract_from_html
        result = extract_from_html(html_content, categoria_hint=body.categoria_hint)
    except Exception:
        logger.exception("Error extrayendo specs del HTML (equipo %d)", id)
        raise HTTPException(500, "No se pudo procesar el HTML")

    return result


# ── Stream B: fotos/from-urls (batch) ────────────────────────────────────────
#
# Permite subir múltiples fotos desde URLs en un solo call. Reutiliza
# toda la lógica de admin_upload_foto_from_url (validate + download + store).

class FotosFromUrlsBody(BaseModel):
    urls: list[str]


@router.post("/admin/equipos/{equipo_id}/fotos/from-urls")
def admin_fotos_from_urls(
    equipo_id: int,
    body: FotosFromUrlsBody,
    request: Request,
) -> dict:
    """Descarga y sube a R2 varias fotos desde URLs en batch.

    Cada URL se procesa independientemente: un fallo individual no cancela
    el resto. Devuelve {ok: [...], errors: [...]}.
    """
    require_admin(request)

    urls = [u.strip() for u in (body.urls or []) if u.strip()]
    if not urls:
        raise HTTPException(400, "Lista de URLs vacía")
    if len(urls) > 20:
        raise HTTPException(400, "Máximo 20 URLs por llamada")

    cfg_pub = (os.getenv("R2_PUBLIC_BASE") or "").rstrip("/")

    ok_results: list[dict] = []
    error_results: list[dict] = []

    for url in urls:
        # Foto ya en R2 → saltear sin error
        if cfg_pub and url.startswith(cfg_pub + "/"):
            ok_results.append({"url": url, "public_url": url, "skipped": True})
            continue
        try:
            with media_http():
                _validate_external_image_url(url)
                raw_content, _raw_ctype = _download_image_bytes(url)

            with get_db() as conn:
                try:
                    with media_http():
                        asset = store_upload(
                            raw_content, kind="equipo",
                            derive_specs=EQUIPO_DERIVE_SPECS, conn=conn,
                        )
                    display = asset.variant("display")
                    _insert_equipo_foto(conn, equipo_id, display.url, display.key, asset.id)
                except Exception:
                    conn.rollback()
                    raise

            ok_results.append({
                "url": url,
                "public_url": display.url,
                "path": display.key,
                "size": display.bytes,
            })
        except Exception as exc:
            error_results.append({"url": url, "error": str(exc)})

    return {"ok": ok_results, "errors": error_results}
