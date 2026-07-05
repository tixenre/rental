"""
routes/clientes.py — CRUD de clientes e importación desde histórico.
"""

from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Request
from pydantic import BaseModel

from urllib.parse import quote

from database import get_db, row_to_dict
from auth.guards import require_admin
from auth.commands import magic as magic_commands
from busqueda import construir
from config import settings
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


# ── Fusión de duplicados (Fase 2 identidad #1098) ─────────────────────────────
# El back-office para deduplicar clientes que son la misma persona. Cablea al motor
# `identity/merge` (transaccional, con guardas). Destructivo → require_admin.
# ⚠️ ORDEN: la GET estática va ANTES de `/clientes/{id}` — si no, `/{id}` captura
# "duplicados" como id y tira 422 (colisión de rutas — cazada por el supervisor; el
# test_clientes_merge_route la clava a nivel HTTP).

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


class InvitarClienteIn(BaseModel):
    email: str
    nombre: Optional[str] = None
    telefono: Optional[str] = None


@router.post("/clientes/invitar")
def invitar_cliente(body: InvitarClienteIn, request: Request):
    """Crea (o reusa) una cuenta por email y devuelve un LINK de invitación single-use
    para que el cliente la reclame (active la cuenta + registre su passkey). El admin lo
    manda por donde quiera — mismo patrón que el link de verificación (no se manda mail
    desde acá: el motor de mail es por plantilla; el admin copia el link). El email se
    valida/locked recién con Didit; el nombre/teléfono del admin son provisionales."""
    require_admin(request)
    email = (body.email or "").strip().lower()
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise HTTPException(400, "Email inválido")
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, dni_validado_at FROM clientes WHERE LOWER(email) = LOWER(%s)", (email,)
        ).fetchone()
        if row:
            # Anti-takeover: una cuenta YA verificada (identidad + pagos) NO se invita por
            # link — si se filtra, quien lo abra entra con todo adentro. Esas se recuperan
            # por Didit/CUIL (Fase 3, no se puede falsificar). Sí se invita lo no-verificado
            # (incluso clientes viejos con pedidos pero sin Didit → caso de migración).
            if row["dni_validado_at"] is not None:
                raise HTTPException(
                    400,
                    "Esa cuenta ya está verificada — el cliente la recupera por su identidad "
                    "(Didit), no por un link de invitación.",
                )
            cliente_id, ya_existia = row["id"], True
        else:
            cliente_id = conn.insert_returning(
                "INSERT INTO clientes (email, nombre, telefono, cuenta_estado) "
                "VALUES (%s, %s, %s, 'liviana')",
                (email, (body.nombre or "").strip() or None, (body.telefono or "").strip() or None),
            )
            conn.commit()
            ya_existia = False
    token = magic_commands.crear(email=email, purpose="invitacion", cliente_id=cliente_id)
    return {
        "ok": True,
        "cliente_id": cliente_id,
        "ya_existia": ya_existia,
        "url": f"{settings.SITE_URL}/cliente/claim?t={quote(token, safe='')}",
    }


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


@router.get("/clientes/{id}/perfiles-fiscales")
def get_cliente_perfiles_fiscales(id: int, request: Request):
    """Solo lectura (#1240): perfiles fiscales personales del cliente +
    productoras a las que está vinculado — para la ficha admin. La gestión
    real vive en `POST /api/cliente/facturacion/perfiles` (self-service del
    cliente) y `routes/productoras.py` (admin, membership de productoras)."""
    require_admin(request)
    with get_db() as conn:
        if not conn.execute("SELECT id FROM clientes WHERE id=%s", (id,)).fetchone():
            raise HTTPException(404, "Cliente no encontrado")
        perfiles = conn.execute(
            """SELECT id, cuit, perfil_impuestos, razon_social, domicilio_fiscal,
                      etiqueta, es_default
               FROM cliente_perfiles_fiscales
               WHERE cliente_id = %s
               ORDER BY es_default DESC, created_at ASC""",
            (id,),
        ).fetchall()
        productoras = conn.execute(
            """SELECT p.id, p.cuit, p.perfil_impuestos, p.razon_social
               FROM productoras p
               JOIN productora_miembros pm ON pm.productora_id = p.id
               WHERE pm.cliente_id = %s
               ORDER BY p.razon_social NULLS LAST, p.id""",
            (id,),
        ).fetchall()
    return {
        "perfiles": [row_to_dict(r) for r in perfiles],
        "productoras": [row_to_dict(r) for r in productoras],
    }


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
            set_clause = ", ".join(f"{k}=%s" for k in updates) + ", updated_at=CURRENT_TIMESTAMP"
            conn.execute(f"UPDATE clientes SET {set_clause} WHERE id=%s", list(updates.values()) + [id])
            # Si cambió el descuento del cliente, recotizar sus presupuestos SIN
            # override manual (pedidos NO confirmados; los confirmados/cerrados
            # quedan congelados — lock de precio). El descuento del cliente ya se
            # lee EN VIVO (Fase C-1, #1219) — no hace falta pasarlo, solo disparar
            # el recálculo. Misma transacción → ve el UPDATE de arriba → atómico.
            if "descuento" in updates and (updates["descuento"] or 0) != (actual["descuento"] or 0):
                from routes.alquileres import propagar_descuento_a_presupuestos
                propagar_descuento_a_presupuestos(conn, id)
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


