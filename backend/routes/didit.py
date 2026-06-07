"""routes/didit.py — Verificación de identidad con Didit (DNI + selfie → RENAPER).

Expone tres endpoints:

  POST /api/admin/verificacion/sesion/{cliente_id}
      Admin crea una sesión de Didit para un cliente dado. Requiere sesión admin.
      Si DIDIT_API_KEY no está seteada devuelve 503.

  POST /api/cliente/verificacion/sesion
      El cliente autenticado crea su propia sesión. Requiere sesión cliente.
      Devuelve la URL a la que hay que redirigir al cliente para el flujo Didit.

  POST /api/webhooks/didit
      Webhook público — Didit llama aquí al finalizar una verificación.
      Autenticado solo por firma HMAC-SHA256 (X-Signature-V2) + freshness (X-Timestamp).
      En estado "Approved": guarda dni, cuil, nombre/apellido/fecha-nacimiento/
      dirección de RENAPER y marca dni_validado_at en clientes.

Datos personales (Ley 25.326):
  - Solo se persiste texto plano (nombre, DNI, CUIL, fecha nacimiento, dirección).
  - La foto del DNI nunca llega a nuestra base (Didit la procesa internamente).
  - No se loguea el body del webhook (puede contener datos RENAPER).
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from admin_guard import require_admin
from config import settings
from database import get_db, now_ar
from routes.cliente_portal import require_cliente
from services.didit import (
    DiditNotConfiguredError,
    DiditSignatureError,
    create_session,
    verify_webhook,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# El webhook (server-to-server) NO se pasa por sesión: se configura una sola vez
# en el Console de Didit apuntando a /api/webhooks/didit (de ahí sale el secret).
# Lo que SÍ se pasa por sesión es la URL de **retorno del usuario**: a dónde lo
# manda Didit cuando termina el flujo. Lo devolvemos al portal con un flag para
# que la pantalla de Identidad muestre el estado "confirmando…" mientras llega
# el webhook (el webhook es asíncrono, puede tardar unos segundos).
_RETURN_PATH = "/cliente/portal?verificacion=pendiente"


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

    return_url = f"{settings.SITE_URL}{_RETURN_PATH}"
    try:
        sesion = create_session(
            return_url=return_url,
            vendor_data=str(cliente_id),
        )
    except DiditNotConfiguredError:
        raise HTTPException(503, "Verificación de identidad no habilitada (DIDIT_API_KEY)")
    except Exception as exc:
        logger.error("didit: error al crear sesión admin cliente_id=%s — %s", cliente_id, exc)
        raise HTTPException(503, "No se pudo conectar con el servicio de verificación")

    with get_db() as conn:
        conn.execute(
            "UPDATE clientes SET didit_session_id=?, updated_at=? WHERE id=?",
            (sesion.session_id, now_ar(), cliente_id),
        )
        conn.commit()

    logger.info("didit: sesión creada session_id=%s cliente_id=%s", sesion.session_id, cliente_id)
    return {"session_id": sesion.session_id, "url": sesion.url}


# ── Cliente: crear sesión propia ─────────────────────────────────────────────

@router.post("/cliente/verificacion/sesion", status_code=201)
def cliente_iniciar_verificacion(request: Request):
    """El cliente autenticado crea su propia sesión de verificación Didit.

    Guarda el didit_session_id para correlacionar el webhook con el cliente.
    Devuelve la URL a la que hay que redirigir al cliente para el flujo Didit.

    503 si DIDIT_API_KEY no está configurada.
    """
    session = require_cliente(request)
    cliente_id = session["cliente_id"]

    return_url = f"{settings.SITE_URL}{_RETURN_PATH}"
    try:
        sesion = create_session(
            return_url=return_url,
            vendor_data=str(cliente_id),
        )
    except DiditNotConfiguredError:
        raise HTTPException(503, "Verificación de identidad no habilitada")
    except Exception as exc:
        logger.error("didit: error al crear sesión cliente_id=%s — %s", cliente_id, exc)
        raise HTTPException(503, "No se pudo conectar con el servicio de verificación")

    with get_db() as conn:
        conn.execute(
            "UPDATE clientes SET didit_session_id=?, updated_at=? WHERE id=?",
            (sesion.session_id, now_ar(), cliente_id),
        )
        conn.commit()

    logger.info("didit: cliente %s inició verificación session_id=%s", cliente_id, sesion.session_id)
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

    # Extraer datos validados por RENAPER. No se logea el body completo (Ley 25.326).
    kyc = payload.get("kyc") or {}
    doc = kyc.get("document") or {}
    dni = (doc.get("document_number") or "").strip() or None
    cuil = (doc.get("tax_id") or doc.get("cuil") or "").strip() or None
    nombre_renaper = (doc.get("first_name") or "").strip() or None
    apellido_renaper = (doc.get("last_name") or "").strip() or None
    fecha_nacimiento_renaper = (doc.get("date_of_birth") or "").strip() or None
    addr_raw = doc.get("full_address") or doc.get("address") or {}
    if isinstance(addr_raw, dict):
        direccion_renaper = (addr_raw.get("formatted_address") or "").strip() or None
    else:
        direccion_renaper = (str(addr_raw)).strip() or None

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
        nombre_renaper=nombre_renaper,
        apellido_renaper=apellido_renaper,
        fecha_nacimiento_renaper=fecha_nacimiento_renaper,
        direccion_renaper=direccion_renaper,
    )
    return {"ok": True}


def _guardar_verificacion(
    *,
    cliente_id: int,
    session_id: str,
    dni: str | None,
    cuil: str | None,
    nombre_renaper: str | None = None,
    apellido_renaper: str | None = None,
    fecha_nacimiento_renaper: str | None = None,
    direccion_renaper: str | None = None,
) -> None:
    """Persiste los datos verificados por RENAPER en clientes. Idempotente.

    Solo actualiza si el didit_session_id almacenado coincide con el de este
    webhook — previene que un vendor_data forjado marque como verificado a otro
    cliente (el payload ya está firmado con HMAC, esto es defensa en profundidad).
    """
    ahora = now_ar()
    with get_db() as conn:
        conn.execute(
            """UPDATE clientes
               SET dni=?,
                   cuil=COALESCE(?, cuil),
                   dni_validado_at=?,
                   didit_session_id=?,
                   nombre_renaper=COALESCE(?, nombre_renaper),
                   apellido_renaper=COALESCE(?, apellido_renaper),
                   fecha_nacimiento_renaper=COALESCE(?, fecha_nacimiento_renaper),
                   direccion_renaper=COALESCE(?, direccion_renaper),
                   updated_at=?
               WHERE id=? AND didit_session_id=?""",
            (dni, cuil, ahora, session_id,
             nombre_renaper, apellido_renaper, fecha_nacimiento_renaper, direccion_renaper,
             ahora, cliente_id, session_id),
        )
        conn.commit()
    logger.info(
        "didit: cliente_id=%s verificado dni=%s session_id=%s",
        cliente_id,
        dni,
        session_id,
    )
