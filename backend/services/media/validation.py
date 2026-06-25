"""Validación de seguridad de uploads de imagen.

Defiende el pipeline de media de dos vectores antes de procesar cualquier byte:

- **Magic-bytes**: no se confía en la extensión ni en el content-type del cliente.
  PIL abre + `verify()` la estructura → si no es una imagen real (polyglot, archivo
  renombrado, basura) se rechaza con 400, en vez del fallback silencioso a jpeg.
- **Decompression-bomb**: un archivo chico puede expandir a gigapíxeles y tumbar el
  server por OOM. Se fija `Image.MAX_IMAGE_PIXELS` (PIL eleva `DecompressionBombError`
  al abrir algo por encima del tope) + un chequeo explícito de w×h.

Función pura, sin framework: eleva `MediaError`. La usa `service.store_upload`.
"""
import logging

from .errors import MediaError

logger = logging.getLogger(__name__)

# Tope anti decompression-bomb. 50 MP (~8660×5773) es holgado para fotos reales de
# cámara/celular y corta bombas. PIL eleva DecompressionBombError al abrir algo mayor.
MAX_PIXELS = 50_000_000

# Formatos aceptados (lo que PIL.Image.format puede devolver para un raster válido).
_FORMAT_TO_CT_EXT = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
    "GIF": ("image/gif", "gif"),
    "AVIF": ("image/avif", "avif"),
}

# Fija el cap global de PIL al importar el módulo (lo importa service.py → aplica a
# todo el pipeline). Global a propósito: evita togglear por-llamada (race en threads).
try:
    from PIL import Image as _PILImage

    _PILImage.MAX_IMAGE_PIXELS = MAX_PIXELS
except Exception:  # noqa: BLE001 — PIL puede no estar en algún contexto de test mínimo
    pass


def validate_and_detect(raw: bytes) -> tuple[str, str]:
    """Valida que `raw` sea una imagen real de formato permitido y devuelve (content_type, ext).

    Eleva MediaError(400) si está vacío, no es una imagen, o el formato no está permitido.
    Reemplaza al detector permisivo que caía a jpeg ante cualquier cosa.
    """
    if not raw:
        raise MediaError(400, "Archivo vacío")
    try:
        from PIL import Image
        from io import BytesIO
    except ImportError:
        raise MediaError(500, "PIL no instalado en el backend")

    try:
        with Image.open(BytesIO(raw)) as img:
            fmt = img.format
            w, h = img.size
            img.verify()  # valida la estructura sin decodificar todo el raster
    except MediaError:
        raise
    except Exception as e:  # noqa: BLE001 — DecompressionBombError, UnidentifiedImageError, etc.
        raise MediaError(400, f"El archivo no es una imagen válida ({e}).") from e

    if fmt not in _FORMAT_TO_CT_EXT:
        raise MediaError(
            400,
            f"Formato no permitido: {fmt or 'desconocido'}. Permitidos: JPEG, PNG, WEBP, GIF, AVIF.",
        )
    if w * h > MAX_PIXELS:
        raise MediaError(400, f"Imagen demasiado grande ({w}×{h} px). Máximo {MAX_PIXELS:,} píxeles.")
    return _FORMAT_TO_CT_EXT[fmt]
