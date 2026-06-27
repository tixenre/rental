"""Eventos de mantenimiento por equipo (#501 fase a — extraído de `core`).

Registra sus rutas en el router compartido del paquete `routes.equipos`. Tabla
propia (`equipo_mantenimiento`); sin dependencias de otros helpers de equipos.
"""
from typing import Optional

from fastapi import HTTPException, Request
from pydantic import BaseModel

from admin_guard import require_admin
from database import get_db, row_to_dict
from routes.equipos.core import router


class MantenimientoCreate(BaseModel):
    fecha:            str
    tipo:             Optional[str] = "revision"   # revision / reparacion / limpieza / otro
    descripcion:      Optional[str] = None
    costo:            Optional[int] = None
    proxima_revision: Optional[str] = None
    # Bloqueo de disponibilidad: si bloquea_stock=True, saca `cantidad`
    # unidades del equipo durante [fecha, fecha_hasta].
    fecha_hasta:      Optional[str] = None
    cantidad:         int = 1
    bloquea_stock:    bool = False


class MantenimientoUpdate(BaseModel):
    fecha:            Optional[str] = None
    tipo:             Optional[str] = None
    descripcion:      Optional[str] = None
    costo:            Optional[int] = None
    proxima_revision: Optional[str] = None
    fecha_hasta:      Optional[str] = None
    cantidad:         Optional[int] = None
    bloquea_stock:    Optional[bool] = None


@router.get("/equipos/{id}/mantenimiento")
def list_mantenimiento(id: int):
    """Lista los eventos de mantenimiento del equipo, más recientes primero."""
    with get_db() as conn:
        if not conn.execute("SELECT id FROM equipos WHERE id=%s", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        rows = conn.execute("""
            SELECT id, equipo_id, fecha, tipo, descripcion, costo, proxima_revision,
                   fecha_hasta, cantidad, bloquea_stock, created_at
            FROM equipo_mantenimiento WHERE equipo_id = %s
            ORDER BY fecha DESC, id DESC
        """, (id,)).fetchall()
        items = [row_to_dict(r) for r in rows]
        # Proxima revisión pendiente más cercana (futura o vencida).
        pendientes = [r for r in items if r.get("proxima_revision")]
        proxima = min(pendientes, key=lambda r: r["proxima_revision"]) if pendientes else None
        return {
            "items": items,
            "stats": {
                "total_eventos": len(items),
                "total_costo": sum((r.get("costo") or 0) for r in items),
                "proxima_revision": proxima["proxima_revision"] if proxima else None,
            },
        }


@router.post("/equipos/{id}/mantenimiento", status_code=201)
def add_mantenimiento(id: int, data: MantenimientoCreate, request: Request):
    """Agrega un evento de mantenimiento al equipo."""
    require_admin(request)
    with get_db() as conn:
        try:
            if not conn.execute("SELECT id FROM equipos WHERE id=%s", (id,)).fetchone():
                raise HTTPException(404, "Equipo no encontrado")
            new_id = conn.insert_returning("""
                INSERT INTO equipo_mantenimiento
                    (equipo_id, fecha, tipo, descripcion, costo, proxima_revision,
                     fecha_hasta, cantidad, bloquea_stock)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (id, data.fecha, data.tipo or "revision", data.descripcion, data.costo,
                  data.proxima_revision or None, data.fecha_hasta or None, max(1, data.cantidad),
                  data.bloquea_stock))
            conn.commit()
            row = conn.execute(
                "SELECT * FROM equipo_mantenimiento WHERE id = %s", (new_id,)
            ).fetchone()
            return row_to_dict(row)
        except Exception:
            conn.rollback()
            raise


@router.patch("/equipos/{id}/mantenimiento/{log_id}")
def update_mantenimiento(id: int, log_id: int, data: MantenimientoUpdate, request: Request):
    """Actualiza un evento de mantenimiento existente."""
    require_admin(request)
    with get_db() as conn:
        try:
            existing = conn.execute(
                "SELECT * FROM equipo_mantenimiento WHERE id = %s AND equipo_id = %s",
                (log_id, id),
            ).fetchone()
            if not existing:
                raise HTTPException(404, "Evento no encontrado")
            updates = data.model_dump(exclude_unset=True)
            if not updates:
                raise HTTPException(400, "Nada para actualizar")
            # Columnas TIMESTAMP: '' rompe el cast → normalizar a NULL.
            for k in ("fecha_hasta", "proxima_revision"):
                if k in updates and not updates[k]:
                    updates[k] = None
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE equipo_mantenimiento SET {set_clause} WHERE id = %s",
                list(updates.values()) + [log_id],
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM equipo_mantenimiento WHERE id = %s", (log_id,)
            ).fetchone()
            return row_to_dict(row)
        except Exception:
            conn.rollback()
            raise


@router.delete("/equipos/{id}/mantenimiento/{log_id}", status_code=204)
def delete_mantenimiento(id: int, log_id: int, request: Request):
    """Elimina un evento de mantenimiento."""
    require_admin(request)
    with get_db() as conn:
        try:
            existing = conn.execute(
                "SELECT id FROM equipo_mantenimiento WHERE id = %s AND equipo_id = %s",
                (log_id, id),
            ).fetchone()
            if not existing:
                raise HTTPException(404, "Evento no encontrado")
            conn.execute("DELETE FROM equipo_mantenimiento WHERE id = %s", (log_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
