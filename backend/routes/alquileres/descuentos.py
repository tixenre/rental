"""Descuentos por jornadas (#501 — extraído del god-module `routes/alquileres.py`).

Transporte HTTP fino sobre el motor `backend/descuentos/` (CQRS-lite): la
lógica de la escala de descuento por cantidad de jornadas vive en
`descuentos.queries.jornadas` / `descuentos.commands.jornadas`. Registra sus
rutas en el router compartido del paquete `routes.alquileres`.
"""
from fastapi import Request, HTTPException
from pydantic import BaseModel

from database import get_db
from auth.guards import require_admin
from descuentos.commands.jornadas import crear_descuento_jornada, eliminar_descuento_jornada
from descuentos.queries.jornadas import listar_descuentos_jornada
from routes.alquileres.core import router


# ── Descuentos por jornadas ───────────────────────────────────────────────────

class DescuentoJornadaIn(BaseModel):
    jornadas: int
    pct: float


@router.get("/descuentos-jornada")
def get_descuentos_jornada():
    """Devuelve los puntos ancla de descuentos por jornadas (público — lo usa el carrito)."""
    with get_db() as conn:
        return listar_descuentos_jornada(conn)


@router.post("/admin/descuentos-jornada", status_code=201)
def create_descuento_jornada(data: DescuentoJornadaIn, request: Request):
    require_admin(request)
    with get_db() as conn:
        try:
            return crear_descuento_jornada(conn, jornadas=data.jornadas, pct=data.pct)
        except ValueError as e:
            raise HTTPException(400, str(e))


@router.delete("/admin/descuentos-jornada/{id}", status_code=204)
def delete_descuento_jornada(id: int, request: Request):
    require_admin(request)
    with get_db() as conn:
        eliminar_descuento_jornada(conn, id)
