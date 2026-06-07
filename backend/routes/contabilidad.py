"""routes/contabilidad.py — Módulo contable (#809).

Transporte HTTP fino sobre el motor `backend/contabilidad/` (igual que
`routes/reportes.py` sobre `reportes/`). Fase 1: cuentas (CRUD) + saldos + tablero
mínimo. Acceso = cualquier admin (`require_admin`); el actor de auditoría sale de
`admin.get("email")`.
"""

from fastapi import APIRouter, Request, HTTPException, UploadFile, File
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
from contabilidad.categorias import crear_categoria, listar_categorias
from contabilidad.movimientos import (
    anular_movimiento,
    crear_movimiento,
    editar_movimiento,
    gastos_por_categoria,
    listar_movimientos,
    obtener_movimiento,
)

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


# ── Categorías de gasto ─────────────────────────────────────────────────────

class CategoriaCreate(BaseModel):
    nombre: str


@router.get("/admin/contabilidad/categorias")
def get_categorias(request: Request):
    require_admin(request)
    with get_db() as conn:
        return {"categorias": listar_categorias(conn)}


@router.post("/admin/contabilidad/categorias")
def post_categoria(request: Request, body: CategoriaCreate):
    require_admin(request)
    with get_db() as conn:
        try:
            cat = crear_categoria(conn, body.nombre)
            conn.commit()
            return cat
        except ValueError as e:
            conn.rollback()
            raise HTTPException(400, str(e))
        except Exception:
            conn.rollback()
            raise


# ── Movimientos (gasto / transferencia / retiro / aporte / ajuste) ──────────

class MovimientoCreate(BaseModel):
    tipo: str
    monto: int
    cuenta_origen_id: int | None = None
    cuenta_destino_id: int | None = None
    categoria_id: int | None = None
    metodo: str | None = None
    fecha: str | None = None
    nota: str | None = None


class MovimientoUpdate(BaseModel):
    monto: int | None = None
    cuenta_origen_id: int | None = None
    cuenta_destino_id: int | None = None
    categoria_id: int | None = None
    metodo: str | None = None
    fecha: str | None = None
    nota: str | None = None


class AnularBody(BaseModel):
    motivo: str


@router.get("/admin/contabilidad/movimientos")
def get_movimientos(
    request: Request,
    tipo: str | None = None,
    cuenta_id: int | None = None,
    categoria_id: int | None = None,
    desde: str | None = None,
    hasta: str | None = None,
    incluir_anulados: bool = False,
    limit: int = 500,
):
    require_admin(request)
    with get_db() as conn:
        movs = listar_movimientos(
            conn, tipo=tipo, cuenta_id=cuenta_id, categoria_id=categoria_id,
            desde=desde, hasta=hasta, incluir_anulados=incluir_anulados, limit=limit,
        )
    return {"movimientos": movs, "count": len(movs)}


@router.post("/admin/contabilidad/movimientos")
def post_movimiento(request: Request, body: MovimientoCreate):
    """Registra un movimiento (gasto/transferencia/retiro/aporte/ajuste)."""
    admin = require_admin(request)
    with get_db() as conn:
        try:
            mov = crear_movimiento(
                conn, tipo=body.tipo, monto=body.monto,
                cuenta_origen_id=body.cuenta_origen_id,
                cuenta_destino_id=body.cuenta_destino_id,
                categoria_id=body.categoria_id, metodo=body.metodo,
                fecha=body.fecha, nota=body.nota, por=admin.get("email"),
            )
            conn.commit()
            return mov
        except ValueError as e:
            conn.rollback()
            raise HTTPException(400, str(e))
        except Exception:
            conn.rollback()
            raise


@router.patch("/admin/contabilidad/movimientos/{mov_id}")
def patch_movimiento(request: Request, mov_id: int, body: MovimientoUpdate):
    admin = require_admin(request)
    campos = body.model_dump(exclude_unset=True)
    with get_db() as conn:
        try:
            mov = editar_movimiento(conn, mov_id, campos=campos, por=admin.get("email"))
            conn.commit()
            return mov
        except ValueError as e:
            conn.rollback()
            raise HTTPException(400, str(e))
        except Exception:
            conn.rollback()
            raise


@router.post("/admin/contabilidad/movimientos/{mov_id}/anular")
def anular_mov(request: Request, mov_id: int, body: AnularBody):
    """Soft-delete con motivo: la plata nunca se borra, queda anulada y trazable."""
    admin = require_admin(request)
    with get_db() as conn:
        try:
            mov = anular_movimiento(conn, mov_id, motivo=body.motivo, por=admin.get("email"))
            conn.commit()
            return mov
        except ValueError as e:
            conn.rollback()
            raise HTTPException(400, str(e))
        except Exception:
            conn.rollback()
            raise


_COMPROBANTE_MAX = 5 * 1024 * 1024  # 5 MB
_COMPROBANTE_TIPOS = ("application/pdf", "image/jpeg", "image/png", "image/webp")


@router.post("/admin/contabilidad/movimientos/{mov_id}/comprobante")
async def subir_comprobante(request: Request, mov_id: int, file: UploadFile = File(...)):
    """Adjunta un comprobante (PDF o imagen) a un movimiento. Sube a R2 reusando
    la infra de media (`services/media/storage`)."""
    require_admin(request)
    content = await file.read()
    if len(content) > _COMPROBANTE_MAX:
        raise HTTPException(400, "El comprobante supera los 5 MB.")
    ctype = (file.content_type or "").lower()
    if ctype not in _COMPROBANTE_TIPOS:
        raise HTTPException(400, "Formato no soportado (subí un PDF o una imagen).")

    with get_db() as conn:
        mov = obtener_movimiento(conn, mov_id)
        if not mov:
            raise HTTPException(404, "El movimiento no existe.")
        try:
            from services.media import storage

            ext = {"application/pdf": "pdf", "image/jpeg": "jpg",
                   "image/png": "png", "image/webp": "webp"}.get(ctype, "bin")
            key = f"contabilidad/comprobantes/{mov_id}/comprobante.{ext}"
            url = storage.put(key, content, ctype)
            # Borrado best-effort del comprobante anterior si cambia la key.
            vieja = mov.get("comprobante_key")
            if vieja and vieja != key:
                storage.delete_object(vieja)
            conn.execute(
                "UPDATE movimientos SET comprobante_url = ?, comprobante_key = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (url, key, mov_id),
            )
            conn.commit()
            return {"comprobante_url": url}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(502, f"No se pudo subir el comprobante: {e}")


@router.get("/admin/contabilidad/gastos")
def get_gastos(request: Request, desde: str | None = None, hasta: str | None = None):
    """Gastos agrupados por categoría en la ventana (para el tablero / análisis)."""
    require_admin(request)
    with get_db() as conn:
        filas = gastos_por_categoria(conn, desde, hasta)
    return {"por_categoria": filas, "total": sum(f["monto"] for f in filas)}
