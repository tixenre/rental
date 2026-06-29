"""routes/cliente_portal/core.py — spine del paquete del portal del cliente (#501).

El `router` compartido del paquete + el guard `require_cliente` + los helpers y
constantes compartidos por los submódulos (proyección de ítems, ventanas de
modificación, documentos por estado). Las superficies del portal (cuenta, pedidos,
solicitudes, documentos, favoritos) viven en submódulos que registran sus rutas
sobre este router al importarse (ver `__init__`).
"""
import logging
from fastapi import APIRouter
from typing import Optional

from database import to_datetime, now_ar

# Guards de cliente: viven en auth/guards.py (motor único de auth). Se re-exportan
# acá para que los submódulos del portal y el __init__ los importen desde el spine.
from auth.guards import (  # noqa: F401
    require_cliente,
    require_cliente_verificado,
    cliente_verificado,
    IDENTIDAD_NO_VERIFICADA_MSG,
)
from auth.session import get_session  # noqa: F401  (re-exportado por __init__)

logger = logging.getLogger(__name__)
router = APIRouter()


ESTADOS_MODIFICABLES = {"presupuesto", "confirmado"}

# ── Items: fuente única + proyección por superficie ──────────────────────────
# El portal lee los items de un pedido vía los helpers canónicos de
# routes/alquileres (`_get_alquiler_items` / `_batch_get_alquiler_items` —
# misma query y mismo batch de componentes que el admin) y PROYECTA solo
# estos campos: al cliente no se le expone `pi.*` completo ni stock interno.
_ITEM_CAMPOS_PORTAL = (
    "cantidad", "precio_jornada", "subtotal", "equipo_id", "nombre", "marca",
    "modelo", "foto_url", "nombre_publico", "nombre_publico_largo",
)
# Los documentos (contrato/remito) suman los campos de identificación del equipo.
_ITEM_CAMPOS_DOC = _ITEM_CAMPOS_PORTAL + ("serie", "valor_reposicion")
_COMP_CAMPOS_DOC = (
    "cantidad", "nombre", "marca", "modelo", "serie", "valor_reposicion",
    "nombre_publico", "nombre_publico_largo",
)


def _proyectar(item: dict, campos: tuple) -> dict:
    return {k: item.get(k) for k in campos}


def _modificacion_ventana_horas(conn) -> int:
    """Devuelve la ventana de corte (en horas) configurada en app_settings."""
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = 'modificacion_ventana_horas'"
    ).fetchone()
    try:
        return int(row["value"]) if row else 24
    except (TypeError, ValueError):
        return 24


def _ventana_cumple(fecha_desde: Optional[str], ventana_horas: int) -> bool:
    """True si todavía estamos a >= ventana_horas del retiro (o si no hay fecha)."""
    if not fecha_desde:
        return True
    try:
        d0 = to_datetime(fecha_desde)
    except ValueError:
        return True
    if d0 is None:
        return True
    return (d0 - now_ar()).total_seconds() >= ventana_horas * 3600


# ── Documentos disponibles según estado del pedido ───────────────────────────

def _documentos_disponibles(estado: str) -> dict:
    """Devuelve qué PDFs puede descargar el cliente según el estado del pedido."""
    e = (estado or "").lower()
    confirmado_o_mas = e in ("confirmado", "retirado", "devuelto", "finalizado")
    return {
        "remito": confirmado_o_mas,
        "contrato": confirmado_o_mas,
        "albaran": e in ("retirado", "devuelto", "finalizado"),
    }


# (Los guards de cliente —require_cliente / require_cliente_verificado /
# cliente_verificado / IDENTIDAD_NO_VERIFICADA_MSG— se movieron a auth/guards.py
# y se re-exportan en el bloque de imports de arriba.)


