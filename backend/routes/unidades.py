"""
routes/unidades.py — Catálogo global de unidades (lm, K, V, etc.).

Los specs tipo tabla con columnas `valor_unidad` referencian este catálogo
para que el dueño elija de una lista cerrada en lugar de escribir libre.

La unidad en cada celda sigue guardándose como string (símbolo) — este
catálogo es solo fuente de verdad de qué unidades existen.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from database import get_db, row_to_dict
# Guard CANÓNICO reexportado bajo el nombre del paquete (`_require_admin`): valida
# email ∈ ADMIN_EMAILS (→ 403), no solo que exista sesión. Una copia local débil
# dejaba pasar a cualquier logueado, incluido un cliente del portal.
from admin_guard import require_admin as _require_admin


router = APIRouter()


# ── Models ─────────────────────────────────────────────────────────────

class UnidadInput(BaseModel):
    simbolo: str
    nombre: str
    dimension: Optional[str] = None


class UnidadUpdate(BaseModel):
    simbolo: Optional[str] = None
    nombre: Optional[str] = None
    dimension: Optional[str] = None


# ── CRUD ────────────────────────────────────────────────────────────────

@router.get("/admin/unidades")
def listar_unidades(request: Request):
    """Lista todas las unidades del catálogo, agrupables por dimensión."""
    _require_admin(request)
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, simbolo, nombre, dimension
            FROM unidades
            ORDER BY dimension NULLS LAST, simbolo
            """
        ).fetchall()
        return {"items": [row_to_dict(r) for r in rows]}


@router.post("/admin/unidades", status_code=201)
def crear_unidad(payload: UnidadInput, request: Request):
    _require_admin(request)
    simbolo = (payload.simbolo or "").strip()
    nombre = (payload.nombre or "").strip()
    dimension = (payload.dimension or "").strip() or None
    if not simbolo or not nombre:
        raise HTTPException(400, "simbolo y nombre son obligatorios")
    with get_db() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO unidades (simbolo, nombre, dimension)
                VALUES (?, ?, ?)
                RETURNING id
                """,
                (simbolo, nombre, dimension),
            )
            new_id = cur.fetchone()[0]
            conn.commit()
            return {"id": new_id, "simbolo": simbolo, "nombre": nombre, "dimension": dimension}
        except Exception as e:
            conn.rollback()
            if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
                raise HTTPException(409, f"Ya existe una unidad con símbolo '{simbolo}'.")
            raise


@router.patch("/admin/unidades/{unidad_id}")
def actualizar_unidad(unidad_id: int, payload: UnidadUpdate, request: Request):
    _require_admin(request)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "Nada para actualizar")
    # Limpiar strings vacíos / espacios.
    for k in ("simbolo", "nombre"):
        if k in updates:
            v = (updates[k] or "").strip()
            if not v:
                raise HTTPException(400, f"{k} no puede estar vacío")
            updates[k] = v
    if "dimension" in updates:
        v = (updates["dimension"] or "").strip()
        updates["dimension"] = v or None
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM unidades WHERE id = ?", (unidad_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(404, "Unidad no existe")
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        try:
            conn.execute(
                f"UPDATE unidades SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                list(updates.values()) + [unidad_id],
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
                raise HTTPException(409, "Ya existe otra unidad con ese símbolo.")
            raise
        return {"ok": True, "id": unidad_id, **updates}


@router.delete("/admin/unidades/{unidad_id}", status_code=204)
def borrar_unidad(unidad_id: int, request: Request):
    """Borra una unidad del catálogo. No valida usos (las specs guardan el
    símbolo como string libre, no hay FK). Si una unidad borrada estaba
    en uso, queda como string huérfano en las columnas que la usaban."""
    _require_admin(request)
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM unidades WHERE id = ?", (unidad_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(404, "Unidad no existe")
        conn.execute("DELETE FROM unidades WHERE id = ?", (unidad_id,))
        conn.commit()
