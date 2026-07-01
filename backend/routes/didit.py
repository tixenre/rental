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
      Autenticado solo por firma HMAC-SHA256 (X-Signature) + freshness (X-Timestamp).
      En estado "Approved": guarda dni, cuil, nombre/apellido/nombre-completo/
      fecha-nacimiento/dirección de RENAPER y marca dni_validado_at en clientes.
      Los datos viven en `decision.id_verifications[]` (API v3) — ver
      services/didit/decision.py.

Datos personales (Ley 25.326):
  - Solo se persiste texto plano (nombre, DNI, CUIL, fecha nacimiento, dirección).
  - La foto del DNI nunca llega a nuestra base (Didit la procesa internamente).
  - No se loguea el body del webhook (puede contener datos RENAPER); el log de
    verificación registra solo PRESENCIA de cada campo (bool), no su valor.
"""

import logging
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from auth.guards import require_admin
from config import settings
from database import get_db, now_ar, row_to_dict
from routes.cliente_portal import require_cliente
from services.didit import (
    DiditNotConfiguredError,
    DiditSignatureError,
    create_session,
    extraer_contactos,
    extraer_datos_renaper,
    retrieve_decision,
    verify_webhook,
)

from identity import kyc

logger = logging.getLogger(__name__)

router = APIRouter()

# El webhook (server-to-server) NO se pasa por sesión: se configura una sola vez
# en el Console de Didit apuntando a /api/webhooks/didit (de ahí sale el secret).
# Lo que SÍ se pasa por sesión es la URL de **retorno del usuario**: a dónde lo
# manda Didit cuando termina el flujo. Lo devolvemos al portal con un flag para
# que la pantalla de Identidad muestre el estado "confirmando…" mientras llega
# el webhook (el webhook es asíncrono, puede tardar unos segundos).
_RETURN_PATH = "/cliente/portal?verificacion=pendiente"


class SesionVerificacionIn(BaseModel):
    return_to: Optional[str] = None


def _es_path_interno_seguro(p: Optional[str]) -> bool:
    """Allowlist anti open-redirect: path interno del propio sitio."""
    if not p or not isinstance(p, str):
        return False
    if len(p) > 512:
        return False
    if not p.startswith("/") or p.startswith("//"):
        return False
    if "://" in p or "\\" in p:
        return False
    if any(ord(c) < 0x20 for c in p):  # control chars (\n \r \t ...)
        return False
    return True


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
        row = conn.execute("SELECT id FROM clientes WHERE id=%s", (cliente_id,)).fetchone()
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
    except httpx.HTTPStatusError as exc:
        # El body ya fue logueado en services/didit/client.py con exc.response.text
        logger.error("didit: %s al crear sesión admin cliente_id=%s", exc.response.status_code, cliente_id)
        raise HTTPException(503, "No se pudo conectar con el servicio de verificación")
    except Exception as exc:
        logger.error("didit: error al crear sesión admin cliente_id=%s — %s", cliente_id, exc)
        raise HTTPException(503, "No se pudo conectar con el servicio de verificación")

    with get_db() as conn:
        conn.execute(
            "UPDATE clientes SET didit_session_id=%s, updated_at=%s WHERE id=%s",
            (sesion.session_id, now_ar(), cliente_id),
        )
        conn.commit()

    logger.info("didit: sesión creada session_id=%s cliente_id=%s", sesion.session_id, cliente_id)
    return {"session_id": sesion.session_id, "url": sesion.url}


# ── Admin: re-chequear el estado actual en Didit ─────────────────────────────

# Estados de sesión que Didit puede devolver (GET .../decision/, campo top-level
# `status`, distinto del `id_verifications[].status` por-feature). Normalizamos
# a minúsculas + espacio→guion-bajo antes de comparar (los valores del webhook
# vienen "In_review"/"Under_review"; la API directa documenta "In Review").
_ESTADOS_EN_REVISION = {"in_review", "under_review", "processing", "in_progress"}


@router.post("/admin/verificacion/recheck/{cliente_id}")
def recheck_verificacion(cliente_id: int, request: Request):
    """Re-consulta a Didit el estado ACTUAL de la sesión del cliente y aplica el
    resultado (aprobar / rechazar / en revisión) por la pluma única `identity.kyc`
    — sin que el admin tenga que validar la identidad a mano.

    Caso de uso: Didit rechazó automáticamente por una razón menor (ej. foto
    oscura), el admin revisó el caso a mano *en el dashboard de Didit* y lo
    aprobó ahí — pero el webhook de esa revisión manual no siempre llega (o ya
    llegó y se perdió). Este endpoint refleja en Rambla lo que Didit devuelve
    HOY, en vez de que el admin tenga que marcarlo aprobado él mismo.

    404 si el cliente no existe. 409 si nunca inició una verificación (sin
    `didit_session_id`). 503 si Didit no está configurado o no responde.
    """
    require_admin(request)

    with get_db() as conn:
        row = conn.execute(
            "SELECT didit_session_id FROM clientes WHERE id=%s", (cliente_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "Cliente no encontrado")
    session_id = row_to_dict(row).get("didit_session_id")
    if not session_id:
        raise HTTPException(409, "El cliente todavía no inició una verificación con Didit")

    try:
        decision = retrieve_decision(session_id)
    except DiditNotConfiguredError:
        raise HTTPException(503, "Verificación de identidad no habilitada (DIDIT_API_KEY)")
    except httpx.HTTPStatusError as exc:
        logger.error(
            "didit: %s al re-chequear session_id=%s cliente_id=%s",
            exc.response.status_code, session_id, cliente_id,
        )
        raise HTTPException(503, "No se pudo conectar con el servicio de verificación")
    except Exception as exc:
        logger.error(
            "didit: error al re-chequear session_id=%s cliente_id=%s — %s",
            session_id, cliente_id, exc,
        )
        raise HTTPException(503, "No se pudo conectar con el servicio de verificación")

    status = (decision.get("status") or "").strip()
    status_key = status.lower().replace(" ", "_")
    logger.info("didit recheck: cliente_id=%s session_id=%s status=%s", cliente_id, session_id, status)

    aplicado: Optional[bool]
    if status_key == "approved":
        datos = extraer_datos_renaper(decision)
        contactos = extraer_contactos(decision)
        aplicado = kyc.aprobar(cliente_id=cliente_id, session_id=session_id, datos=datos, contactos=contactos)
    elif status_key == "declined":
        motivo = decision.get("decline_reason") or decision.get("comment") or None
        if motivo:
            motivo = str(motivo)[:500]
        aplicado = kyc.actualizar_estado(
            cliente_id=cliente_id, session_id=session_id, estado="rechazado", motivo=motivo
        )
    elif status_key in _ESTADOS_EN_REVISION:
        aplicado = kyc.actualizar_estado(cliente_id=cliente_id, session_id=session_id, estado="en_revision")
    else:
        # Expired / Abandoned / Not_Started / Kyc_Expired u otro estado no accionable.
        aplicado = None

    return {"status": status, "aplicado": aplicado, "session_id": session_id}


# ── Cliente: crear sesión propia ─────────────────────────────────────────────

@router.post("/cliente/verificacion/sesion", status_code=201)
def cliente_iniciar_verificacion(request: Request, body: Optional[SesionVerificacionIn] = None):
    """El cliente autenticado crea su propia sesión de verificación Didit.

    Guarda el didit_session_id para correlacionar el webhook con el cliente.
    Devuelve la URL a la que hay que redirigir al cliente para el flujo Didit.

    Acepta un `return_to` OPCIONAL (path interno del sitio) para que, al terminar
    el flujo, Didit devuelva al cliente a la pantalla desde la que arrancó (p. ej.
    retomar un pedido). El body es opcional — el portal puede postear SIN body.
    Si el `return_to` es inválido o ausente, se usa el fallback al portal; NUNCA
    se rechaza con 400 por un return_to malo (allowlist anti open-redirect).

    503 si DIDIT_API_KEY no está configurada.
    """
    session = require_cliente(request)
    cliente_id = session["cliente_id"]

    return_url = f"{settings.SITE_URL}{_RETURN_PATH}"
    rt = body.return_to if body else None
    if _es_path_interno_seguro(rt):
        return_url = f"{return_url}&return_to={quote(rt, safe='')}"
    try:
        sesion = create_session(
            return_url=return_url,
            vendor_data=str(cliente_id),
        )
    except DiditNotConfiguredError:
        raise HTTPException(503, "Verificación de identidad no habilitada")
    except httpx.HTTPStatusError as exc:
        logger.error("didit: %s al crear sesión cliente_id=%s", exc.response.status_code, cliente_id)
        raise HTTPException(503, "No se pudo conectar con el servicio de verificación")
    except Exception as exc:
        logger.error("didit: error al crear sesión cliente_id=%s — %s", cliente_id, exc)
        raise HTTPException(503, "No se pudo conectar con el servicio de verificación")

    with get_db() as conn:
        conn.execute(
            "UPDATE clientes SET didit_session_id=%s, updated_at=%s WHERE id=%s",
            (sesion.session_id, now_ar(), cliente_id),
        )
        conn.commit()

    # El cliente inició su propia verificación → consentimiento explícito del KYC (Ley 25.326).
    kyc.registrar_consentimiento(cliente_id)

    logger.info("didit: cliente %s inició verificación session_id=%s", cliente_id, sesion.session_id)
    return {"session_id": sesion.session_id, "url": sesion.url}


# ── Webhook público ──────────────────────────────────────────────────────────

@router.post("/webhooks/didit", status_code=200)
async def webhook_didit(request: Request):
    """Recibe eventos status.updated de Didit. Autenticado solo por HMAC.

    Flujo:
      1. Lee el body raw (antes de parsear JSON).
      2. Verifica firma HMAC-SHA256 (X-Signature sobre el body crudo, con
         X-Signature-V2 canónico como respaldo) + freshness (X-Timestamp).
      3. Si status == "Approved": extrae los datos de RENAPER de
         `decision.id_verifications[]` (API v3; respaldo: retrieve_decision) y
         actualiza clientes (dni, cuil, nombre completo, dirección, etc.).
      4. Siempre devuelve 200 (Didit reintenta en 4xx/5xx — idempotente).

    No loguea el body completo (puede contener datos RENAPER / Ley 25.326).
    """
    body = await request.body()
    signature = request.headers.get("X-Signature", "")
    signature_v2 = request.headers.get("X-Signature-V2", "")
    timestamp = request.headers.get("X-Timestamp", "")

    try:
        verify_webhook(body=body, signature=signature, timestamp=timestamp, signature_v2=signature_v2)
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

    # Solo procesamos estados conocidos que requieren acción.
    ESTADOS_ACCION = {"Approved", "Declined", "Processing", "In_review", "Under_review"}
    if status not in ESTADOS_ACCION:
        return {"ok": True}

    # vendor_data es el cliente_id que pasamos al crear la sesión.
    vendor_data = payload.get("vendor_data", "")
    try:
        cliente_id = int(vendor_data)
    except (ValueError, TypeError):
        logger.error("didit webhook: vendor_data inválido %r session_id=%s", vendor_data, session_id)
        return {"ok": True}  # Devolvemos 200 para que Didit no reintente.

    if status == "Approved":
        # Identidad (RENAPER) + contactos verificados (mail/teléfono). Normalmente el
        # webhook ya los trae embebidos; si llegara 'liviano' (sin `decision` o sin DNI),
        # pedimos la decisión canónica por API. No se loguea el body (Ley 25.326).
        decision = payload.get("decision")
        datos = extraer_datos_renaper(decision)
        if not datos.tiene_datos:
            try:
                # `retrieve_decision` hace un GET httpx SÍNCRONO (hasta el timeout):
                # en este handler async bloquearía el event loop. Lo mandamos al
                # threadpool para no congelar el servidor ante un webhook 'liviano'.
                decision = await run_in_threadpool(retrieve_decision, session_id)
                datos = extraer_datos_renaper(decision)
            except Exception as exc:
                logger.error("didit webhook: no se pudo recuperar la decisión session_id=%s — %s", session_id, exc)
        # La orquestación (escribir identidad + ancla CUIL + contactos + evento) vive en
        # identity/kyc — el route es solo transporte.
        contactos = extraer_contactos(decision)
        kyc.aprobar(cliente_id=cliente_id, session_id=session_id, datos=datos, contactos=contactos)

    elif status == "Declined":
        # Intentamos extraer un motivo legible del payload (no siempre presente).
        motivo: Optional[str] = None
        try:
            decision = payload.get("decision") or {}
            motivo = (
                decision.get("decline_reason")
                or decision.get("comment")
                or None
            )
            if motivo:
                motivo = str(motivo)[:500]  # cap defensivo
        except Exception:
            pass
        kyc.actualizar_estado(
            cliente_id=cliente_id, session_id=session_id, estado="rechazado", motivo=motivo
        )

    else:
        # Processing / In_review / Under_review → en revisión.
        kyc.actualizar_estado(
            cliente_id=cliente_id, session_id=session_id, estado="en_revision"
        )

    return {"ok": True}
