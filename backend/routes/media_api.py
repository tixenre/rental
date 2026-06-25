"""Endpoint público de media por entidad — variantes de fotos para el frontend.

GET /api/media/entity/{kind}/{entity_id}
  Devuelve los assets de media de una entidad con sus variantes completas
  (name, url, width, height, content_type). Público — las URLs de variantes
  ya son CDN públicas.

  Soporta: kind="equipo" (equipo_fotos) | kind="estudio" (estudio_fotos).
  Legacy fallback: fotos sin media_id (subidas antes de F0a) devuelven una
  variante sintética "display" con la url almacenada (cero rotura).

  El frontend usa este endpoint en `useEntityMedia(kind, entityId)` para
  construir srcset con width/height reales (anti-CLS) vía `<ResponsiveImage>`.
"""
from fastapi import APIRouter, HTTPException

from database import get_db
from services.media.service import _validate_kind
from services.media.errors import MediaError

router = APIRouter()


def _load_variants(conn, media_id: int) -> list[dict]:
    """Carga las variantes de un media_asset desde media_variants."""
    rows = conn.execute(
        "SELECT name, url, width, height, content_type "
        "FROM media_variants WHERE asset_id = ? ORDER BY id",
        (media_id,),
    ).fetchall()
    return [
        {
            "name": r["name"],
            "url": r["url"],
            "width": r["width"] or 0,
            "height": r["height"] or 0,
            "content_type": r["content_type"] or "image/webp",
        }
        for r in rows
    ]


def _load_lqip(conn, media_id: int) -> str | None:
    """Lee el lqip del asset (data URI del blur-up placeholder). Null si no existe."""
    row = conn.execute(
        "SELECT lqip FROM media_assets WHERE id = ?", (media_id,)
    ).fetchone()
    if row:
        try:
            return row["lqip"]
        except (KeyError, IndexError):
            pass
    return None


def _build_asset(conn, row) -> dict:
    """Construye un asset con variants y lqip. Fallback legible para fotos pre-F0a."""
    media_id = row["media_id"]
    variants = _load_variants(conn, media_id) if media_id else []
    lqip = _load_lqip(conn, media_id) if media_id else None

    if not variants and row["url"]:
        variants = [{
            "name": "display",
            "url": row["url"],
            "width": 0,
            "height": 0,
            "content_type": "image/webp",
        }]

    return {
        "id": row["id"],
        "media_id": media_id,
        "orden": row["orden"],
        "es_principal": bool(row["es_principal"]),
        "lqip": lqip,
        "variants": variants,
    }


def _get_equipo_media(conn, entity_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id, url, media_id, orden, es_principal "
        "FROM equipo_fotos WHERE equipo_id = ? ORDER BY orden, id",
        (entity_id,),
    ).fetchall()
    return [_build_asset(conn, r) for r in rows]


def _get_estudio_media(conn, entity_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id, url, media_id, orden, es_principal "
        "FROM estudio_fotos WHERE estudio_id = ? ORDER BY orden, id",
        (entity_id,),
    ).fetchall()
    return [_build_asset(conn, r) for r in rows]


_KIND_HANDLERS = {
    "equipo": _get_equipo_media,
    "estudio": _get_estudio_media,
}


@router.get("/media/entity/{kind}/{entity_id}")
def get_entity_media(kind: str, entity_id: int):
    """Variantes de fotos de una entidad. Público (URLs ya son CDN-públicas).

    Devuelve:
      {assets: [{id, media_id, orden, es_principal, variants: [{name, url, width, height, content_type}]}]}

    Fallback: fotos sin media_id (pre-F0a) devuelven variant sintética con url directa.
    """
    try:
        _validate_kind(kind)
    except MediaError:
        raise HTTPException(400, f"kind inválido: {kind!r}")

    handler = _KIND_HANDLERS.get(kind)
    if handler is None:
        raise HTTPException(404, f"kind '{kind}' no soportado. Disponibles: {list(_KIND_HANDLERS)}")

    with get_db() as conn:
        assets = handler(conn, entity_id)

    return {"assets": assets}
