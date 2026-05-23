"""dataio/slug.py — Generación de slugs URL-friendly para equipos.

Convierte "Sony FX3 Cinema Camera" → "sony-fx3-cinema-camera".
Idempotente: slugify(slugify(x)) == slugify(x).
"""

import re
import unicodedata


def slugify(text: str, max_len: int = 80) -> str:
    """Convierte un string a slug ASCII separado por guiones.

    Reglas:
      - Lowercase
      - Quita acentos (NFKD + ASCII)
      - Reemplaza no-alfanuméricos por '-'
      - Colapsa guiones consecutivos
      - Trim '-' de los bordes
      - Trunca a max_len caracteres
    """
    if not text:
        return ""
    # Normalizar y quitar acentos
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    # Lowercase + reemplazar no-alfanuméricos
    lowered = ascii_text.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:max_len].rstrip("-")


def equipo_slug(marca: str | None, modelo: str | None, nombre: str | None = None) -> str:
    """Genera el slug canónico para un equipo a partir de marca+modelo.

    Si marca o modelo están vacíos, cae al nombre completo.
    Si todo está vacío, devuelve ''.
    """
    parts = [p for p in (marca, modelo) if p and p.strip()]
    base = " ".join(parts) if parts else (nombre or "")
    return slugify(base)
