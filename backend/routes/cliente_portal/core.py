"""routes/cliente_portal/core.py — spine del paquete del portal del cliente (#501).

El `router` compartido del paquete + el guard `require_cliente` + los helpers y
constantes compartidos por los submódulos (proyección de ítems, ventanas de
modificación, documentos por estado). Las superficies del portal (cuenta, pedidos,
solicitudes, documentos, favoritos) viven en submódulos que registran sus rutas
sobre este router al importarse (ver `__init__`).
"""
import logging
from fastapi import APIRouter, Request, HTTPException
from typing import Optional

from database import to_datetime, now_ar, get_db
from routes.auth import get_session

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


# ── Auth helper ───────────────────────────────────────────────────────────────

def require_cliente(request: Request) -> dict:
    """Devuelve la sesión del cliente (cookie). 401 si no hay sesión válida."""
    session = get_session(request)
    if not session or session.get("role") != "cliente":
        raise HTTPException(401, "Sesión de cliente requerida")
    return session


# Mensaje único del gate de identidad — la UI lo muestra tal cual si llegara a disparar.
IDENTIDAD_NO_VERIFICADA_MSG = (
    "Necesitás verificar tu identidad antes de hacer un pedido. "
    "Verificá tu DNI desde tu portal — tarda menos de 2 minutos."
)


def cliente_verificado(conn, cliente_id: int) -> bool:
    """True si el cliente completó la verificación de identidad (dni_validado_at).
    Fuente única del criterio "está verificado"; usa una conexión ya abierta."""
    row = conn.execute(
        "SELECT dni_validado_at FROM clientes WHERE id = ?", (cliente_id,)
    ).fetchone()
    return bool(row and row["dni_validado_at"])


def require_cliente_verificado(request: Request) -> dict:
    """Como require_cliente pero además exige identidad verificada (el gate del
    flujo de pedidos). 401 sin sesión; 404 si el cliente no existe; 403 si no
    completó la verificación Didit. El criterio "está verificado" lo decide la
    fuente única `cliente_verificado` (no se duplica el chequeo de `dni_validado_at`)."""
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    with get_db() as conn:
        if conn.execute("SELECT 1 FROM clientes WHERE id = ?", (cliente_id,)).fetchone() is None:
            raise HTTPException(404, "Cliente no encontrado.")
        if not cliente_verificado(conn, cliente_id):
            raise HTTPException(403, IDENTIDAD_NO_VERIFICADA_MSG)
    return session


