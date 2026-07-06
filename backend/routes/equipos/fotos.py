"""Fotos / media de un equipo (#501 fase a — extraído de `core`).

Split #1258 (Corte A/B): la búsqueda externa de fotos (Firecrawl) vive en
`busqueda_fotos.py` y la extracción de specs desde HTML en
`specs_extraccion.py`. Acá queda: subida de fotos (archivo / URL, singular y
batch), galería (listar/borrar/reordenar) + los helpers compartidos entre
upload y galería (`_foto_path`/`_sync_principal_denorm`/etc. — no se separan,
un solo lado los usa a los dos) + diagnóstico de storage. Registra sus rutas
en el router compartido del paquete `routes.equipos`. Los helpers de R2 vienen
de `services.media.storage` (no de `core`); `core` mantiene su propio import
de `_r2_config`/`_delete_from_r2` porque `delete_equipo` también limpia el
blob scrapeado. `UploadFotoFromUrlInput` lo re-exporta el `__init__` del
paquete (lo consume `test_ssrf`).
"""
import logging
import os
import re
import unicodedata

from fastapi import HTTPException, Request
from pydantic import BaseModel

from auth.guards import require_admin
from database import get_db
from routes.equipos.core import router

logger = logging.getLogger(__name__)

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
        "FROM equipo_fotos WHERE equipo_id = %s ORDER BY orden, id",
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
        "SELECT media_id FROM equipo_fotos WHERE equipo_id = %s AND es_principal = TRUE LIMIT 1",
        (equipo_id,),
    ).fetchone()
    if not row or not row["media_id"]:
        return None
    v = conn.execute(
        "SELECT url FROM media_variants WHERE asset_id = %s AND name = 'display-sm' LIMIT 1",
        (row["media_id"],),
    ).fetchone()
    return v["url"] if v else None


def _principal_thumb_url(conn, equipo_id: int) -> str | None:
    """URL de la variante 'display-thumb' (160px) de la foto PRINCIPAL del equipo,
    para srcset en slots de ~48px. None si no existe (foto pre-backfill) → fallback seguro."""
    row = conn.execute(
        "SELECT media_id FROM equipo_fotos WHERE equipo_id = %s AND es_principal = TRUE LIMIT 1",
        (equipo_id,),
    ).fetchone()
    if not row or not row["media_id"]:
        return None
    v = conn.execute(
        "SELECT url FROM media_variants WHERE asset_id = %s AND name = 'display-thumb' LIMIT 1",
        (row["media_id"],),
    ).fetchone()
    return v["url"] if v else None


def _sync_principal_denorm(conn, equipo_id: int) -> None:
    """Sincroniza TODAS las columnas denormalizadas de la foto principal del equipo.

    Una sola UPDATE reemplaza los 3 sitios que antes actualizaban (url/sm/thumb) por separado.
    No commitea — el caller lo hace.
    """
    row = conn.execute(
        "SELECT url, media_id FROM equipo_fotos WHERE equipo_id = %s AND es_principal = TRUE LIMIT 1",
        (equipo_id,),
    ).fetchone()
    if not row:
        conn.execute(
            "UPDATE equipos SET foto_url = NULL, foto_url_sm = NULL, foto_url_thumb = NULL, "
            "foto_url_avif = NULL, foto_url_sm_avif = NULL, foto_url_thumb_avif = NULL, "
            "foto_lqip = NULL WHERE id = %s",
            (equipo_id,),
        )
        return

    principal_url = row["url"]
    media_id = row["media_id"]
    sm = thumb = avif = sm_avif = thumb_avif = lqip = None

    if media_id:
        for v in conn.execute(
            "SELECT name, url FROM media_variants WHERE asset_id = %s "
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
            "SELECT lqip FROM media_assets WHERE id = %s", (media_id,)
        ).fetchone()
        lqip = lqip_row["lqip"] if lqip_row else None

    conn.execute(
        "UPDATE equipos SET foto_url = %s, foto_url_sm = %s, foto_url_thumb = %s, "
        "foto_url_avif = %s, foto_url_sm_avif = %s, foto_url_thumb_avif = %s, foto_lqip = %s "
        "WHERE id = %s",
        (principal_url, sm, thumb, avif, sm_avif, thumb_avif, lqip, equipo_id),
    )


