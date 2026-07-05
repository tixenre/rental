"""Endpoints públicos de apoyo al catálogo/picker de fechas del cliente (#1237).

  GET /api/public/rental/disclaimers → avisos del date picker (antelación
      mínima, horarios reducidos de fin de semana) contextuales a la fecha
      elegida. La regla ("¿corresponde avisar?") y el texto exacto viven en
      `services.fechas.disclaimers_retiro` — el front (DateRangePickerModal)
      antes los reimplementaba en TS; ahora solo pide y muestra.

El prefijo `/api/public/` ya está en `middleware.PUBLIC_API_ANY` (sin sesión),
mismo patrón que `routes/compartir.py`.
"""
from fastapi import APIRouter, Query

from database import get_db
from services.fechas import disclaimers_retiro

router = APIRouter(tags=["rental-publico"])


@router.get("/public/rental/disclaimers")
def get_disclaimers_retiro(
    fecha_desde: str | None = Query(None, description="YYYY-MM-DD o YYYY-MM-DDTHH:MM"),
    fecha_hasta: str | None = Query(None, description="YYYY-MM-DD o YYYY-MM-DDTHH:MM"),
):
    """Avisos relevantes para la selección actual del picker (o para cuando
    todavía no hay fecha elegida). Ver `disclaimers_retiro` — solo devuelve lo
    que aplica, no una lista fija de reglas."""
    with get_db() as conn:
        return {"disclaimers": disclaimers_retiro(conn, fecha_desde, fecha_hasta)}
