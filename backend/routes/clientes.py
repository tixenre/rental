"""
routes/clientes.py — CRUD de clientes e importación desde histórico.
"""

from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Request
from pydantic import BaseModel

from database import get_db, row_to_dict
from auth.guards import require_admin
from busqueda import construir
from identity import merge

router = APIRouter()


def nombre_completo_cliente(nombre, apellido) -> str:
    """Compone el nombre visible de un cliente: **"Nombre Apellido"** (nombre
    primero). Fuente ÚNICA — antes se armaba "Apellido, Nombre" copiado en ~6
    lugares (back-office, pedidos, estudio). Decisión del dueño 2026-06-06: el
    nombre se muestra siempre con el nombre primero. Si falta el apellido,
    devuelve solo el nombre."""
    n = (nombre or "").strip()
    a = (apellido or "").strip()
    return f"{n} {a}".strip() if a else n

# Campos buscables del cliente. El combinado nombre+apellido permite que
# "santiago perez" matchee/rankee aunque nombre y apellido sean campos distintos.
CAMPOS_CLIENTE = [
    "(c.nombre || ' ' || c.apellido)",
    "c.nombre",
    "c.apellido",
    "c.email",
    "c.cuit",
    "c.telefono",
]


# ── Modelos ──────────────────────────────────────────────────────────────────

class ClienteCreate(BaseModel):
    from pydantic import field_validator
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

    @field_validator("descuento")
    @classmethod
    def validate_descuento(cls, v):
        if v is None:
            return 0
        if v < 0 or v > 100:
            raise ValueError("descuento debe estar entre 0 y 100")
        return v


class ClienteUpdate(BaseModel):
    from pydantic import field_validator
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

    @field_validator("descuento")
    @classmethod
    def validate_descuento(cls, v):
        if v is None:
            return v
        if v < 0 or v > 100:
            raise ValueError("descuento debe estar entre 0 y 100")
        return v


# ── Rutas ────────────────────────────────────────────────────────────────────


@router.get("/clientes")
def list_clientes(
    request:  Request,
    q:        Optional[str] = Query(None),
    page:     int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
):
    require_admin(request)
    offset = (page - 1) * per_page
    where  = "WHERE 1=1"
    params: list = []

    # Búsqueda fuzzy unificada (backend/busqueda): sin tildes, sin guiones,
    # multi-palabra cruzando campos y ranking por relevancia (el mejor match
    # primero, consistente — antes ordenaba alfabético y "a veces traía otro").
    pred = construir(CAMPOS_CLIENTE, q) if q else None
    if pred and pred.activo:
        where += f" AND ({pred.where})"
        params += pred.where_params

    with get_db() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM clientes c {where}", params).fetchone()[0]
        if pred and pred.activo:
            select_params = pred.score_params + params + [per_page, offset]
            rows = conn.execute(
                f"SELECT c.*, ({pred.score}) AS _score FROM clientes c {where} "
                f"ORDER BY _score DESC, c.apellido, c.nombre LIMIT %s OFFSET %s",
                select_params,
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT c.* FROM clientes c {where} ORDER BY c.apellido, c.nombre LIMIT %s OFFSET %s",
                params + [per_page, offset],
            ).fetchall()
        items = []
        for r in rows:
            d = row_to_dict(r)
            d.pop("_score", None)  # interno del ranking, no parte del contrato
            items.append(d)
        return {"total": total, "page": page, "per_page": per_page, "items": items}


@router.get("/clientes/{id}")
def get_cliente(id: int, request: Request):
    require_admin(request)
    with get_db() as conn:
        row  = conn.execute("SELECT * FROM clientes WHERE id=%s", (id,)).fetchone()
        if not row:
            raise HTTPException(404, "Cliente no encontrado")
        return row_to_dict(row)


@router.get("/clientes/{id}/pedidos")
def get_cliente_pedidos(id: int, request: Request):
    require_admin(request)
    with get_db() as conn:
        if not conn.execute("SELECT id FROM clientes WHERE id=%s", (id,)).fetchone():
            raise HTTPException(404, "Cliente no encontrado")
        rows = conn.execute("""
            SELECT p.id, p.numero_pedido, p.estado, p.fecha_desde, p.fecha_hasta,
                   p.monto_total, p.monto_pagado, p.descuento_pct, p.created_at,
                   STRING_AGG(e.nombre, ' · ') AS equipos
            FROM alquileres p
            LEFT JOIN alquiler_items pi ON pi.pedido_id = p.id
            LEFT JOIN equipos e ON e.id = pi.equipo_id
            WHERE p.cliente_id = %s
            GROUP BY p.id, p.numero_pedido, p.estado, p.fecha_desde, p.fecha_hasta,
                     p.monto_total, p.monto_pagado, p.descuento_pct, p.created_at
            ORDER BY p.created_at DESC NULLS LAST, p.numero_pedido DESC
        """, (id,)).fetchall()
        return [row_to_dict(r) for r in rows]


