"""Paquete media — pipeline no-destructivo de imágenes.

Núcleo puro sin FastAPI: lanza MediaError (errors.py), no HTTPException.
El adapter FastAPI vive en services/media_fastapi.py.
"""
from .errors import MediaError
from .models import MediaAsset, MediaVariant, DeriveSpec
from .specs import DISPLAY_KEEP_ASPECT, DISPLAY_SQUARE
from .service import store_upload, collect_asset_keys, purge_r2

__all__ = [
    "MediaError",
    "MediaAsset",
    "MediaVariant",
    "DeriveSpec",
    "DISPLAY_KEEP_ASPECT",
    "DISPLAY_SQUARE",
    "store_upload",
    "collect_asset_keys",
    "purge_r2",
]
