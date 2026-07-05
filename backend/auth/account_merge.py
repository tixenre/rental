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
    pedidos**. Una cuenta así nunca hizo nada → mover sus llaves y borrarla no pierde datos.

    #1240: una cuenta liviana SÍ puede crear un perfil fiscal (`POST /api/cliente/
    facturacion/perfiles` no exige `dni_validado_at`) antes de verificarse — si tuviera uno,
    ya no es "sin datos que perder" (`merge_accounts` acá no reasigna, solo mueve llaves),
    así que se suma al chequeo. Mismo motivo para `productora_miembros`: un admin puede
    vincular una cuenta liviana a una productora (`agregar_miembro` tampoco exige
    verificación) — sin este chequeo, absorber esa cuenta borraba el vínculo en silencio
    (`ON DELETE CASCADE`, `merge_accounts` no lo reasigna)."""
    with get_db() as conn:
        r = conn.execute(
            "SELECT cuenta_estado, dni_validado_at FROM clientes WHERE id = %s", (cliente_id,)
        ).fetchone()
        if not r or r["cuenta_estado"] != "liviana" or r["dni_validado_at"] is not None:
            return False
        tiene_pedidos = conn.execute(
            "SELECT 1 FROM alquileres WHERE cliente_id = %s LIMIT 1", (cliente_id,)
        ).fetchone()
        if tiene_pedidos is not None:
            return False
        tiene_perfil_fiscal = conn.execute(
            "SELECT 1 FROM cliente_perfiles_fiscales WHERE cliente_id = %s LIMIT 1",
            (cliente_id,),
        ).fetchone()
        if tiene_perfil_fiscal is not None:
            return False
        tiene_productora = conn.execute(
            "SELECT 1 FROM productora_miembros WHERE cliente_id = %s LIMIT 1",
            (cliente_id,),
        ).fetchone()
    return tiene_productora is None


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
