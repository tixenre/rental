"""
routes/marcas.py — CRUD de marcas (brands).
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from database import get_db, row_to_dict
from admin_guard import require_admin

router = APIRouter()


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
            SELECT id, nombre, logo_url, destacada, popularidad_score, created_at, updated_at
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
