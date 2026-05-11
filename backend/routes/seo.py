"""
routes/seo.py — sitemap.xml dinámico para SEO.

Lista las URLs públicas que queremos que Google indexe:
- Home / catálogo
- Páginas estáticas (Estudio, FAQ)
- Detalle de cada equipo visible

NO incluye:
- /admin/* (info privada)
- /cliente/* (info privada)
- Equipos ocultos (visible=false)
"""

from __future__ import annotations

import os
from datetime import datetime
from xml.sax.saxutils import escape

from fastapi import APIRouter, Response

from database import get_db

router = APIRouter()

# URL pública del sitio. Override con env var SITE_URL si se cambia el dominio.
SITE_URL = os.getenv("SITE_URL", "https://ramblarental.com").rstrip("/")


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap():
    """Sitemap XML compatible con Google / Bing.

    Spec: https://www.sitemaps.org/protocol.html
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Páginas estáticas con priority/changefreq.
    # NO incluimos /equipo/{id} todavía: hoy no es route real de TanStack,
    # es un modal abierto sobre /. Google vería duplicados de la home.
    # Cuando se haga SSR/SSG por equipo, agregar dynamic urls acá.
    urls: list[dict] = [
        {"loc": f"{SITE_URL}/", "lastmod": today, "changefreq": "daily", "priority": "1.0"},
        {"loc": f"{SITE_URL}/estudio", "lastmod": today, "changefreq": "monthly", "priority": "0.8"},
        {"loc": f"{SITE_URL}/preguntas-frecuentes", "lastmod": today, "changefreq": "monthly", "priority": "0.6"},
    ]

    # Construir XML.
    body = ['<?xml version="1.0" encoding="UTF-8"?>']
    body.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for u in urls:
        body.append("  <url>")
        body.append(f"    <loc>{escape(u['loc'])}</loc>")
        body.append(f"    <lastmod>{u['lastmod']}</lastmod>")
        body.append(f"    <changefreq>{u['changefreq']}</changefreq>")
        body.append(f"    <priority>{u['priority']}</priority>")
        body.append("  </url>")
    body.append("</urlset>")

    return Response(
        content="\n".join(body),
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},  # 1h cache
    )
