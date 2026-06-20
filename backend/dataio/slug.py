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


def slug_unico(base: str, ocupados: set[str]) -> str:
    """Devuelve `base`, o `base-2`, `base-3`… hasta encontrar uno que no esté en
    `ocupados`. NO muta `ocupados` (el caller decide cuándo reservarlo). Fuente
    única de la regla de desambiguación de slugs (backfill + alta de equipo)."""
    if base not in ocupados:
        return base
    n = 2
    while f"{base}-{n}" in ocupados:
        n += 1
    return f"{base}-{n}"


def backfill_equipos_slug(conn) -> int:
    """Puebla los slugs faltantes (`slug IS NULL`, equipos no eliminados) usando
    el conn de la app (placeholders `?`, filas dict). Idempotente: no toca filas
    que ya tienen slug. NO crea la columna ni el constraint (eso es esquema →
    `init_db()` + migración) y NO commitea (el caller maneja la transacción).
    Devuelve cuántas filas pobló.

    Es la fuente única del backfill: la corren `init_db()` (bootstrap), el alta
    de equipo (slug en la creación) y la migración Alembic. Reemplaza al viejo
    self-heal que vivía DENTRO del export (un export, read-only por contrato, no
    debe mutar esquema/datos — #922)."""
    from database import marca_subquery  # lazy: evita import circular con dataio

    pendientes = conn.execute(f"""
        SELECT id, nombre, {marca_subquery('equipos')}, modelo FROM equipos
        WHERE slug IS NULL AND eliminado_at IS NULL
    """).fetchall()
    if not pendientes:
        return 0
    ocupados = {
        r["slug"]
        for r in conn.execute(
            "SELECT slug FROM equipos WHERE slug IS NOT NULL"
        ).fetchall()
    }
    for r in pendientes:
        base = equipo_slug(r["marca"], r["modelo"], r["nombre"]) or f"equipo-{r['id']}"
        slug = slug_unico(base, ocupados)
        ocupados.add(slug)
        conn.execute("UPDATE equipos SET slug = ? WHERE id = ?", (slug, r["id"]))
    return len(pendientes)
