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

from database import to_datetime
from services.fechas import setting_horas, dentro_de_ventana_horas

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


ESTADOS_MODIFICABLES = {"solicitado", "confirmado"}

# ── Items: fuente única + proyección por superficie ──────────────────────────
# El portal lee los items de un pedido vía los helpers canónicos de
# routes/alquileres (`_get_alquiler_items` / `_batch_get_alquiler_items` —
# misma query y mismo batch de componentes que el admin) y PROYECTA solo
# estos campos: al cliente no se le expone `pi.*` completo ni stock interno.
_ITEM_CAMPOS_PORTAL = (
    "cantidad", "precio_jornada", "subtotal", "equipo_id", "nombre", "marca",
    "modelo", "foto_url", "nombre_publico", "nombre_publico_largo",
)
# Los documentos (contrato/remito/albarán/checklist) suman los campos de
# identificación del equipo + los que usa el checklist de retiro (fecha de
# compra, accesorios incluidos vía `_contenido_pairs` en pdf_templates.py).
_ITEM_CAMPOS_DOC = _ITEM_CAMPOS_PORTAL + (
    "serie", "valor_reposicion", "fecha_compra", "contenido_incluido_json",
)
_COMP_CAMPOS_DOC = (
    "cantidad", "nombre", "marca", "modelo", "serie", "valor_reposicion",
    "nombre_publico", "nombre_publico_largo",
)


def _proyectar(item: dict, campos: tuple) -> dict:
    return {k: item.get(k) for k in campos}


def _modificacion_ventana_horas(conn) -> int:
    """Ventana de corte (en horas) para modificar un pedido, configurada en
    `app_settings.modificacion_ventana_horas` (default 24). Fuente única del lector
    de horas: `services.fechas.setting_horas`."""
    return setting_horas(conn, "modificacion_ventana_horas", 24)


def _ventana_cumple(fecha_desde: Optional[str], ventana_horas: int) -> bool:
    """True si todavía estamos a >= ventana_horas del retiro (o si no hay fecha).
    Es la negación de la ventana de tiempo compartida (`dentro_de_ventana_horas`):
    cumple = el retiro NO cae dentro de las próximas `ventana_horas`."""
    if not fecha_desde:
        return True
    return not dentro_de_ventana_horas(to_datetime(fecha_desde), ventana_horas)


# ── Documentos disponibles según estado del pedido ───────────────────────────

def _documentos_disponibles(estado: str) -> dict:
    """Devuelve qué PDFs puede descargar el cliente según el estado del pedido.

    Los cuatro (Remito, Contrato, Detalle de seguro, Checklist de retiro) están
    disponibles desde "solicitado" — apenas se solicita, antes de que Rambla
    lo confirme — para que el cliente tenga tiempo de leerlos o consultar a
    su aseguradora sin esperar. El pedido puede seguir modificándose hasta
    que se confirma (`ESTADOS_MODIFICABLES` incluye "solicitado"), así que
    cada PDF sigue mostrando el badge de estado real (`_membrete(..., estado=True)`
    en pdf_templates.py) como disclaimer — un pedido en "Presupuesto" queda
    visiblemente marcado como provisorio, no como confirmado. "borrador"
    (solo admin, nunca un pedido de cliente) y "cancelado" quedan afuera."""
    e = (estado or "").lower()
    disponible = e not in ("borrador", "cancelado", "")
    return {
        "remito": disponible,
        "contrato": disponible,
        "albaran": disponible,
        "packing-list": disponible,
    }


# (Los guards de cliente —require_cliente / require_cliente_verificado /
# cliente_verificado / IDENTIDAD_NO_VERIFICADA_MSG— se movieron a auth/guards.py
# y se re-exportan en el bloque de imports de arriba.)


