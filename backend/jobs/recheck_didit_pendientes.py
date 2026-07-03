"""Barrido de verificaciones Didit abandonadas (el cliente no volvió a la web).

El gate en `routes/didit.py::cliente_iniciar_verificacion` y el self-recheck que
dispara el front al volver (`?verificacion=pendiente`) cubren al cliente que SÍ
vuelve a interactuar con el sitio. Pero si abandona del todo (cierra la pestaña
y no vuelve) nadie del lado cliente vuelve a preguntarle a Didit por él — y si
además el webhook se perdió, ese cliente queda `en_revision`/`no_verificado`
para siempre hasta que un admin lo note a mano.

Este barrido corre server-side, sin depender de que el cliente vuelva: re-chequea
contra Didit (mismo motor único `services.didit.recheck_cliente`) a los clientes
con una sesión Didit vigente que sigue sin resolverse hace más de `_GRACIA_MIN`
minutos. Barato (histéresis de N minutos evita re-consultar la misma sesión en
cada ciclo del scheduler) y acotado (`_MAX_POR_CORRIDA`, no hot-path)."""

import logging

from database import get_db, row_to_dict
from services.didit import ClienteSinVerificacionError, DiditNotConfiguredError, recheck_cliente

logger = logging.getLogger(__name__)

# Gracia antes de re-chequear: darle tiempo a que el webhook llegue solo (suele
# tardar segundos, no minutos) y a que el propio cliente vuelva y dispare el
# self-recheck del front antes de gastar un GET a Didit por él.
_GRACIA_MINUTOS = 30

# Tope por corrida: barrido periódico, no hay apuro en resolver los 500 casos
# de una — evita ráfagas grandes de GETs a Didit si se acumulara backlog.
_MAX_POR_CORRIDA = 50


def recheck_verificaciones_pendientes(gracia_minutos: int = _GRACIA_MINUTOS, max_por_corrida: int = _MAX_POR_CORRIDA) -> int:
    """Re-chequea contra Didit a los clientes con sesión pendiente hace rato.
    Devuelve cuántos re-chequeó (aplicado o no). Idempotente: re-correrlo sobre
    un cliente ya resuelto no hace nada (Didit ya no lo devuelve como pendiente,
    y el resultado se re-aplica sin duplicar vía `identity.kyc._ya_registrado`)."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id FROM clientes
               WHERE didit_session_id IS NOT NULL
                 AND dni_verificacion_estado IN ('no_verificado', 'en_revision')
                 AND updated_at < NOW() - make_interval(mins => %s)
               ORDER BY updated_at ASC
               LIMIT %s""",
            (gracia_minutos, max_por_corrida),
        ).fetchall()
    cliente_ids = [row_to_dict(r)["id"] for r in rows]
    if not cliente_ids:
        return 0

    resueltos = 0
    for cliente_id in cliente_ids:
        try:
            recheck_cliente(cliente_id)
            resueltos += 1
        except ClienteSinVerificacionError:
            continue
        except DiditNotConfiguredError:
            # Feature apagada — no tiene sentido seguir intentando el resto.
            logger.info("recheck de pendientes Didit: DIDIT_API_KEY no configurada, corte de corrida")
            break
        except Exception as exc:
            logger.warning("recheck de pendientes Didit: falló cliente_id=%s — %s", cliente_id, exc)

    if resueltos:
        logger.info("recheck de pendientes Didit: %s/%s clientes re-chequeados", resueltos, len(cliente_ids))
    return resueltos
