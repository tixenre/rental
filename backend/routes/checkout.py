"""routes/checkout.py — Portero del checkout (transporte HTTP).

POST /api/checkout/validar
    Valida todas las precondiciones antes de crear un pedido y devuelve
    {listo, faltan}. Corre todos los checks (fail-not-fast) para que la UI
    muestre exactamente qué resolver. No crea pedidos.

POST /api/checkout/aceptar-tyc
    Registra la aceptación de la versión actual de T&C para el cliente.

Ver `docs/SISTEMA_CHECKOUT.md` para el flujo completo y el contrato de respuesta.
"""

import uuid as _uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from auth.stepup import has_recent_stepup
from database import get_db
from routes.cliente_portal import require_cliente
from services.checkout import registrar_aceptacion, validar_checkout

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
        return validar_checkout(
            conn,
            cliente_id=cliente_id,
            session_id=data.session_id,
            firma_ok=firma_ok,
        )


@router.post("/checkout/aceptar-tyc")
def checkout_aceptar_tyc(request: Request):
    """Registra la aceptación de T&C (versión actual) para el cliente logueado."""
    session = require_cliente(request)
    cliente_id: int = session["cliente_id"]

    with get_db() as conn:
        registrar_aceptacion(conn, cliente_id)
        conn.commit()

    return {"ok": True}
