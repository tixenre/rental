"""routes/contabilidad.py — Módulo contable (#809).

Transporte HTTP fino sobre el motor `backend/contabilidad/` (igual que
`routes/reportes.py` sobre `reportes/`). Fase 1: cuentas (CRUD) + saldos + tablero
mínimo. Acceso = cualquier admin (`require_admin`); el actor de auditoría sale de
`admin.get("email")`.
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from database import get_db
from admin_guard import require_admin
from contabilidad.cuentas import (
    crear_cuenta,
    desactivar_cuenta,
    editar_cuenta,
    listar_cuentas,
)
from contabilidad.saldos import saldos as _saldos

router = APIRouter()


class CuentaCreate(BaseModel):
    nombre: str
    tipo: str
    socio: str | None = None
    saldo_inicial: int = 0
    fecha_apertura: str | None = None
    orden: int = 0


class CuentaUpdate(BaseModel):
    nombre: str | None = None
    saldo_inicial: int | None = None
    fecha_apertura: str | None = None
    orden: int | None = None
    activa: bool | None = None


@router.get("/admin/contabilidad/saldos")
def get_saldos(request: Request):
    """Saldos de todas las cuentas activas + total disponible. Los ingresos por
    alquiler ya vienen derivados de `alquiler_pagos`."""
    require_admin(request)
    with get_db() as conn:
        return _saldos(conn)


@router.get("/admin/contabilidad/tablero")
def get_tablero(request: Request):
    """Tablero financiero. Fase 1: solo 'disponible' (plata por caja + total).
    En fases siguientes se suman ganancia neta del mes y rendición pendiente."""
    require_admin(request)
    with get_db() as conn:
        return {"disponible": _saldos(conn)}


@router.get("/admin/contabilidad/cuentas")
def get_cuentas(request: Request, incluir_inactivas: bool = False):
    """Cuentas crudas (para administrar). `incluir_inactivas=true` trae también las
    dadas de baja."""
    require_admin(request)
    with get_db() as conn:
        return {"cuentas": listar_cuentas(conn, incluir_inactivas=incluir_inactivas)}


@router.post("/admin/contabilidad/cuentas")
def post_cuenta(request: Request, body: CuentaCreate):
    """Crea una cuenta/caja nueva."""
    admin = require_admin(request)
    with get_db() as conn:
        try:
            cuenta = crear_cuenta(
                conn,
                nombre=body.nombre,
                tipo=body.tipo,
                socio=body.socio,
                saldo_inicial=body.saldo_inicial,
                fecha_apertura=body.fecha_apertura,
                orden=body.orden,
                por=admin.get("email"),
            )
            conn.commit()
            return cuenta
        except ValueError as e:
            conn.rollback()
            raise HTTPException(400, str(e))
        except Exception:
            conn.rollback()
            raise


@router.patch("/admin/contabilidad/cuentas/{cuenta_id}")
def patch_cuenta(request: Request, cuenta_id: int, body: CuentaUpdate):
    """Edita una cuenta. No se puede cambiar tipo ni socio."""
    admin = require_admin(request)
    campos = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None
              or k == "activa"}
    with get_db() as conn:
        try:
            cuenta = editar_cuenta(conn, cuenta_id, campos=campos, por=admin.get("email"))
            conn.commit()
            return cuenta
        except ValueError as e:
            conn.rollback()
            raise HTTPException(400, str(e))
        except Exception:
            conn.rollback()
            raise


@router.delete("/admin/contabilidad/cuentas/{cuenta_id}")
def delete_cuenta(request: Request, cuenta_id: int):
    """Baja lógica de una cuenta (falla si tiene saldo distinto de cero)."""
    admin = require_admin(request)
    with get_db() as conn:
        try:
            cuenta = desactivar_cuenta(conn, cuenta_id, por=admin.get("email"))
            conn.commit()
            return cuenta
        except ValueError as e:
            conn.rollback()
            raise HTTPException(400, str(e))
        except Exception:
            conn.rollback()
            raise
