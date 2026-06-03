"""Procesamiento de imágenes — funciones puras (sin framework, sin red, sin DB).

Movido verbatim de services/image_upload.py. Las funciones no lanzan
HTTPException ni MediaError — fallback al original si algo falla.
"""
import logging

logger = logging.getLogger(__name__)


def _ext_from_ctype(ct: str) -> str:
    ct = (ct or "").lower()
    if "png" in ct:  return "png"
    if "webp" in ct: return "webp"
    if "avif" in ct: return "avif"
    if "gif" in ct:  return "gif"
    return "jpg"


def _trim_and_square(img, padding_pct: float = 0.06):
    """Recorta bordes (transparentes o casi blancos) y empareja a cuadrado
    con fondo blanco + padding.

    Args:
        img: PIL.Image (RGB o RGBA)
        padding_pct: porcentaje de padding alrededor del bbox encontrado.
    Returns:
        PIL.Image en modo RGB cuadrado con fondo blanco.
    """
    from PIL import Image, ImageChops

    if img.mode == "RGBA":
        bbox = img.split()[-1].getbbox()
        if bbox:
            img = img.crop(bbox)
        img_rgb = Image.new("RGB", img.size, (255, 255, 255))
        img_rgb.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = img_rgb
    else:
        img = img.convert("RGB")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        diff = ImageChops.difference(img, bg)
        diff = ImageChops.add(diff, diff, 2.0, -30)
        bbox = diff.getbbox()
        if bbox:
            img = img.crop(bbox)

    w, h = img.size
    side = max(w, h)
    pad = int(side * padding_pct)
    canvas_side = side + 2 * pad
    canvas = Image.new("RGB", (canvas_side, canvas_side), (255, 255, 255))
    offset = ((canvas_side - w) // 2, (canvas_side - h) // 2)
    canvas.paste(img, offset)
    return canvas


def _optimize_image(content: bytes, *, square: bool = True, fmt: str = "webp") -> tuple[bytes, str, int, int]:
    """Optimiza la imagen y la guarda como WebP q=85 (o JPEG q=82 si fmt='jpeg').
    Devuelve (bytes, ct, w, h).
    Si algo falla, devuelve el contenido original como fallback.

    - `square=True` → fotos de EQUIPOS: trim + cuadrado + fondo blanco + 1200×1200.
    - `square=False` → branding/estudio (hero): mantiene aspect ratio, max 1600px.
    """
    try:
        from PIL import Image, ImageOps
        from io import BytesIO
    except ImportError:
        return content, "image/jpeg", 0, 0

    try:
        img = Image.open(BytesIO(content))
        img = ImageOps.exif_transpose(img)

        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.mode else "RGB")

        if square:
            try:
                img = _trim_and_square(img, padding_pct=0.06)
            except Exception as e:
                logger.warning("optimize_image: trim_and_square falló, sigo sin trim: %s", e)

            TARGET_SIDE = 1200
            if img.width > TARGET_SIDE:
                img = img.resize((TARGET_SIDE, TARGET_SIDE), Image.Resampling.LANCZOS)
        else:
            if img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[-1])
                img = bg
            else:
                img = img.convert("RGB")

            MAX_SIDE = 1600
            longest = max(img.width, img.height)
            if longest > MAX_SIDE:
                scale = MAX_SIDE / longest
                img = img.resize(
                    (round(img.width * scale), round(img.height * scale)),
                    Image.Resampling.LANCZOS,
                )

        out = __import__("io").BytesIO()
        if fmt == "jpeg":
            # JPEG no soporta alpha: aplanar a RGB por las dudas (el path square ya
            # devuelve RGB, pero si el trim falló podría quedar RGBA).
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(out, format="JPEG", quality=82, optimize=True, progressive=True)
            return out.getvalue(), "image/jpeg", img.width, img.height
        img.save(out, format="WEBP", quality=85, method=6)
        return out.getvalue(), "image/webp", img.width, img.height
    except Exception as e:
        logger.warning("optimize_image: fallback (no se pudo optimizar): %s", e, exc_info=True)
        return content, "image/jpeg", 0, 0
