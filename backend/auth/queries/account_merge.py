"""Lectura del guardrail de merge de cuentas — nunca muta.

Move-verbatim desde `auth/account_merge.py` (reorg CQRS-lite, espeja
`contabilidad/`/`identities/`): mismo SQL, mismo comportamiento. Ver
`auth/commands/account_merge.py` para la escritura (`merge_accounts`).
"""
from database import get_db


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
