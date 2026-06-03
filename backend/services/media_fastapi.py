"""Adapter FastAPI para el módulo media.

Mapea MediaError → HTTPException(status, detail) 1:1, para que las rutas
queden limpias y la respuesta HTTP sea idéntica al módulo legacy image_upload.
"""
from contextlib import contextmanager

from fastapi import HTTPException

from services.media.errors import MediaError


@contextmanager
def media_http():
    """Context manager que convierte MediaError en HTTPException."""
    try:
        yield
    except MediaError as e:
        raise HTTPException(status_code=e.status, detail=e.detail) from e
