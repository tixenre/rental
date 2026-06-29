"""auth/account_merge.py — unir dos cuentas de cliente cuando son la MISMA persona.

Caso de uso (Fase 1B, #1098): el usuario está logueado en la cuenta A y vincula una
llave (Google) que resulta ser de la cuenta B. Como probó control de A (la sesión) **Y**
de B (el OAuth de Google), sabemos que A y B son la misma persona → se unen. Para que el
merge sea SEGURO se exige que una de las dos sea **absorbible**: liviana (nació por el alta
passwordless), sin verificar y sin pedidos → no tiene datos que perder; se mueven sus
llaves a la otra y se borra.

El merge GENERAL de dos cuentas CON datos (reasignar pedidos/contabilidad, dedup por CUIL
verificado) es más delicado y vive en la Fase 2 (`identity/merge`) — acá NO se hace. Todas
las FKs a `clientes` son CASCADE o SET NULL (ninguna RESTRICT), así que borrar una cuenta
absorbible nunca falla por una referencia colgada.
"""
import logging

from database import get_db

logger = logging.getLogger(__name__)


def account_is_absorbable(cliente_id: int) -> bool:
    """True si la cuenta es segura de absorber + borrar: **liviana, sin verificar y sin
    pedidos**. Una cuenta así nunca hizo nada → mover sus llaves y borrarla no pierde datos."""
    with get_db() as conn:
        r = conn.execute(
            "SELECT cuenta_estado, dni_validado_at FROM clientes WHERE id = %s", (cliente_id,)
        ).fetchone()
        if not r or r["cuenta_estado"] != "liviana" or r["dni_validado_at"] is not None:
            return False
        tiene_pedidos = conn.execute(
            "SELECT 1 FROM alquileres WHERE cliente_id = %s LIMIT 1", (cliente_id,)
        ).fetchone()
    return tiene_pedidos is None


def merge_accounts(*, source: int, target: int) -> None:
    """Une `source` en `target`: mueve sus llaves (passkeys + identidades de login) **y sus
    listas guardadas** a `target`, y borra `source`. **Solo** para `source` absorbible (sin
    pedidos) — no reasigna pedidos/plata (no los tiene). El resto de FKs son CASCADE/SET NULL
    → el DELETE es seguro. Transaccional (todo o nada)."""
    if source == target:
        return
    with get_db() as conn:
        with conn.transaction():
            # passkeys: credential_id es UNIQUE global → se mueven sin conflicto.
            conn.execute(
                "UPDATE passkey_credentials SET cliente_id = %s WHERE cliente_id = %s",
                (target, source),
            )
            # identidades: UNIQUE(method, identifier) → mover solo las que el target NO tenga;
            # las que chocan (target ya las tiene) se van con el DELETE del source (cascade).
            conn.execute(
                """UPDATE login_identities li SET cliente_id = %s
                   WHERE li.cliente_id = %s
                     AND NOT EXISTS (
                       SELECT 1 FROM login_identities t
                       WHERE t.method = li.method AND t.identifier = li.identifier
                         AND t.cliente_id = %s)""",
                (target, source, target),
            )
            # listas guardadas: contenido persistente del usuario → se mueven (no se pierden).
            # No hay UNIQUE por cliente → sin conflicto; los items siguen por `lista_id`.
            # (Los carritos son efímeros + client-side → su FK es SET NULL, no se mueven.)
            conn.execute(
                "UPDATE cliente_listas SET cliente_id = %s WHERE cliente_id = %s",
                (target, source),
            )
            conn.execute("DELETE FROM clientes WHERE id = %s", (source,))
    logger.info("merge de cuentas: source=%s absorbida en target=%s", source, target)
