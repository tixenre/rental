"""Presets de variantes de uso frecuente."""
from .models import DeriveSpec

# Foto de branding / hero / estudio: mantiene aspect ratio, máx 1600px.
DISPLAY_KEEP_ASPECT = DeriveSpec(name="display", square=False)

# Variante chica de la foto hero/estudio para srcset (hero en mobile, donde la
# imagen se ve a ~400-500px): mantiene aspect ratio, máx 800px. El navegador elige
# `display-sm` en pantallas chicas y `display` en grandes → ~4× menos bytes en mobile.
# Acompaña a DISPLAY_KEEP_ASPECT.
DISPLAY_KEEP_ASPECT_SM = DeriveSpec(name="display-sm", square=False, max_width=800)

# Foto de equipo / catálogo: cuadrada 1200×1200 con fondo blanco.
DISPLAY_SQUARE = DeriveSpec(name="display", square=True)

# Variante chica de la foto de equipo para srcset (catálogo en mobile, donde la card
# se ve a ~300-400px): cuadrada 600×600. El navegador elige `display-sm` en pantallas
# chicas y `display` en grandes → baja ~4× los bytes en mobile. Acompaña a DISPLAY_SQUARE.
DISPLAY_SQUARE_SM = DeriveSpec(name="display-sm", square=True, max_width=600)

# Miniatura para slots muy chicos del catálogo (~48px): cuadrada 160×160. El navegador
# elige esta variante en slots de 48px, evitando bajar los 600px de display-sm.
DISPLAY_SQUARE_THUMB = DeriveSpec(name="display-thumb", square=True, max_width=160)

# Variante OG para previews de WhatsApp/redes: misma foto cuadrada que `display`
# pero en JPEG (WhatsApp no renderiza webp de forma confiable). Se inyecta en
# og:image. La web sigue usando `display` (webp) — esto es solo para crawlers.
OG_SQUARE_JPEG = DeriveSpec(name="og", square=True, fmt="jpeg")
