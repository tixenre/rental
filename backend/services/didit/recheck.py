"""recheck.py — re-consulta a Didit el estado ACTUAL de la verificación de un
cliente y lo aplica por la pluma única `identity.kyc`. Fuente única del recheck:
la usan el endpoint de admin, el self-service del cliente y el barrido
automático de sesiones abandonadas (`jobs/recheck_didit_pendientes.py`) — no
reimplementar esta búsqueda en ningún otro lugar.

Existe porque el webhook de Didit puede no llegar nunca (falla de origen), y
porque un cliente puede reintentar la verificación varias veces mientras una
sesión anterior sigue pendiente — cada reintento pisa `clientes.didit_session_id`,
así que la sesión que terminó decidiéndose puede ya no ser la "actual"; por eso
se revisa el historial completo (`kyc_events`) y no solo el puntero vigente.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from database import get_db, now_ar, row_to_dict
from services.didit.client import DiditNotConfiguredError, retrieve_decision
from services.didit.decision import extraer_contactos, extraer_datos_renaper

# Import perezoso de `identity.kyc` (no a nivel de módulo): `identity/__init__.py`
# importa `identity.contacts`, que importa `services.didit.decision` — como este
# módulo vive DENTRO de `services.didit` (su `__init__.py` lo exporta), un import
# top-level de `identity.kyc` acá cerraría un ciclo (`services.didit` →
# `identity.kyc` → `identity.contacts` → `services.didit.decision` → de nuevo
# `services.didit`, todavía a medio inicializar). Mismo patrón que
# `jobs/scheduler.py` para romper ciclos de import.

logger = logging.getLogger(__name__)

# Estados de sesión que Didit puede devolver (GET .../decision/, campo top-level
# `status`, distinto del `id_verifications[].status` por-feature). Normalizamos
# a minúsculas + espacio→guion-bajo antes de comparar (los valores del webhook
# vienen "In_review"/"Under_review"; la API directa documenta "In Review").
ESTADOS_EN_REVISION = {"in_review", "under_review", "processing", "in_progress"}

# Tope de sesiones históricas a re-consultar (barato: GETs puntuales, no
# hot-path — pero sin cap un cliente con decenas de reintentos podría disparar
# demasiados GETs a Didit de una sola llamada).
_MAX_SESIONES_HISTORIAL = 20


class ClienteSinVerificacionError(Exception):
    """El cliente no existe o no tiene ninguna sesión Didit conocida (ni la
    actual ni en el historial de `kyc_events`)."""


def _sesiones_conocidas(conn, cliente_id: int) -> list:
    rows = conn.execute(
        """SELECT session_id FROM kyc_events
           WHERE cliente_id=%s AND session_id IS NOT NULL
           GROUP BY session_id ORDER BY MAX(id) DESC LIMIT %s""",
        (cliente_id, _MAX_SESIONES_HISTORIAL),
    ).fetchall()
    return [row_to_dict(r)["session_id"] for r in rows]


def recheck_cliente(cliente_id: int, *, session_id_override: Optional[str] = None) -> dict:
    """Re-consulta a Didit y aplica el resultado. Devuelve {status, aplicado, session_id}.

    Si `session_id_override` viene vacío, revisa la sesión actual + todo el
    historial conocido (la aprobada, si existe en cualquier punto, gana). Si
    viene seteado, salta la búsqueda y re-chequea ESA sesión puntual (uso admin:
    una sesión copiada del dashboard de Didit que no dejó rastro en `kyc_events`).

    Raises:
        ClienteSinVerificacionError — cliente inexistente o sin sesión conocida.
        DiditNotConfiguredError — DIDIT_API_KEY no seteada.
        RuntimeError — Didit no respondió para ninguna sesión candidata.
    """
    from identity import kyc  # import perezoso — ver comentario de módulo

    with get_db() as conn:
        row = conn.execute(
            "SELECT didit_session_id FROM clientes WHERE id=%s", (cliente_id,)
        ).fetchone()
        if not row:
            raise ClienteSinVerificacionError(f"cliente {cliente_id} no encontrado")
        actual = row_to_dict(row).get("didit_session_id")
        historial = [] if session_id_override else _sesiones_conocidas(conn, cliente_id)

    if session_id_override:
        candidatos = [session_id_override]
    else:
        # La sesión actual primero (la más probable) + el resto del historial sin duplicar.
        candidatos = ([actual] if actual else []) + [s for s in historial if s != actual]
    if not candidatos:
        raise ClienteSinVerificacionError(f"cliente {cliente_id} nunca inició una verificación")

    mejor: Optional[tuple] = None  # (session_id, decision, status, status_key)
    for candidato in candidatos:
        try:
            decision = retrieve_decision(candidato)
        except DiditNotConfiguredError:
            raise
        except httpx.HTTPStatusError as exc:
            # Una sesión puntual del historial puede haber expirado/borrado en Didit
            # — no aborta la búsqueda, seguimos con las demás candidatas.
            logger.warning(
                "didit recheck: %s al re-chequear session_id=%s cliente_id=%s (historial)",
                exc.response.status_code, candidato, cliente_id,
            )
            continue
        except Exception as exc:
            logger.warning(
                "didit recheck: error al re-chequear session_id=%s cliente_id=%s (historial) — %s",
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
        raise RuntimeError(f"Didit no respondió para ninguna sesión de cliente_id={cliente_id}")

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
    elif status_key in ESTADOS_EN_REVISION:
        aplicado = kyc.actualizar_estado(cliente_id=cliente_id, session_id=session_id, estado="en_revision")
    else:
        # Expired / Abandoned / Not_Started / Kyc_Expired u otro estado no accionable.
        aplicado = None

    return {"status": status, "aplicado": aplicado, "session_id": session_id}
