"""routes/productoras — CRUD admin de productoras + membership (#1240).

Productoras: entidad fiscal SIN login propio, compartida entre varias cuentas
de cliente (una persona puede comprar en nombre de varias productoras, y una
productora puede tener varias personas comprando en su nombre). El admin es
el ÚNICO que crea/edita/vincula — sin self-service del cliente, sin roles ni
invitaciones. El cliente solo LEE (`GET /api/cliente/productoras`, en
`routes/cliente_portal/cuenta.py`).

Toda alta/edición verifica el CUIT contra el padrón real de ARCA
(`verificar_y_crear_productora`, bloqueante) — misma regla que los perfiles
fiscales personales: nunca una productora con datos sin confirmar.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from database import get_db, row_to_dict
from auth.guards import require_admin
from identity.anchor import cuil_valido
from rate_limit import limiter, ADMIN_WRITE_LIMIT
from routes.contabilidad import map_pg_errors

router = APIRouter(tags=["productoras"])

_CAMPOS_PRODUCTORA = (
    "id, cuit, perfil_impuestos, razon_social, domicilio_fiscal, "
    "email_facturacion, notas, verificado_at, created_at, updated_at"
)


@router.get("/admin/productoras")
def listar_productoras(request: Request, q: Optional[str] = None):
    """Lista productoras — filtro simple por razón social/CUIT (sin motor de
    búsqueda fuzzy dedicado, el volumen esperado es bajo)."""
    require_admin(request)
    with get_db() as conn:
        if q:
            like = f"%{q.strip()}%"
            rows = conn.execute(
                f"""SELECT {_CAMPOS_PRODUCTORA} FROM productoras
                    WHERE razon_social ILIKE %s OR cuit ILIKE %s
                    ORDER BY razon_social NULLS LAST, id""",
                (like, like),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {_CAMPOS_PRODUCTORA} FROM productoras ORDER BY razon_social NULLS LAST, id"
            ).fetchall()
    return [row_to_dict(r) for r in rows]


class ProductoraCreate(BaseModel):
    cuit: str
    notas: Optional[str] = None


@router.post("/admin/productoras", status_code=201)
@limiter.limit(ADMIN_WRITE_LIMIT)
@map_pg_errors
def crear_productora(request: Request, body: ProductoraCreate):
    """Alta bloqueante: si AFIP no puede confirmar el CUIT, 422 con el motivo
    real — no se crea nada a medias."""
    require_admin(request)
    cuit = body.cuit.strip()
    if not cuil_valido(cuit):
        raise HTTPException(400, "CUIT inválido — verificá el dígito verificador.")

    from services.facturacion.padron import verificar_y_crear_productora
    with get_db() as conn:
        try:
            verificar_y_crear_productora(cuit, conn, notas=body.notas)
        except RuntimeError as e:
            conn.rollback()
            raise HTTPException(422, f"AFIP no pudo confirmar este CUIT: {e}")
        conn.commit()
        row = conn.execute(
            f"SELECT {_CAMPOS_PRODUCTORA} FROM productoras WHERE cuit = %s", (cuit,)
        ).fetchone()
    return row_to_dict(row) if row else {}


@router.get("/admin/productoras/{productora_id}")
def obtener_productora(productora_id: int, request: Request):
    """Detalle + lista de miembros (clientes vinculados)."""
    require_admin(request)
    with get_db() as conn:
        row = conn.execute(
            f"SELECT {_CAMPOS_PRODUCTORA} FROM productoras WHERE id = %s", (productora_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Productora no encontrada")
        miembros = conn.execute(
            """SELECT c.id, c.nombre, c.apellido, c.email
               FROM clientes c
               JOIN productora_miembros pm ON pm.cliente_id = c.id
               WHERE pm.productora_id = %s
               ORDER BY c.nombre, c.apellido""",
            (productora_id,),
        ).fetchall()
    productora = row_to_dict(row)
    productora["miembros"] = [row_to_dict(m) for m in miembros]
    return productora


class ProductoraUpdate(BaseModel):
    # Re-verifica el CUIT contra ARCA (refresca razón social/domicilio/condición
    # IVA) — no se edita a mano, mismo criterio "AFIP siempre gana" del resto.
    reverificar: bool = False
    notas: Optional[str] = None


@router.patch("/admin/productoras/{productora_id}")
@limiter.limit(ADMIN_WRITE_LIMIT)
@map_pg_errors
def actualizar_productora(productora_id: int, request: Request, body: ProductoraUpdate):
    require_admin(request)
    with get_db() as conn:
        row = conn.execute(
            "SELECT cuit FROM productoras WHERE id = %s", (productora_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Productora no encontrada")
        cuit = row["cuit"]

        if body.reverificar:
            from services.facturacion.padron import verificar_y_crear_productora
            try:
                verificar_y_crear_productora(cuit, conn, notas=body.notas)
            except RuntimeError as e:
                conn.rollback()
                raise HTTPException(422, f"AFIP no pudo confirmar este CUIT: {e}")
        elif body.notas is not None:
            conn.execute(
                "UPDATE productoras SET notas = %s, updated_at = now() WHERE id = %s",
                (body.notas, productora_id),
            )
        conn.commit()
        result = conn.execute(
            f"SELECT {_CAMPOS_PRODUCTORA} FROM productoras WHERE id = %s", (productora_id,)
        ).fetchone()
    return row_to_dict(result)


class MiembroIn(BaseModel):
    cliente_id: int


@router.post("/admin/productoras/{productora_id}/miembros", status_code=201)
@limiter.limit(ADMIN_WRITE_LIMIT)
def agregar_miembro(productora_id: int, request: Request, body: MiembroIn):
    """Vincula un cliente a la productora — idempotente (si ya está vinculado,
    no falla ni duplica)."""
    require_admin(request)
    with get_db() as conn:
        productora = conn.execute(
            "SELECT 1 FROM productoras WHERE id = %s", (productora_id,)
        ).fetchone()
        if not productora:
            raise HTTPException(404, "Productora no encontrada")
        cliente = conn.execute(
            "SELECT 1 FROM clientes WHERE id = %s", (body.cliente_id,)
        ).fetchone()
        if not cliente:
            raise HTTPException(404, "Cliente no encontrado")
        conn.execute(
            """INSERT INTO productora_miembros (productora_id, cliente_id)
               VALUES (%s, %s) ON CONFLICT (productora_id, cliente_id) DO NOTHING""",
            (productora_id, body.cliente_id),
        )
        conn.commit()
    return {"ok": True}


@router.delete("/admin/productoras/{productora_id}/miembros/{cliente_id}", status_code=204)
@limiter.limit(ADMIN_WRITE_LIMIT)
def quitar_miembro(productora_id: int, cliente_id: int, request: Request):
    require_admin(request)
    with get_db() as conn:
        conn.execute(
            "DELETE FROM productora_miembros WHERE productora_id = %s AND cliente_id = %s",
            (productora_id, cliente_id),
        )
        conn.commit()
    return None
