"""routes/checkout.py — Portero del checkout (transporte HTTP).

POST /api/checkout/validar
    Valida todas las precondiciones antes de crear un pedido y devuelve
    {listo, faltan}. Corre todos los checks (fail-not-fast) para que la UI
    muestre exactamente qué resolver. No crea pedidos.

POST /api/checkout/aceptar-tyc
    Registra la aceptación de la versión actual de T&C para el cliente.

POST /api/checkout/contrato-preview
    Preview HTML del contrato del pedido EN CURSO (antes de crearlo) — el
    cliente lee el contrato real que va a firmar antes de confirmar.

Ver `docs/SISTEMA_CHECKOUT.md` para el flujo completo y el contrato de respuesta.
"""

import logging
import uuid as _uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from auth.stepup import has_recent_stepup
from database import get_db, now_ar, row_to_dict, MARCA_SUBQUERY
from identity import nombre_validado, direccion_validada
from identity.contacts import email_comunicacion, telefono_contacto
from pdf import _contrato_html
from routes.cliente_portal import require_cliente
from services.carrito import desde_items_json
from services.checkout import registrar_aceptacion, validar_checkout
from services.checkout.validar import _leer_carrito
from services.contenido import contenido_de_batch

logger = logging.getLogger(__name__)
router = APIRouter(tags=["checkout"])


class CheckoutValidarIn(BaseModel):
    session_id: str
    # Fallback de firma: el cliente clickeó "Confirmo". La modalidad preferida
    # es el passkey step-up (has_recent_stepup); esto cubre clientes sin passkey.
    session_confirmed: bool = False


@router.post("/checkout/validar")
def checkout_validar(data: CheckoutValidarIn, request: Request):
    """Portero del checkout — devuelve {listo, faltan}."""
    try:
        _uuid.UUID(data.session_id)
    except ValueError:
        raise HTTPException(400, "session_id inválido — debe ser UUID v4")

    session = require_cliente(request)
    cliente_id: int = session["cliente_id"]

    firma_ok = has_recent_stepup(request, cliente_id) or data.session_confirmed

    with get_db() as conn:
        try:
            return validar_checkout(
                conn,
                cliente_id=cliente_id,
                session_id=data.session_id,
                firma_ok=firma_ok,
            )
        except Exception:
            # El portero ya aísla cada check (`_run_check`) — esto es la red
            # residual para lo que corre ANTES/fuera de esos checks (ej. el
            # guard de auth, o un bug en el propio `validar_checkout`). Nunca
            # un 500 crudo con detalle interno; se loguea con contexto para
            # diagnosticar.
            logger.exception(
                "checkout: error inesperado en el portero (cliente_id=%s, session_id=%s)",
                cliente_id, data.session_id,
            )
            raise HTTPException(503, "No pudimos validar tu pedido. Reintentá en unos segundos.")


@router.post("/checkout/aceptar-tyc")
def checkout_aceptar_tyc(request: Request):
    """Registra la aceptación de T&C (versión actual) para el cliente logueado."""
    session = require_cliente(request)
    cliente_id: int = session["cliente_id"]

    with get_db() as conn:
        registrar_aceptacion(conn, cliente_id)
        conn.commit()

    return {"ok": True}


class ContratoPreviewIn(BaseModel):
    session_id: str


def _marcar_como_simulacion(html_str: str) -> str:
    """Envuelve el HTML del contrato REAL (mismo `_contrato_html` del pedido ya
    creado) con un aviso de SIMULACIÓN — banner fijo arriba + marca de agua
    diagonal. El pedido todavía no existe: el documento definitivo recién es
    válido cuando se confirma (queda en el portal + se manda por mail)."""
    banner = (
        '<div style="position:sticky;top:0;z-index:20;background:#fef3c7;'
        'color:#78350f;font-family:var(--font-mono,monospace);font-size:12px;'
        'text-align:center;padding:10px 16px;border-bottom:2px solid #f59e0b;'
        'letter-spacing:.02em">'
        "Vista previa — simulación para que leas el contrato antes de confirmar. "
        "No es un documento válido: el contrato definitivo va a estar disponible "
        "en tu portal y te lo mandamos por mail cuando confirmes el pedido."
        "</div>"
    )
    watermark = (
        '<div style="position:fixed;inset:0;pointer-events:none;z-index:10;'
        'display:flex;align-items:center;justify-content:center;overflow:hidden">'
        '<span style="font-family:var(--font-mono,monospace);font-weight:700;'
        'font-size:64px;color:rgba(190,24,93,.08);transform:rotate(-32deg);'
        'white-space:nowrap;letter-spacing:.08em">SIMULACIÓN — NO VÁLIDO</span>'
        "</div>"
    )
    return html_str.replace("<body>", "<body>" + banner + watermark, 1)


