"""Panel admin de specs no reconocidas (#1203).

Superficie HTTP de la cola `spec_propuestas_pendientes` (Canal C de
`services.specs`, alimentada por `services.specs_ingesta.commands.proponer`):
listado agrupado por label + resolución en bloque. `_require_admin` (guard)
vive en `core`. Ver `services/specs/commands/propuestas.py` para la regla
dura (nunca muta el registry — resolver acá es bookkeeping, el spec/alias
real lo agrega un humano al código y re-siembra).
"""
from typing import Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel

from database import get_db
from rate_limit import limiter, ADMIN_WRITE_LIMIT
from services.specs import aplicar_propuesta, descartar_propuesta, listar_no_reconocidos_agrupados
from routes.specs.core import router, _require_admin


@router.get("/admin/specs/no-reconocidos")
def listar_no_reconocidos(request: Request):
    """Specs sin match agrupadas por (categoría, label) — qué equipos las
    encontraron, valores de ejemplo, listas para clasificar a mano."""
    _require_admin(request)
    with get_db() as conn:
        return {"items": listar_no_reconocidos_agrupados(conn)}


class ResolverNoReconocidosInput(BaseModel):
    propuesta_ids: list[int]
    accion: Literal["aplicado", "descartado"]


@router.post("/admin/specs/no-reconocidos/resolver")
@limiter.limit(ADMIN_WRITE_LIMIT)
def resolver_no_reconocidos(payload: ResolverNoReconocidosInput, request: Request):
    """Cierra en bloque las propuestas subyacentes de un grupo (un label
    agrupado puede tener una fila por equipo). `aplicado`: ya se agregó al
    registry a mano + re-sembró. `descartado`: no corresponde (ruido, o ya
    cubierto por un spec existente)."""
    _require_admin(request)
    if not payload.propuesta_ids:
        raise HTTPException(400, "propuesta_ids vacío")
    accionar = aplicar_propuesta if payload.accion == "aplicado" else descartar_propuesta
    with get_db() as conn:
        for pid in payload.propuesta_ids:
            accionar(conn, pid)
        conn.commit()
    return {"resueltas": len(payload.propuesta_ids)}
