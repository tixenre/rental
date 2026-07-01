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
        # Registramos la creación YA — no esperamos al webhook (puede no llegar
        # nunca, es la falla de origen que motiva el recheck). Sin esto, una
        # sesión sin ningún webhook procesado queda invisible para
        # `_sesiones_conocidas` aunque el cliente la haya usado y Didit la
        # haya decidido.
        kyc.registrar_evento(conn, cliente_id, "iniciado", session_id=sesion.session_id)
        conn.commit()

    logger.info("didit: sesión creada session_id=%s cliente_id=%s", sesion.session_id, cliente_id)
    return {"session_id": sesion.session_id, "url": sesion.url}


# ── Admin: re-chequear el estado actual en Didit ─────────────────────────────

# Estados de sesión que Didit puede devolver (GET .../decision/, campo top-level
# `status`, distinto del `id_verifications[].status` por-feature). Normalizamos
# a minúsculas + espacio→guion-bajo antes de comparar (los valores del webhook
# vienen "In_review"/"Under_review"; la API directa documenta "In Review").
_ESTADOS_EN_REVISION = {"in_review", "under_review", "processing", "in_progress"}

# Tope de sesiones históricas a re-consultar (barato: GETs de un admin action
# puntual, no hot-path — pero sin cap un cliente con decenas de reintentos
# podría disparar demasiados GETs a Didit de un solo click).
_MAX_SESIONES_HISTORIAL = 20


def _sesiones_conocidas(conn, cliente_id: int) -> list:
    """`session_id` de Didit con al menos un evento propio para este cliente
    (`kyc_events`, ya scopeado a `cliente_id`), del más reciente al más viejo.

    Un cliente puede reintentar la verificación varias veces mientras un admin
    revisa a mano una sesión anterior en el dashboard de Didit — cada reintento
    pisa `clientes.didit_session_id` con la sesión nueva (siempre la más
    reciente), así que la sesión que el admin terminó aprobando puede ya no ser
    la "actual". Este historial es lo que le permite al recheck encontrarla."""
    rows = conn.execute(
        """SELECT session_id FROM kyc_events
           WHERE cliente_id=%s AND session_id IS NOT NULL
           GROUP BY session_id ORDER BY MAX(id) DESC LIMIT %s""",
        (cliente_id, _MAX_SESIONES_HISTORIAL),
    ).fetchall()
    return [row_to_dict(r)["session_id"] for r in rows]


class RecheckVerificacionIn(BaseModel):
    """`session_id` opcional: override manual para saltar la búsqueda por
    historial y re-chequear una sesión puntual (p. ej. una copiada del
    dashboard de Didit que no dejó ningún rastro en `kyc_events` — sesiones
    creadas antes del fix que empezó a registrar cada `iniciado`)."""
    session_id: Optional[str] = None


@router.post("/admin/verificacion/recheck/{cliente_id}")
def recheck_verificacion(cliente_id: int, request: Request, body: Optional[RecheckVerificacionIn] = None):
    """Re-consulta a Didit el estado ACTUAL de la sesión del cliente y aplica el
    resultado (aprobar / rechazar / en revisión) por la pluma única `identity.kyc`
    — sin que el admin tenga que validar la identidad a mano.

    Caso de uso: Didit rechazó automáticamente por una razón menor (ej. foto
    oscura), el admin revisó el caso a mano *en el dashboard de Didit* y lo
    aprobó ahí — pero el webhook de esa revisión manual no siempre llega (o ya
    llegó y se perdió). Este endpoint refleja en Rambla lo que Didit devuelve
    HOY, en vez de que el admin tenga que marcarlo aprobado él mismo.

    Revisa TODO el historial conocido de sesiones del cliente (`_sesiones_conocidas`),
    no solo la que `clientes.didit_session_id` sigue rastreando: si el cliente
    reintentó la verificación mientras el admin la revisaba, la sesión actual ya
    no es la aprobada — la búsqueda encuentra la que sí lo está en cualquier
    punto del historial y **mueve el puntero** (`didit_session_id`) hacia ella
    antes de aplicarla (así `identity.kyc.aprobar` sigue validando `_session_coincide`
    contra el mismo campo, sin relajar esa defensa).

    Si el body trae `session_id`, se salta la búsqueda y re-chequea ESA sesión
    puntual directamente — para el caso límite de una sesión que ni siquiera
    dejó un evento "iniciado" (creada antes de ese fix, o creada fuera de
    nuestro flujo) y por eso el historial no la puede encontrar sola.

    404 si el cliente no existe. 409 si nunca inició una verificación (sin
    ninguna sesión conocida y sin override). 503 si Didit no está configurado
    o no responde.
    """
    require_admin(request)
    override = (body.session_id or "").strip() if body and body.session_id else None

    with get_db() as conn:
        row = conn.execute(
            "SELECT didit_session_id FROM clientes WHERE id=%s", (cliente_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Cliente no encontrado")
        actual = row_to_dict(row).get("didit_session_id")
        historial = [] if override else _sesiones_conocidas(conn, cliente_id)

    if override:
        candidatos = [override]
    else:
        # La sesión actual primero (la más probable) + el resto del historial sin duplicar.
        candidatos = ([actual] if actual else []) + [s for s in historial if s != actual]
    if not candidatos:
        raise HTTPException(409, "El cliente todavía no inició una verificación con Didit")

    mejor: Optional[tuple] = None  # (session_id, decision, status, status_key)
    for candidato in candidatos:
        try:
            decision = retrieve_decision(candidato)
        except DiditNotConfiguredError:
            raise HTTPException(503, "Verificación de identidad no habilitada (DIDIT_API_KEY)")
        except httpx.HTTPStatusError as exc:
            # Una sesión puntual del historial puede haber expirado/borrado en Didit
            # — no aborta la búsqueda, seguimos con las demás candidatas.
            logger.warning(
                "didit: %s al re-chequear session_id=%s cliente_id=%s (historial)",
                exc.response.status_code, candidato, cliente_id,
            )
            continue
        except Exception as exc:
            logger.warning(
                "didit: error al re-chequear session_id=%s cliente_id=%s (historial) — %s",
                candidato, cliente_id, exc,
            )
            continue

        status = (decision.get("status") or "").strip()
        status_key = status.lower().replace(" ", "_")
        if status_key == "approved":
            mejor = (candidato, decision, status, status_key)
            break  # encontramos la aprobada — no hace falta seguir revisando el historial
        if mejor is None:
            mejor = (candidato, decision, status, status_key)  # primera respuesta válida, de fallback

    if mejor is None:
        raise HTTPException(503, "No se pudo conectar con el servicio de verificación")
    session_id, decision, status, status_key = mejor
    logger.info("didit recheck: cliente_id=%s session_id=%s status=%s", cliente_id, session_id, status)

    aplicado: Optional[bool]
    if status_key == "approved":
        if session_id != actual:
            # Encontramos la aprobación en una sesión distinta a la que veníamos
            # rastreando (el cliente reintentó de nuevo mientras se revisaba) —
            # movemos el puntero para que _session_coincide la reconozca.
            with get_db() as conn:
                conn.execute(
                    "UPDATE clientes SET didit_session_id=%s, updated_at=%s WHERE id=%s",
                    (session_id, now_ar(), cliente_id),
                )
                conn.commit()
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
        # Ídem admin: registrar la creación ya, sin depender de que el webhook llegue.
        kyc.registrar_evento(conn, cliente_id, "iniciado", session_id=sesion.session_id)
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
