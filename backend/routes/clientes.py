"""
routes/clientes.py — CRUD de clientes e importación desde histórico.
"""

from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Request
from pydantic import BaseModel

from database import get_db, row_to_dict
from admin_guard import require_admin

router = APIRouter()


# ── Modelos ──────────────────────────────────────────────────────────────────

class ClienteCreate(BaseModel):
    nombre:             str
    apellido:           str
    telefono:           str = ""
    email:              str = ""
    direccion:          str = ""
    cuit:               str = ""
    descuento:          float = 0
    perfil_impuestos:   str = "consumidor_final"
    notas:              Optional[str] = None
    direccion_maps_url: Optional[str] = None


class ClienteUpdate(BaseModel):
    nombre:             Optional[str]   = None
    apellido:           Optional[str]   = None
    telefono:           Optional[str]   = None
    email:              Optional[str]   = None
    direccion:          Optional[str]   = None
    cuit:               Optional[str]   = None
    descuento:          Optional[float] = None
    perfil_impuestos:   Optional[str]   = None
    notas:              Optional[str]   = None
    direccion_maps_url: Optional[str]   = None


# ── Rutas ────────────────────────────────────────────────────────────────────


@router.get("/clientes")
def list_clientes(
    request:  Request,
    q:        Optional[str] = Query(None),
    page:     int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
):
    require_admin(request)
    conn   = get_db()
    offset = (page - 1) * per_page
    where  = "WHERE 1=1"
    params: list = []
    if q:
        like = f"%{q}%"
        where += " AND (nombre LIKE ? OR apellido LIKE ? OR email LIKE ? OR cuit LIKE ?)"
        params += [like, like, like, like]
    try:
        total = conn.execute(f"SELECT COUNT(*) FROM clientes {where}", params).fetchone()[0]
        rows  = conn.execute(
            f"SELECT * FROM clientes {where} ORDER BY apellido, nombre LIMIT ? OFFSET ?",
            params + [per_page, offset]
        ).fetchall()
        return {"total": total, "page": page, "per_page": per_page, "items": [row_to_dict(r) for r in rows]}
    finally:
        conn.close()


@router.get("/clientes/{id}")
def get_cliente(id: int, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        row  = conn.execute("SELECT * FROM clientes WHERE id=?", (id,)).fetchone()
        if not row:
            raise HTTPException(404, "Cliente no encontrado")
        return row_to_dict(row)
    finally:
        conn.close()


@router.get("/clientes/{id}/pedidos")
def get_cliente_pedidos(id: int, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM clientes WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Cliente no encontrado")
        rows = conn.execute("""
            SELECT p.id, p.numero_pedido, p.estado, p.fecha_desde, p.fecha_hasta,
                   p.monto_total, p.monto_pagado, p.descuento_pct,
                   STRING_AGG(e.nombre, ' · ') AS equipos
            FROM alquileres p
            LEFT JOIN alquiler_items pi ON pi.pedido_id = p.id
            LEFT JOIN equipos e ON e.id = pi.equipo_id
            WHERE p.cliente_id = ?
            GROUP BY p.id, p.numero_pedido, p.estado, p.fecha_desde, p.fecha_hasta,
                     p.monto_total, p.monto_pagado, p.descuento_pct
            ORDER BY p.numero_pedido DESC
        """, (id,)).fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


@router.post("/clientes", status_code=201)
def create_cliente(data: ClienteCreate, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        cur  = conn.execute("""
            INSERT INTO clientes (nombre, apellido, telefono, email, direccion, cuit,
                                  descuento, perfil_impuestos, notas, direccion_maps_url)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (data.nombre, data.apellido, data.telefono, data.email, data.direccion,
              data.cuit, data.descuento, data.perfil_impuestos, data.notas, data.direccion_maps_url))
        conn.commit()
        row = conn.execute("SELECT * FROM clientes WHERE id=?", (cur.lastrowid,)).fetchone()
        return row_to_dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.patch("/clientes/{id}")
def update_cliente(id: int, data: ClienteUpdate, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM clientes WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Cliente no encontrado")
        updates = data.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(400, "Nada para actualizar")
        set_clause = ", ".join(f"{k}=?" for k in updates) + ", updated_at=CURRENT_TIMESTAMP"
        conn.execute(f"UPDATE clientes SET {set_clause} WHERE id=?", list(updates.values()) + [id])
        conn.commit()
        row = conn.execute("SELECT * FROM clientes WHERE id=?", (id,)).fetchone()
        return row_to_dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.delete("/clientes/{id}", status_code=204)
def delete_cliente(id: int, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM clientes WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Cliente no encontrado")
        conn.execute("DELETE FROM clientes WHERE id=?", (id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
