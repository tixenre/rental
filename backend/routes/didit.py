"""routes/didit.py — Verificación de identidad con Didit (DNI + selfie → RENAPER).

Expone dos endpoints:

  POST /api/admin/verificacion/sesion/{cliente_id}
      Admin crea una sesión de Didit para un cliente dado y guarda el session_id.
      Devuelve la URL a la que hay que redirigir al cliente para el flujo de
      verificación (puede enviarse por mail o copiarse en el portal).
      Requiere sesión admin. Si DIDIT_API_KEY no está seteada devuelve 503.

  POST /api/webhooks/didit
      Webhook público — Didit llama aquí al finalizar una verificación.
      No requiere sesión de usuario; la autenticación es la firma HMAC-SHA256
      (X-Signature-V2) + freshness del X-Timestamp.
      En estado "Approved": guarda dni, cuil, dni_validado_at en clientes.

Datos personales (Ley 25.326):
  - Solo se guardan el DNI número, CUIL y timestamp de validación.
  - La foto del DNI nunca llega a nuestra base (Didit la procesa internamente).
  - Accesos admin-only a los campos sensibles.
  - No se loguea el body del webhook (puede contener datos RENAPER).
"""

import logging
from datetime import timezone, datetime

from fastapi import APIRouter, HTTPException, Request

from admin_guard import require_admin
from config import settings
from database import get_db, now_ar
from services.didit import (
    DiditNotConfiguredError,
    DiditSignatureError,
    create_session,
    verify_webhook,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# URL canónica del webhook (la que le damos a Didit al crear la sesión).
_WEBHOOK_PATH = "/api/webhooks/didit"


# ── Admin: crear sesión ──────────────────────────────────────────────────────

@router.post("/admin/verificacion/sesion/{cliente_id}", status_code=201)
def iniciar_verificacion(cliente_id: int, request: Request):
    """Crea una sesión de verificación Didit para el cliente indicado.

    Guarda el didit_session_id en clientes inmediatamente (para poder
    correlacionar el webhook entrante con el cliente correcto).

    Returns:
        { session_id, url }  — url es la que el admin le manda al cliente.

    503 si DIDIT_API_KEY no está configurada.
    404 si el cliente no existe.
    """
    require_admin(request)

    with get_db() as conn:
        row = conn.execute("SELECT id FROM clientes WHERE id=?", (cliente_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Cliente no encontrado")

    callback_url = f"{settings.SITE_URL}{_WEBHOOK_PATH}"
    try:
        sesion = create_session(
            callback_url=callback_url,
            vendor_data=str(cliente_id),
        )
    except DiditNotConfiguredError:
        raise HTTPException(503, "Verificación de identidad no habilitada (DIDIT_API_KEY)")

    with get_db() as conn:
        conn.execute(
            "UPDATE clientes SET didit_session_id=?, updated_at=? WHERE id=?",
            (sesion.session_id, now_ar(), cliente_id),
        )
        conn.commit()

    logger.info("didit: sesión creada session_id=%s cliente_id=%s", sesion.session_id, cliente_id)
    return {"session_id": sesion.session_id, "url": sesion.url}


# ── Webhook público ──────────────────────────────────────────────────────────

@router.post("/webhooks/didit", status_code=200)
async def webhook_didit(request: Request):
    """Recibe eventos status.updated de Didit. Autenticado solo por HMAC.

    Flujo:
      1. Lee el body raw (antes de parsear JSON).
      2. Verifica firma HMAC-SHA256 (X-Signature-V2) + freshness (X-Timestamp).
      3. Si status == "Approved": actualiza clientes con dni, cuil, dni_validado_at.
      4. Siempre devuelve 200 (Didit reintenta en 4xx/5xx — idempotente).

    No loguea el body completo (puede contener datos RENAPER / Ley 25.326).
    """
    body = await request.body()
    signature = request.headers.get("X-Signature-V2", "")
    timestamp = request.headers.get("X-Timestamp", "")

    try:
        verify_webhook(body=body, signature=signature, timestamp=timestamp)
    except DiditSignatureError as exc:
        logger.warning("didit webhook: firma rechazada — %s", exc)
        raise HTTPException(401, "Firma inválida")

    try:
        payload = await request.json()
    except Exception:
        # Body malformado pero firma válida — raro en la práctica (Didit firmó
        # su propio JSON). Devolvemos 200 para que Didit no reintente; logueamos
        # para diagnóstico.
        logger.error("didit webhook: body no es JSON válido session_id=%s", request.headers.get("X-Didit-Session-Id", ""))
        return {"ok": True}

    session_id = payload.get("session_id", "")
    status = payload.get("status", "")
    logger.info("didit webhook: session_id=%s status=%s", session_id, status)

    if status != "Approved":
        # Otros estados (Processing, Declined, etc.) se ignoran por ahora.
        return {"ok": True}

    # Extraer datos validados por RENAPER.
    kyc = payload.get("kyc") or {}
    doc = kyc.get("document") or {}
    dni = (doc.get("document_number") or "").strip() or None
    cuil = (doc.get("tax_id") or doc.get("cuil") or "").strip() or None

    # vendor_data es el cliente_id que pasamos al crear la sesión.
    vendor_data = payload.get("vendor_data", "")
    try:
        cliente_id = int(vendor_data)
    except (ValueError, TypeError):
        logger.error("didit webhook: vendor_data inválido %r session_id=%s", vendor_data, session_id)
        return {"ok": True}  # Devolvemos 200 para que Didit no reintente.

    _guardar_verificacion(
        cliente_id=cliente_id,
        session_id=session_id,
        dni=dni,
        cuil=cuil,
    )
    return {"ok": True}


def _guardar_verificacion(
    *,
    cliente_id: int,
    session_id: str,
    dni: str | None,
    cuil: str | None,
) -> None:
    """Persiste los datos verificados en clientes. Idempotente."""
    ahora = now_ar()
    with get_db() as conn:
        conn.execute(
            """UPDATE clientes
               SET dni=?,
                   cuil=COALESCE(?, cuil),
                   dni_validado_at=?,
                   didit_session_id=?,
                   updated_at=?
               WHERE id=?""",
            (dni, cuil, ahora, session_id, ahora, cliente_id),
        )
        conn.commit()
    logger.info(
        "didit: cliente_id=%s verificado dni=%s session_id=%s",
        cliente_id,
        dni,
        session_id,
    )
