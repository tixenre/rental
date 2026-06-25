"""Endpoints del dashboard de media (back-office, F0f).

GET  /admin/media/stats        — métricas: total assets, variantes, huérfanos, bytes.
POST /admin/media/gc           — ejecuta reconcile_media (dry_run param).
POST /admin/media/rederive/{id} — re-deriva variantes de un asset desde el original.

Todos requieren autenticación de admin (admin_guard.require_admin).
"""
import logging

from fastapi import APIRouter, Request, HTTPException

from database import get_db
from services.media.errors import MediaError
from services.media.gc import reconcile_media, rederive_variants, _find_orphan_ids
from services.media.specs import (
    DISPLAY_KEEP_ASPECT, DISPLAY_KEEP_ASPECT_SM,
    DISPLAY_SQUARE, DISPLAY_SQUARE_SM, DISPLAY_SQUARE_THUMB,
    DISPLAY_KEEP_ASPECT_AVIF, DISPLAY_KEEP_ASPECT_SM_AVIF,
    DISPLAY_SQUARE_AVIF, DISPLAY_SQUARE_SM_AVIF, DISPLAY_SQUARE_THUMB_AVIF,
    OG_SQUARE_JPEG,
)

# Specs completos para re-derivar: el admin no sabe el kind, pide todos.
# El pipeline es idempotente — si un spec no aplica por aspect ratio, no rompe.
# INCLUYE las variantes AVIF (espeja EQUIPO_DERIVE_SPECS): sin ellas, re-derivar
# un asset desde el back-office regeneraba solo webp y PERDÍA el AVIF → el catálogo
# caía al fallback webp para ese equipo (#1054). No quitar las AVIF de esta lista.
_ALL_DERIVE_SPECS = [
    DISPLAY_KEEP_ASPECT, DISPLAY_KEEP_ASPECT_SM,
    DISPLAY_SQUARE, DISPLAY_SQUARE_SM, DISPLAY_SQUARE_THUMB,
    DISPLAY_KEEP_ASPECT_AVIF, DISPLAY_KEEP_ASPECT_SM_AVIF,
    DISPLAY_SQUARE_AVIF, DISPLAY_SQUARE_SM_AVIF, DISPLAY_SQUARE_THUMB_AVIF,
    OG_SQUARE_JPEG,
]

router = APIRouter(tags=["admin"])
logger = logging.getLogger(__name__)


@router.get("/admin/media/stats")
def get_media_stats(request: Request):
    """Resumen de estado del sistema de media."""
    try:
        from admin_guard import require_admin
        require_admin(request)

        with get_db() as conn:
            total_assets = conn.execute(
                "SELECT COUNT(*) AS n FROM media_assets"
            ).fetchone()["n"]

            total_variants = conn.execute(
                "SELECT COUNT(*) AS n FROM media_variants"
            ).fetchone()["n"]

            total_bytes_row = conn.execute(
                "SELECT COALESCE(SUM(bytes), 0) AS b FROM media_assets WHERE bytes IS NOT NULL"
            ).fetchone()
            total_bytes = total_bytes_row["b"] if total_bytes_row else 0

            assets_with_lqip = conn.execute(
                "SELECT COUNT(*) AS n FROM media_assets WHERE lqip IS NOT NULL"
            ).fetchone()["n"]

            orphan_ids = _find_orphan_ids(conn)
            orphan_count = len(orphan_ids)

            assets_no_variants = conn.execute(
                """
                SELECT COUNT(*) AS n
                FROM media_assets ma
                WHERE NOT EXISTS (
                    SELECT 1 FROM media_variants mv WHERE mv.asset_id = ma.id
                )
                AND ma.original_key IS NOT NULL
                """
            ).fetchone()["n"]

        return {
            "total_assets": total_assets,
            "total_variants": total_variants,
            "total_bytes": total_bytes,
            "assets_with_lqip": assets_with_lqip,
            "orphans": orphan_count,
            "assets_no_variants": assets_no_variants,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("get_media_stats falló")
        raise HTTPException(500, detail=f"{type(exc).__name__}: {exc}")


@router.post("/admin/media/gc")
async def run_media_gc(request: Request):
    """Ejecuta GC sobre media huérfana.

    Body (opcional):
      dry_run: bool (default true)
      kind: str (default null = todos)

    dry_run=true (default) solo detecta, no borra.
    """
    try:
        from admin_guard import require_admin
        require_admin(request)

        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        dry_run: bool = body.get("dry_run", True)
        kind: str | None = body.get("kind", None)

        with get_db() as conn:
            result = reconcile_media(conn, kind=kind, dry_run=dry_run)
            if not dry_run:
                try:
                    conn.connection.commit()
                except Exception:
                    pass

        return result.to_dict()

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("run_media_gc falló")
        raise HTTPException(500, detail=f"{type(exc).__name__}: {exc}")


@router.post("/admin/media/rederive/{asset_id}")
def rederive_asset(request: Request, asset_id: int):
    """Re-deriva las variantes de un asset desde su original privado.

    Útil cuando los derive_specs cambiaron o una variante quedó corrupta.
    """
    try:
        from admin_guard import require_admin
        require_admin(request)

        # Verificar que R2 esté configurado (bucket requerido).
        import os
        if not os.getenv("R2_BUCKET"):
            raise HTTPException(503, "R2 no configurado — no se puede re-derivar")

        with get_db() as conn:
            variants = rederive_variants(asset_id, derive_specs=_ALL_DERIVE_SPECS, conn=conn)
            try:
                conn.connection.commit()
            except Exception:
                pass

        return {
            "asset_id": asset_id,
            "variants_derived": len(variants),
            "variants": [
                {"name": v.name, "url": v.url, "width": v.width, "height": v.height}
                for v in variants
            ],
        }

    except HTTPException:
        raise
    except MediaError as e:
        raise HTTPException(e.status, e.detail)
    except Exception as exc:
        logger.exception("rederive_asset falló (asset_id=%s)", asset_id)
        raise HTTPException(500, detail=f"{type(exc).__name__}: {exc}")
