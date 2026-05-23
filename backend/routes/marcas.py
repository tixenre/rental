"""
routes/marcas.py — CRUD de marcas (brands).
"""

import re
import time
import unicodedata
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from database import get_db, row_to_dict
from admin_guard import require_admin

router = APIRouter()


def _logo_path(marca_id: int, nombre: str, ext: str) -> str:
    """Genera path R2 para el logo: marcas/{id}_{slug}/logo-{ts}.{ext}.

    El timestamp en el nombre del archivo evita el problema del cache
    inmutable: R2 sirve los assets con `Cache-Control: immutable max-age=1y`,
    así que si dos uploads usan el mismo path el navegador sigue mostrando
    el viejo durante un año. Con timestamp cada upload tiene URL nueva.
    El archivo anterior queda como huérfano en R2 (cleanup futuro si pesa).
    """
    slug = unicodedata.normalize("NFKD", nombre or "").encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")[:50]
    folder = f"{marca_id}_{slug}" if slug else str(marca_id)
    ts = int(time.time())
    return f"marcas/{folder}/logo-{ts}.{ext}"


# ── Pydantic Models ──────────────────────────────────────────────────────────

class MarcaAdmin(BaseModel):
    id: int
    nombre: str
    logo_url: Optional[str] = None
    visible: bool
    destacada: bool = False
    orden: int
    total: int


class MarcaPatch(BaseModel):
    nombre: Optional[str] = None
    logo_url: Optional[str] = None
    visible: Optional[bool] = None
    destacada: Optional[bool] = None
    orden: Optional[int] = None


class MarcasReorderRequest(BaseModel):
    marcas: list[dict]  # [{"id": 1, "orden": 2}, ...]


class MarcaMergeRequest(BaseModel):
    source_id: int  # marca a eliminar (sus equipos van a target)
    target_id: int  # marca destino (recibe los equipos de source)


# ── Public API ───────────────────────────────────────────────────────────────

@router.get("/marcas")
def list_marcas():
    """Lista marcas visibles ordenadas por orden manual, después por
    popularidad automática (#131), después alfabético.

    El `orden` manual (default 100) sigue siendo override — el admin
    puede forzar marcas específicas arriba bajándole el número. Si
    todas tienen orden=100, gana la popularidad real (cant_pedidos +
    ingreso, calculado por el ranking service).

    El campo `destacada` (issue #288) lo lee el frontend para curar el
    BrandCarousel del home: si hay marcas con destacada=true las muestra,
    sino fallback al algoritmo automático de top N por count."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT id, nombre, logo_url, destacada, orden,
                   popularidad_score, created_at, updated_at
            FROM marcas
            WHERE visible = TRUE
            ORDER BY orden ASC, popularidad_score DESC, nombre ASC
        """).fetchall()
        marcas = [row_to_dict(r) for r in rows]
        return {"items": marcas}
    finally:
        conn.close()


# ── Admin API ────────────────────────────────────────────────────────────────

