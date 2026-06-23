"""Presets de variantes de uso frecuente."""
from .models import DeriveSpec

# Foto de branding / hero / estudio: mantiene aspect ratio, máx 1600px.
DISPLAY_KEEP_ASPECT = DeriveSpec(name="display", square=False)

# Foto de equipo / catálogo: cuadrada 1200×1200 con fondo blanco.
DISPLAY_SQUARE = DeriveSpec(name="display", square=True)

# Variante chica de la foto de equipo para srcset (catálogo en mobile, donde la card
# se ve a ~300-400px): cuadrada 600×600. El navegador elige `display-sm` en pantallas
# chicas y `display` en grandes → baja ~4× los bytes en mobile. Acompaña a DISPLAY_SQUARE.
DISPLAY_SQUARE_SM = DeriveSpec(name="display-sm", square=True, max_width=600)

# Variante OG para previews de WhatsApp/redes: misma foto cuadrada que `display`
# pero en JPEG (WhatsApp no renderiza webp de forma confiable). Se inyecta en
# og:image. La web sigue usando `display` (webp) — esto es solo para crawlers.
OG_SQUARE_JPEG = DeriveSpec(name="og", square=True, fmt="jpeg")
