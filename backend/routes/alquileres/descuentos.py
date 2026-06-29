"""Descuentos por jornadas (#501 — extraído del god-module `routes/alquileres.py`).

CRUD de los descuentos por cantidad de jornadas (la escala de descuento que se
aplica según cuántos días dura el alquiler). Registra sus rutas en el router
compartido del paquete `routes.alquileres`.
"""
from fastapi import Request, HTTPException
from pydantic import BaseModel

from database import get_db, row_to_dict
from auth.guards import require_admin
from routes.alquileres.core import router


# ── Descuentos por jornadas ───────────────────────────────────────────────────

class DescuentoJornadaIn(BaseModel):
    jornadas: int
    pct: float


@router.get("/descuentos-jornada")
def get_descuentos_jornada():
    """Devuelve los puntos ancla de descuentos por jornadas (público — lo usa el carrito)."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, jornadas, pct FROM descuentos_jornada ORDER BY jornadas ASC"
        ).fetchall()
        return [row_to_dict(r) for r in rows]


@router.post("/admin/descuentos-jornada", status_code=201)
def create_descuento_jornada(data: DescuentoJornadaIn, request: Request):
    require_admin(request)
    if data.jornadas < 1:
        raise HTTPException(400, "jornadas debe ser >= 1")
    if not (0 <= data.pct <= 100):
        raise HTTPException(400, "pct debe estar entre 0 y 100")
    with get_db() as conn:
        conn.execute(
            "INSERT INTO descuentos_jornada (jornadas, pct) VALUES (%s, %s) "
            "ON CONFLICT (jornadas) DO UPDATE SET pct = EXCLUDED.pct",
            (data.jornadas, data.pct)
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, jornadas, pct FROM descuentos_jornada WHERE jornadas = %s",
            (data.jornadas,)
        ).fetchone()
        return row_to_dict(row)


@router.delete("/admin/descuentos-jornada/{id}", status_code=204)
def delete_descuento_jornada(id: int, request: Request):
    require_admin(request)
    with get_db() as conn:
        conn.execute("DELETE FROM descuentos_jornada WHERE id = %s", (id,))
        conn.commit()
