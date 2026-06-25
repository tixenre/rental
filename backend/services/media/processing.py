"""Procesamiento de imágenes — funciones puras (sin framework, sin red, sin DB).

Movido verbatim de services/image_upload.py. Las funciones no lanzan
HTTPException ni MediaError — fallback al original si algo falla.
"""
import logging

logger = logging.getLogger(__name__)


def strip_exif_for_storage(raw: bytes, content_type: str) -> bytes:
    """Strip EXIF del original antes de guardarlo en R2 (privacidad: GPS, device info, timestamps).

    - Aplica exif_transpose para bake la orientación en los píxeles (la orientación queda
      correcta incluso sin EXIF) → las variantes derivadas del original almacenado son
      orientation-correct sin necesidad de exif_transpose extra.
    - Re-guarda sin metadata. Pérdida: JPEG q=95/WebP q=95 (imperceptible); PNG/GIF lossless.
    - Fallback al raw original si algo falla (safe: el pipeline sigue aunque el strip falle).
    """
    try:
        from PIL import Image, ImageOps
        from io import BytesIO

        img = Image.open(BytesIO(raw))
        img = ImageOps.exif_transpose(img)

        _FMT_MAP: dict[str, tuple[str, str | None]] = {
            "image/jpeg": ("JPEG", "RGB"),
            "image/png":  ("PNG",  None),
            "image/webp": ("WEBP", None),
            "image/gif":  ("GIF",  None),
            "image/avif": ("AVIF", None),
        }
        fmt, force_mode = _FMT_MAP.get(content_type, ("JPEG", "RGB"))

        if force_mode and img.mode != force_mode:
            img = img.convert(force_mode)

        out = BytesIO()
        if fmt == "JPEG":
            img.save(out, format="JPEG", quality=95, optimize=True)
        elif fmt == "WEBP":
            img.save(out, format="WEBP", quality=95)
        else:
            img.save(out, format=fmt)
        return out.getvalue()
    except Exception as e:  # noqa: BLE001
        logger.warning("strip_exif_for_storage: fallback al original (%s)", e)
        return raw


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


def _optimize_image(
    content: bytes, *, square: bool = True, fmt: str = "webp", max_width: int | None = None
) -> tuple[bytes, str, int, int]:
    """Optimiza la imagen y la guarda como WebP q=85 (o JPEG q=82 si fmt='jpeg').
    Devuelve (bytes, ct, w, h).
    Si algo falla, devuelve el contenido original como fallback.

    - `square=True` → fotos de EQUIPOS: trim + cuadrado + fondo blanco, lado `max_width` (default 1200).
    - `square=False` → branding/estudio (hero): mantiene aspect ratio, máx `max_width` (default 1600).

    `max_width` permite derivar variantes más chicas para srcset (ej. 'display-sm' a 600).
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

            TARGET_SIDE = max_width or 1200
            if img.width > TARGET_SIDE:
                img = img.resize((TARGET_SIDE, TARGET_SIDE), Image.Resampling.LANCZOS)
        else:
            if img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[-1])
                img = bg
            else:
                img = img.convert("RGB")

            MAX_SIDE = max_width or 1600
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


def generate_lqip(image_bytes: bytes) -> str | None:
    """Genera un LQIP (Low Quality Image Placeholder) como data URI base64.

    Redimensiona a 4×4px, guarda como JPEG q=20, codifica en base64.
    Resultado: data:image/jpeg;base64,... (~80-120 bytes).
    Se usa como fondo CSS mientras carga la variante CDN (blur-up).

    Fallback: devuelve None si PIL falla (safe — el caller ignora None).
    """
    try:
        from PIL import Image
        from io import BytesIO
        import base64

        img = Image.open(BytesIO(image_bytes))
        img = img.convert("RGB")
        # 4×4 es suficiente para un blur-up — < 100 bytes en base64
        img = img.resize((4, 4), Image.Resampling.LANCZOS)
        out = BytesIO()
        img.save(out, format="JPEG", quality=20, optimize=True)
        encoded = base64.b64encode(out.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception as e:  # noqa: BLE001
        logger.warning("generate_lqip: fallback None (%s)", e)
        return None


def _optimize_og_image(raw_content: bytes) -> tuple[bytes, str, str]:
    """Optimiza imagen para preview Open Graph (WhatsApp / IG / Facebook).

    Target: 1200x630 (recomendación de Facebook). Si la imagen no tiene
    ese aspect ratio (1.91:1), la centramos sobre fondo blanco y cubrimos.
    Se sirve como JPEG (mejor compresión que PNG para fotos).

    Retorna (bytes, content_type, ext).
    """
    from io import BytesIO
    from PIL import Image

    TARGET_W, TARGET_H = 1200, 630

    img = Image.open(BytesIO(raw_content))
    if img.mode in ("RGBA", "LA", "P"):
        # Aplanamos sobre fondo blanco (los OG images suelen rendererarse en
        # plataformas que no manejan transparencia bien).
        bg = Image.new("RGB", img.size, (255, 255, 255))
        img_rgba = img.convert("RGBA") if img.mode != "RGBA" else img
        bg.paste(img_rgba, mask=img_rgba.split()[-1])
        img = bg
    else:
        img = img.convert("RGB")

    # Cover: escalar y centrar para llenar 1200x630.
    src_ratio = img.width / img.height
    tgt_ratio = TARGET_W / TARGET_H
    if src_ratio > tgt_ratio:
        # Imagen más ancha que el target — recortar lados.
        new_h = TARGET_H
        new_w = int(img.width * (TARGET_H / img.height))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - TARGET_W) // 2
        img = img.crop((left, 0, left + TARGET_W, TARGET_H))
    else:
        # Imagen más alta — recortar top/bottom.
        new_w = TARGET_W
        new_h = int(img.height * (TARGET_W / img.width))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        top = (new_h - TARGET_H) // 2
        img = img.crop((0, top, TARGET_W, top + TARGET_H))

    out = BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue(), "image/jpeg", "jpg"
