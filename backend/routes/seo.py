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
    urls: list[dict] = [
        {"loc": f"{SITE_URL}/", "lastmod": today, "changefreq": "daily", "priority": "1.0"},
        {"loc": f"{SITE_URL}/estudio", "lastmod": today, "changefreq": "monthly", "priority": "0.8"},
        {"loc": f"{SITE_URL}/preguntas-frecuentes", "lastmod": today, "changefreq": "monthly", "priority": "0.6"},
    ]

    # Detalle por equipo: cada uno tiene URL única indexable (PR #107).
    # Si la BD no está disponible, devolvemos sitemap parcial con solo
    # estáticas — Google reintenta, mejor que un 500.
    try:
        conn = get_db()
        try:
            rows = conn.execute("""
                SELECT id,
                       COALESCE(updated_at, created_at) AS lastmod
                FROM equipos
                WHERE COALESCE(visible_catalogo, true) = true
                ORDER BY id
            """).fetchall()
        finally:
            conn.close()

        for r in rows:
            lastmod_raw = r["lastmod"]
            lastmod = (
                lastmod_raw.strftime("%Y-%m-%d")
                if hasattr(lastmod_raw, "strftime")
                else today
            )
            urls.append({
                "loc": f"{SITE_URL}/equipo/{r['id']}",
                "lastmod": lastmod,
                "changefreq": "weekly",
                "priority": "0.7",
            })
    except Exception:
        pass

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
