"""Barrido de cuentas livianas abandonadas (3ª pata anti-spam del alta passwordless).

Una cuenta **liviana** (alta con passkey, nace sin datos) que pasado un plazo nunca
verificó identidad, nunca linkeó un contacto y nunca pidió nada es basura: se borra.
El `ON DELETE CASCADE` de `passkey_credentials` / `auth_sessions` / `login_identities`
limpia lo asociado. Junto con el rate-limit por-IP y la inertidad-hasta-Didit, cierra
la higiene anti-spam del alta passwordless (decisión del dueño, #1098 Fase 4).

**Predicado conservador** — solo borra lo inequívocamente abandonado (passkeys
sincronizan: si se borra una cuenta vacía, el usuario la recrea sin perder nada):
  - `cuenta_estado = 'liviana'`  → nació por el alta passwordless (no toca 'completa').
  - `dni_validado_at IS NULL`    → nunca verificó con Didit (inerte, nunca pudo pedir).
  - `email IS NULL`              → nunca linkeó Google/mail (sin contacto = sin uso real).
  - `created_at < now - N días`  → tuvo tiempo de sobra.
  - sin pedidos (`NOT EXISTS` en `alquileres`) → además evita orfanar pedidos
    (la FK es `ON DELETE SET NULL`, no cascade).
"""
import logging

from database import get_db

logger = logging.getLogger(__name__)

# Ventana de gracia: una liviana que en 30 días no verificó, no linkeó contacto y no
# pidió nada es abandono. Generoso a propósito (no borrar una cuenta recién creada).
DIAS_GRACIA = 30


def purgar_cuentas_livianas_stale(dias_gracia: int = DIAS_GRACIA) -> int:
    """Borra las cuentas livianas abandonadas. Devuelve cuántas borró (idempotente:
    re-correrlo sin candidatos borra 0). Usa el reloj de la DB (`NOW()`) para que la
    comparación con `created_at` (DEFAULT CURRENT_TIMESTAMP) sea internamente coherente."""
    with get_db() as conn:
        with conn.transaction():
            rows = conn.execute(
                """DELETE FROM clientes c
                   WHERE c.cuenta_estado = 'liviana'
                     AND c.dni_validado_at IS NULL
                     AND c.email IS NULL
                     AND c.created_at < NOW() - make_interval(days => %s)
                     AND NOT EXISTS (SELECT 1 FROM alquileres a WHERE a.cliente_id = c.id)
                   RETURNING c.id""",
                (dias_gracia,),
            ).fetchall()
    n = len(rows)
    if n:
        logger.info("cleanup de cuentas livianas: borradas %s (abandono > %sd)", n, dias_gracia)
    return n