@router.get("/admin/marcas")
def admin_list_marcas(request: Request):
    """Lista todas las marcas (visible/invisible) con count de equipos y flag `destacada`."""
    require_admin(request)
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT
                m.id, m.nombre, m.logo_url, m.visible, m.destacada, m.orden,
                COUNT(e.id) as total
            FROM marcas m
            LEFT JOIN equipos e ON e.brand_id = m.id
            GROUP BY m.id, m.nombre, m.logo_url, m.visible, m.destacada, m.orden
            ORDER BY m.orden ASC, m.nombre ASC
        """).fetchall()
        marcas = [dict(row) for row in rows]
        return {"items": marcas}
    finally:
        conn.close()


@router.patch("/admin/marcas/{marca_id}")
def admin_update_marca(marca_id: int, patch: MarcaPatch, request: Request):
    """Actualiza una marca (nombre, logo_url, visible, orden)."""
    require_admin(request)
    conn = get_db()
    try:
        # Verificar que existe
        existing = conn.execute("SELECT id FROM marcas WHERE id = %s", (marca_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Marca no encontrada")

        # Construir SET dinámico
        updates = {}
        if patch.nombre is not None:
            updates["nombre"] = patch.nombre
        if patch.logo_url is not None:
            updates["logo_url"] = patch.logo_url
        if patch.visible is not None:
            updates["visible"] = patch.visible
        if patch.destacada is not None:
            updates["destacada"] = patch.destacada
        if patch.orden is not None:
            updates["orden"] = patch.orden

        if not updates:
            raise HTTPException(status_code=400, detail="No hay campos para actualizar")

        updates["updated_at"] = "NOW()"

        set_clause = ", ".join([f"{k} = %s" if k != 'updated_at' else f"{k} = NOW()" for k in updates.keys()])
        values = [v for k, v in updates.items() if k != "updated_at"]
        values.append(marca_id)

        conn.execute(f"""
            UPDATE marcas SET {set_clause} WHERE id = %s
        """, values)

        # brand_id (FK) es la fuente única del nombre de marca; renombrar la
        # fila en `marcas` ya se refleja en todos los equipos vía el join.

        # Devolver la marca actualizada
        row = conn.execute("""
            SELECT
                m.id, m.nombre, m.logo_url, m.visible, m.destacada, m.orden,
                COUNT(e.id) as total
            FROM marcas m
            LEFT JOIN equipos e ON e.brand_id = m.id
            WHERE m.id = %s
            GROUP BY m.id, m.nombre, m.logo_url, m.visible, m.destacada, m.orden
        """, (marca_id,)).fetchone()

        conn.commit()
        return dict(row) if row else {}
    finally:
        conn.close()


@router.post("/admin/marcas/merge")
def admin_merge_marcas(req: MarcaMergeRequest, request: Request):
    """Fusiona dos marcas duplicadas: reasigna todos los equipos de
    `source_id` a `target_id` (vía `brand_id` y `marca` TEXT) y borra source.
    Útil para consolidar "Red" + "RED DIGITAL CINEMA" → una sola marca.
    """
    require_admin(request)
    if req.source_id == req.target_id:
        raise HTTPException(400, "source_id y target_id no pueden ser iguales")
    conn = get_db()
    try:
        # Validar que ambas existen
        rows = conn.execute(
            "SELECT id, nombre FROM marcas WHERE id IN (%s, %s)",
            (req.source_id, req.target_id),
        ).fetchall()
        existing = {r["id"]: r["nombre"] for r in rows}
        if req.source_id not in existing:
            raise HTTPException(404, f"Marca source {req.source_id} no encontrada")
        if req.target_id not in existing:
            raise HTTPException(404, f"Marca target {req.target_id} no encontrada")

        target_nombre = existing[req.target_id]

        # Reasignar brand_id (FK)
        conn.execute(
            "UPDATE equipos SET brand_id = %s WHERE brand_id = %s",
            (req.target_id, req.source_id),
        )
        # Sincronizar el TEXT marca por si quedó desincronizado
        conn.execute(
            "UPDATE equipos SET marca = %s WHERE brand_id = %s",
            (target_nombre, req.target_id),
        )
        # Borrar la source
        conn.execute("DELETE FROM marcas WHERE id = %s", (req.source_id,))
        conn.commit()
        return {"ok": True, "merged_into": target_nombre}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f"Error al fusionar marcas: {e}")
    finally:
        conn.close()


@router.post("/admin/marcas/reorder")
def admin_reorder_marcas(req: MarcasReorderRequest, request: Request):
    """Actualiza el orden de múltiples marcas."""
    require_admin(request)
    conn = get_db()
    try:
        for item in req.marcas:
            marca_id = item.get("id")
            orden = item.get("orden")
            if marca_id is None or orden is None:
                raise HTTPException(status_code=400, detail="Items deben tener 'id' y 'orden'")
            conn.execute("""
                UPDATE marcas SET orden = %s, updated_at = NOW() WHERE id = %s
            """, (orden, marca_id))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.delete("/admin/marcas/{marca_id}", status_code=204)
def admin_delete_marca(marca_id: int, request: Request):
    """Borra una marca. Rechaza si tiene equipos asociados — primero hay que
    fusionar (POST /admin/marcas/merge) o reasignar los equipos."""
    require_admin(request)
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id, nombre FROM marcas WHERE id = %s", (marca_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(404, "Marca no encontrada")

        count_row = conn.execute(
            "SELECT COUNT(*) AS n FROM equipos WHERE brand_id = %s", (marca_id,)
        ).fetchone()
        n = int(count_row["n"] if isinstance(count_row, dict) else count_row[0])
        if n > 0:
            raise HTTPException(
                409,
                f"La marca tiene {n} equipos asociados. Fusionala con otra o reasigná los equipos antes de borrar.",
            )

        conn.execute("DELETE FROM marcas WHERE id = %s", (marca_id,))
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _is_svg(raw: bytes, filename: str | None) -> bool:
    """Heurística para detectar SVG: o el nombre termina en .svg, o los
    primeros bytes contienen <?xml o <svg.
    """
    if filename and filename.lower().endswith(".svg"):
        return True
    head = raw[:512].lstrip().lower()
    return head.startswith(b"<?xml") or head.startswith(b"<svg")


def _sanitize_svg(raw: bytes) -> bytes:
    """Strip <script> tags y atributos on* del SVG antes de subirlo a R2.
    Defensa en profundidad — los uploads requieren admin auth pero un
    admin comprometido podría inyectar XSS en cualquier página que inline
    el SVG.
    """
    text = raw.decode("utf-8", errors="ignore")
    # <script>...</script> (sin importar atributos)
    text = re.sub(r"<\s*script\b[^>]*>.*?<\s*/\s*script\s*>",
                  "", text, flags=re.IGNORECASE | re.DOTALL)
    # <script ... /> auto-closed
    text = re.sub(r"<\s*script\b[^>]*/\s*>", "", text, flags=re.IGNORECASE)
    # atributos on* (onclick, onload, onerror, etc.) — match con/sin comillas
    text = re.sub(r'\s+on[a-z]+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)',
                  "", text, flags=re.IGNORECASE)
    # <foreignObject> permite HTML arbitrario adentro del SVG → tirarlo.
    text = re.sub(r"<\s*foreignObject\b[^>]*>.*?<\s*/\s*foreignObject\s*>",
                  "", text, flags=re.IGNORECASE | re.DOTALL)
    return text.encode("utf-8")


@router.post("/admin/marcas/{marca_id}/upload-logo")
async def admin_upload_marca_logo(marca_id: int, request: Request):
    """Sube un logo (multipart/form-data, campo `file`) a R2 y persiste
    `logo_url` en la marca.

    - SVG: se sube tal cual (con sanitize defensivo de <script> y on*).
      Se sirve con `Content-Type: image/svg+xml`. El frontend puede
      inlinearlo para teñirlo via `currentColor`.
    - Raster (PNG/JPEG/WebP): se optimiza con Pillow → WebP q=85, igual
      que las fotos de equipos.
    """
    require_admin(request)

    # Import lazy para evitar ciclo entre marcas.py ↔ equipos.py
    from routes.equipos import _optimize_image, _ext_from_ctype, _upload_to_r2

    conn = get_db()
    try:
        marca = conn.execute(
            "SELECT id, nombre FROM marcas WHERE id = %s", (marca_id,)
        ).fetchone()
        if not marca:
            raise HTTPException(404, "Marca no encontrada")
        nombre = marca["nombre"] if isinstance(marca, dict) else marca[1]
    finally:
        conn.close()

    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(400, "Falta el campo 'file' en el form-data")

    raw_content = await file.read()
    if not raw_content:
        raise HTTPException(400, "Archivo vacío")
    if len(raw_content) > 5 * 1024 * 1024:
        raise HTTPException(413, "Logo muy grande (máx 5MB)")

    filename = getattr(file, "filename", None)
    if _is_svg(raw_content, filename):
        # SVG: sanitize y subir tal cual.
        content = _sanitize_svg(raw_content)
        ctype = "image/svg+xml"
        ext = "svg"
        w, h = None, None
    else:
        # Raster: optimizar a WebP.
        content, ctype, w, h = _optimize_image(raw_content)
        ext = _ext_from_ctype(ctype)

    path = _logo_path(marca_id, nombre, ext)
    public_url = _upload_to_r2(path, content, ctype)

    conn = get_db()
    try:
        conn.execute(
            "UPDATE marcas SET logo_url = %s, updated_at = NOW() WHERE id = %s",
            (public_url, marca_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "public_url": public_url,
        "path": path,
        "size": len(content),
        "size_original": len(raw_content),
        "content_type": ctype,
        "width": w,
        "height": h,
    }
