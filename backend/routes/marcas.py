"""
routes/marcas.py — CRUD de marcas (brands).
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_db, row_to_dict

router = APIRouter()


# ── Pydantic Models ──────────────────────────────────────────────────────────

class MarcaAdmin(BaseModel):
    id: int
    nombre: str
    logo_url: Optional[str] = None
    visible: bool
    orden: int
    total: int


class MarcaPatch(BaseModel):
    nombre: Optional[str] = None
    logo_url: Optional[str] = None
    visible: Optional[bool] = None
    orden: Optional[int] = None


class MarcasReorderRequest(BaseModel):
    marcas: list[dict]  # [{"id": 1, "orden": 2}, ...]


# ── Public API ───────────────────────────────────────────────────────────────

@router.get("/marcas")
def list_marcas():
    """Lista marcas visibles ordenadas por orden, luego por nombre."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT id, nombre, logo_url, created_at, updated_at
            FROM marcas
            WHERE visible = TRUE
            ORDER BY orden ASC, nombre ASC
        """).fetchall()
        marcas = [row_to_dict(r) for r in rows]
        return {"items": marcas}
    finally:
        conn.close()


# ── Admin API ────────────────────────────────────────────────────────────────

@router.get("/admin/marcas")
def admin_list_marcas():
    """Lista todas las marcas (visible/invisible) con count de equipos."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT
                m.id, m.nombre, m.logo_url, m.visible, m.orden,
                COUNT(e.id) as total
            FROM marcas m
            LEFT JOIN equipos e ON e.brand_id = m.id
            GROUP BY m.id, m.nombre, m.logo_url, m.visible, m.orden
            ORDER BY m.orden ASC, m.nombre ASC
        """).fetchall()
        marcas = [dict(row) for row in rows]
        return {"items": marcas}
    finally:
        conn.close()


@router.patch("/admin/marcas/{marca_id}")
def admin_update_marca(marca_id: int, patch: MarcaPatch):
    """Actualiza una marca (nombre, logo_url, visible, orden)."""
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
                m.id, m.nombre, m.logo_url, m.visible, m.orden,
                COUNT(e.id) as total
            FROM marcas m
            LEFT JOIN equipos e ON e.brand_id = m.id
            WHERE m.id = %s
            GROUP BY m.id, m.nombre, m.logo_url, m.visible, m.orden
        """, (marca_id,)).fetchone()

        conn.commit()
        return dict(row) if row else {}
    finally:
        conn.close()


@router.post("/admin/marcas/reorder")
def admin_reorder_marcas(req: MarcasReorderRequest):
    """Actualiza el orden de múltiples marcas."""
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
