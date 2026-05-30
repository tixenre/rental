"""Configuración general de la app — fuente única de datos de config.

Acá viven constantes de configuración transversales (no atadas a un router
puntual) para que cualquier consumidor las importe de un módulo neutral en
vez de acoplarse a otro router. Ej.: `SITE_URL` la usan SEO, los mails y
cualquier link al sitio que se genere server-side.
"""

import os

# URL pública del sitio. Override con env var SITE_URL si se cambia el dominio.
SITE_URL = os.getenv("SITE_URL", "https://ramblarental.com").rstrip("/")