@router.post("/clientes", status_code=201)
def create_cliente(data: ClienteCreate, request: Request):
    require_admin(request)
    with get_db() as conn:
        try:
            cliente_id = conn.insert_returning("""
                INSERT INTO clientes (nombre, apellido, telefono, email, direccion, cuit,
                                      descuento, perfil_impuestos, notas, direccion_maps_url)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (data.nombre, data.apellido, data.telefono, data.email, data.direccion,
                  data.cuit, data.descuento, data.perfil_impuestos, data.notas, data.direccion_maps_url))
            conn.commit()
            row = conn.execute("SELECT * FROM clientes WHERE id=%s", (cliente_id,)).fetchone()
            return row_to_dict(row)
        except Exception:
            conn.rollback()
            raise


@router.patch("/clientes/{id}")
def update_cliente(id: int, data: ClienteUpdate, request: Request):
    require_admin(request)
    with get_db() as conn:
        try:
            actual = conn.execute("SELECT descuento FROM clientes WHERE id=%s", (id,)).fetchone()
            if not actual:
                raise HTTPException(404, "Cliente no encontrado")
            updates = data.model_dump(exclude_unset=True)
            if not updates:
                raise HTTPException(400, "Nada para actualizar")
            set_clause = ", ".join(f"{k}=?" for k in updates) + ", updated_at=CURRENT_TIMESTAMP"
            conn.execute(f"UPDATE clientes SET {set_clause} WHERE id=%s", list(updates.values()) + [id])
            # Si cambió el descuento del cliente, propagarlo a sus presupuestos
            # (pedidos NO confirmados). Los confirmados/cerrados quedan congelados
            # con su snapshot — lock de precio. Misma transacción → atómico.
            if "descuento" in updates and (updates["descuento"] or 0) != (actual["descuento"] or 0):
                from routes.alquileres import propagar_descuento_a_presupuestos
                propagar_descuento_a_presupuestos(conn, id, updates["descuento"] or 0)
            conn.commit()
            row = conn.execute("SELECT * FROM clientes WHERE id=%s", (id,)).fetchone()
            return row_to_dict(row)
        except Exception:
            conn.rollback()
            raise


@router.delete("/clientes/{id}", status_code=204)
def delete_cliente(id: int, request: Request):
    require_admin(request)
    with get_db() as conn:
        try:
            if not conn.execute("SELECT id FROM clientes WHERE id=%s", (id,)).fetchone():
                raise HTTPException(404, "Cliente no encontrado")
            conn.execute("DELETE FROM clientes WHERE id=%s", (id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise


# ── Fusión de duplicados (Fase 2 identidad #1098) ─────────────────────────────
# El back-office para deduplicar clientes que son la misma persona. Cablea al motor
# `identity/merge` (transaccional, con guardas). Destructivo → require_admin.

@router.get("/clientes/duplicados")
def clientes_duplicados(request: Request):
    """Grupos de clientes que comparten un CUIL verificado — candidatos a fusionar
    (justo lo que el índice único de CUIL rechaza). Enriquece cada id con nombre,
    contacto, estado y nº de pedidos para que el admin elija cuál conservar."""
    require_admin(request)
    with get_db() as conn:
        out = []
        for g in merge.candidatos_duplicados(conn):
            clientes = []
            for cid in g["ids"]:
                row = conn.execute(
                    """SELECT c.id, c.nombre, c.apellido, c.email, c.telefono,
                              c.nombre_completo_renaper, c.dni_validado_at, c.created_at,
                              (SELECT COUNT(*) FROM alquileres a WHERE a.cliente_id = c.id) AS pedidos
                         FROM clientes c WHERE c.id = %s""",
                    (cid,),
                ).fetchone()
                if row:
                    clientes.append(row_to_dict(row))
            out.append({"cuil": g["cuil"], "clientes": clientes})
        return out


class MergeClientesIn(BaseModel):
    source: int  # se absorbe y se borra
    target: int  # sobrevive con su identidad


@router.post("/clientes/merge")
def merge_clientes(body: MergeClientesIn, request: Request):
    """Fusiona dos clientes que son la MISMA persona: mueve pedidos / datos / llaves /
    bitácora de `source` a `target` y borra `source`. **Destructivo e irreversible** →
    require_admin + las guardas del motor (rehúsa perder una identidad verificada o unir
    dos personas con CUIL distinto → 400)."""
    require_admin(request)
    if body.source == body.target:
        raise HTTPException(400, "No se puede fusionar un cliente consigo mismo")
    try:
        merge.merge_accounts(source=body.source, target=body.target)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "merged_into": body.target}
