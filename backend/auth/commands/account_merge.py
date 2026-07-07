"""Escritura de merge de cuentas — única puerta de mutación.

Move-verbatim desde `auth/account_merge.py` (reorg CQRS-lite, espeja
`contabilidad/`/`identities/`): mismo SQL, mismo comportamiento. Ver
`auth/queries/account_merge.py` para la lectura (`account_is_absorbable`).

Caso de uso (Fase 1B, #1098): el usuario está logueado en la cuenta A y vincula una
llave (Google) que resulta ser de la cuenta B. Como probó control de A (la sesión) **Y**
de B (el OAuth de Google), sabemos que A y B son la misma persona → se unen. Para que el
merge sea SEGURO se exige que una de las dos sea **absorbible** (ver `account_is_absorbable`):
liviana (nació por el alta passwordless), sin verificar y sin pedidos → no tiene datos que
perder; se mueven sus llaves a la otra y se borra.

El merge GENERAL de dos cuentas CON datos (reasignar pedidos/contabilidad, dedup por CUIL
verificado) es más delicado y vive en la Fase 2 (`identity/merge`) — acá NO se hace. Todas
las FKs a `clientes` son CASCADE o SET NULL (ninguna RESTRICT), así que borrar una cuenta
absorbible nunca falla por una referencia colgada.
"""
import logging

from database import get_db

logger = logging.getLogger(__name__)


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
            # identidades: una cuenta = una por método (un Google, un mail) → mover la del
            # source solo si el target NO tiene ya una de ese método; la que sobra se va con
            # el DELETE del source (cascade). Mantiene el invariante "un Google por cuenta".
            conn.execute(
                """UPDATE login_identities li SET cliente_id = %s
                   WHERE li.cliente_id = %s
                     AND NOT EXISTS (
                       SELECT 1 FROM login_identities t
                       WHERE t.method = li.method AND t.cliente_id = %s)""",
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
