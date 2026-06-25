"""Paquete media — pipeline no-destructivo de imágenes.

Núcleo puro sin FastAPI: lanza MediaError (errors.py), no HTTPException.
El adapter FastAPI vive en services/media_fastapi.py.
"""
from .errors import MediaError
from .models import MediaAsset, MediaVariant, DeriveSpec
from .specs import (
    DISPLAY_KEEP_ASPECT,
    DISPLAY_KEEP_ASPECT_SM,
    DISPLAY_KEEP_ASPECT_AVIF,
    DISPLAY_KEEP_ASPECT_SM_AVIF,
    DISPLAY_SQUARE,
    DISPLAY_SQUARE_SM,
    DISPLAY_SQUARE_THUMB,
    DISPLAY_SQUARE_AVIF,
    DISPLAY_SQUARE_SM_AVIF,
    OG_SQUARE_JPEG,
    EQUIPO_DERIVE_SPECS,
)
from .service import store_upload, collect_asset_keys, purge_r2

__all__ = [
    "MediaError",
    "MediaAsset",
    "MediaVariant",
    "DeriveSpec",
    "DISPLAY_KEEP_ASPECT",
    "DISPLAY_KEEP_ASPECT_SM",
    "DISPLAY_KEEP_ASPECT_AVIF",
    "DISPLAY_KEEP_ASPECT_SM_AVIF",
    "DISPLAY_SQUARE",
    "DISPLAY_SQUARE_SM",
    "DISPLAY_SQUARE_THUMB",
    "DISPLAY_SQUARE_AVIF",
    "DISPLAY_SQUARE_SM_AVIF",
    "OG_SQUARE_JPEG",
    "EQUIPO_DERIVE_SPECS",
    "store_upload",
    "collect_asset_keys",
    "purge_r2",
]