@router.post("/checkout/contrato-preview")
def checkout_contrato_preview(data: ContratoPreviewIn, request: Request):
    """Preview del CONTRATO del pedido EN CURSO — antes de crearlo. Arma un
    `pedido` equivalente en memoria desde el carrito de la sesión (mismo
    `_leer_carrito` que usa el portero) y llama al mismo `_contrato_html` que
    genera el contrato real — no persiste nada, no crea el pedido. El HTML
    vuelve marcado como SIMULACIÓN (`_marcar_como_simulacion`): el documento
    definitivo recién es válido al confirmar el pedido. Sienta base para la
    firma digital de #1098 Fase 5 (leer antes de firmar)."""
    try:
        _uuid.UUID(data.session_id)
    except ValueError:
        raise HTTPException(400, "session_id inválido — debe ser UUID v4")

    session = require_cliente(request)
    cliente_id: int = session["cliente_id"]

    try:
        with get_db() as conn:
            carrito = _leer_carrito(conn, data.session_id, cliente_id)
            if carrito is None:
                raise HTTPException(404, "No encontramos tu carrito.")

            # `desde_items_json` (services/carrito, fuente única) resuelve la
            # ambigüedad lista-ya-deserializada vs. string JSON — mismo patrón
            # usado en carritos.py/compartir.py/listas.py, no reimplementado acá.
            cantidad_por_id = {
                int(it["equipo_id"]): int(it["cantidad"])
                for it in desde_items_json(carrito.get("items_json"))
                if it.get("equipo_id")
            }
            eq_ids = list(cantidad_por_id.keys())
            if not eq_ids:
                raise HTTPException(400, "Tu carrito está vacío.")

            ph = ",".join("%s" for _ in eq_ids)
            rows = conn.execute(
                f"""SELECT id AS equipo_id, nombre, {MARCA_SUBQUERY}, modelo, serie,
                           valor_reposicion, nombre_publico, nombre_publico_largo
                    FROM equipos e
                    WHERE id IN ({ph}) AND eliminado_at IS NULL""",
                tuple(eq_ids),
            ).fetchall()
            componentes = contenido_de_batch(conn, eq_ids)
            items = []
            for r in rows:
                eq = row_to_dict(r)
                eq["cantidad"] = cantidad_por_id.get(eq["equipo_id"], 1)
                eq["componentes"] = componentes.get(eq["equipo_id"], [])
                items.append(eq)

            cli = conn.execute(
                """SELECT nombre, apellido, direccion, cuit, perfil_impuestos,
                          razon_social, nombre_renaper, apellido_renaper,
                          direccion_renaper
                   FROM clientes WHERE id = %s""",
                (cliente_id,),
            ).fetchone()
            c = row_to_dict(cli) if cli else {}

            pedido = {
                "id": "preview",
                "estado": "presupuesto",
                "fecha_desde": carrito.get("fecha_desde"),
                "fecha_hasta": carrito.get("fecha_hasta"),
                "emitido": now_ar(),
                "items": items,
                "cliente_nombre": nombre_validado(c)
                or f"{c.get('nombre', '')} {c.get('apellido', '')}".strip(),
                "cliente_email": email_comunicacion(conn, cliente_id),
                "cliente_telefono": telefono_contacto(conn, cliente_id),
                "cliente_direccion": direccion_validada(c) or c.get("direccion"),
                "cliente_cuit": c.get("cuit"),
                "cliente_perfil_impuestos": c.get("perfil_impuestos"),
                "cliente_razon_social": c.get("razon_social"),
            }

            # mostrar_locador=False: los datos del Locador (Rambla) son fijos/
            # institucionales, no aportan nada en un preview — lo que importa
            # es que el cliente pueda leer las cláusulas.
            html_str = _marcar_como_simulacion(_contrato_html(pedido, mostrar_locador=False))
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "checkout: error inesperado armando el preview del contrato (cliente_id=%s, session_id=%s)",
            cliente_id, data.session_id,
        )
        raise HTTPException(503, "No pudimos generar el preview del contrato. Reintentá en unos segundos.")

    return HTMLResponse(
        content=html_str,
        headers={"X-Frame-Options": "SAMEORIGIN", "Cache-Control": "no-store, max-age=0"},
    )