def _insert_equipo_foto(conn, equipo_id: int, url: str, path: str, media_id: int | None = None) -> dict:
    """Inserta una fila en equipo_fotos y sincroniza equipos.foto_url con la principal.
    La primera foto del equipo se marca como principal automáticamente.
    """
    cur = conn.execute(
        "SELECT COALESCE(MAX(orden), -1) + 1 AS next_orden FROM equipo_fotos WHERE equipo_id = %s",
        (equipo_id,),
    )
    orden = cur.fetchone()["next_orden"]

    cur2 = conn.execute("SELECT COUNT(*) AS cnt FROM equipo_fotos WHERE equipo_id = %s", (equipo_id,))
    is_first = cur2.fetchone()["cnt"] == 0

    conn.execute(
        "INSERT INTO equipo_fotos (equipo_id, url, path, media_id, orden, es_principal) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (equipo_id, url, path, media_id, orden, is_first),
    )

    if is_first:
        _sync_principal_denorm(conn, equipo_id)

    conn.commit()

    cur3 = conn.execute(
        "SELECT id, url, path, media_id, orden, es_principal, created_at "
        "FROM equipo_fotos WHERE equipo_id = %s ORDER BY id DESC LIMIT 1",
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
        eq = conn.execute("SELECT id FROM equipos WHERE id = %s", (equipo_id,)).fetchone()
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
            eq = conn.execute("SELECT id FROM equipos WHERE id = %s", (equipo_id,)).fetchone()
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


def _agregar_foto_desde_url(conn, equipo_id: int, url: str, cfg_pub: str) -> dict:
    """Descarga una URL externa, la sube a R2 y la agrega a la galería.
    Fuente única para el endpoint singular y el batch (#1051 Stream B)."""
    if cfg_pub and url.startswith(cfg_pub + "/"):
        raise HTTPException(400, "La URL ya está en el bucket — subí el archivo directamente")

    with media_http():
        _validate_external_image_url(url)
        raw, _raw_ctype = _download_image_bytes(url)
        asset = store_upload(raw, kind="equipo", derive_specs=EQUIPO_DERIVE_SPECS, conn=conn)
    display = asset.variant("display")
    return _insert_equipo_foto(conn, equipo_id, display.url, display.key, asset.id)


@router.post("/admin/equipos/{equipo_id}/fotos/from-url", status_code=201)
def upload_equipo_foto_from_url(equipo_id: int, body: EquipoFotoFromUrlBody, request: Request):
    """Descarga URL externa y la agrega a la galería del equipo."""
    require_admin(request)

    url = (body.url or "").strip()
    if not url:
        raise HTTPException(400, "URL vacía")

    cfg_pub = (os.getenv("R2_PUBLIC_BASE") or "").rstrip("/")

    with get_db() as conn:
        try:
            eq = conn.execute("SELECT id FROM equipos WHERE id = %s", (equipo_id,)).fetchone()
            if not eq:
                raise HTTPException(404, "Equipo no encontrado")
            foto = _agregar_foto_desde_url(conn, equipo_id, url, cfg_pub)
        except Exception:
            conn.rollback()
            raise

    return foto


class EquipoFotosFromUrlsBody(BaseModel):
    urls: list[str]


@router.post("/admin/equipos/{equipo_id}/fotos/from-urls", status_code=201)
def upload_equipo_fotos_from_urls(equipo_id: int, body: EquipoFotosFromUrlsBody, request: Request):
    """Batch de `fotos/from-url` (#1051 Stream B): agrega hasta 20 fotos de un
    saque — típicamente la galería completa de un HTML recién enriquecido
    (`enriquecer-from-html` devuelve `foto_candidates`). Best-effort por URL
    (mismo criterio que `/admin/equipos/buscar-fotos`): una que falla no
    aborta el resto — se reporta en `fallidas` en vez de perder el batch entero.

    Returns: {agregadas: EquipoFoto[], fallidas: [{url, error}]}
    """
    require_admin(request)

    urls = [u.strip() for u in (body.urls or []) if u and u.strip()]
    if not urls:
        raise HTTPException(400, "Sin URLs")
    if len(urls) > 20:
        raise HTTPException(400, "Máximo 20 URLs por batch")

    cfg_pub = (os.getenv("R2_PUBLIC_BASE") or "").rstrip("/")
    agregadas: list[dict] = []
    fallidas: list[dict] = []

    with get_db() as conn:
        eq = conn.execute("SELECT id FROM equipos WHERE id = %s", (equipo_id,)).fetchone()
        if not eq:
            raise HTTPException(404, "Equipo no encontrado")

        for url in urls:
            try:
                foto = _agregar_foto_desde_url(conn, equipo_id, url, cfg_pub)
                agregadas.append(foto)
            except HTTPException as e:
                conn.rollback()
                fallidas.append({"url": url, "error": str(e.detail)})
            except Exception as exc:
                conn.rollback()
                logger.warning("fotos/from-urls: fallo con %s: %s", url, exc)
                fallidas.append({"url": url, "error": "no se pudo descargar/procesar"})

    return {"agregadas": agregadas, "fallidas": fallidas}


@router.delete("/admin/equipos/{equipo_id}/fotos/{foto_id}")
def delete_equipo_foto(equipo_id: int, foto_id: int, request: Request):
    require_admin(request)

    with get_db() as conn:
        cur = conn.execute(
            "SELECT url, path, media_id, es_principal FROM equipo_fotos "
            "WHERE id = %s AND equipo_id = %s",
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

        conn.execute("DELETE FROM equipo_fotos WHERE id = %s", (foto_id,))
        if media_id:
            conn.execute("DELETE FROM media_assets WHERE id = %s", (media_id,))

        # Si era la principal, promover la siguiente en orden
        if was_principal:
            next_foto = conn.execute(
                "SELECT id, url FROM equipo_fotos WHERE equipo_id = %s ORDER BY orden, id LIMIT 1",
                (equipo_id,),
            ).fetchone()
            if next_foto:
                conn.execute(
                    "UPDATE equipo_fotos SET es_principal = TRUE WHERE id = %s", (next_foto["id"],)
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
                "UPDATE equipo_fotos SET orden = %s, es_principal = %s "
                "WHERE id = %s AND equipo_id = %s",
                (f.orden, f.es_principal, f.id, equipo_id),
            )
            if f.es_principal:
                row = conn.execute(
                    "SELECT url FROM equipo_fotos WHERE id = %s", (f.id,)
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
