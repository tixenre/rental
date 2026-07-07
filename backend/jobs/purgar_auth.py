"""Barrido diario de housekeeping de `backend/auth/`: filas muertas que se
acumulan sin límite si nadie las borra.

`auth_sessions` (sesiones vencidas — `sessions.purge_expired`) y `auth_challenges`
(magic-links ya usados o vencidos — `magic.purge_expired`) son inertes desde el
punto de vista funcional (`is_active`/`peek`/`consumir` ya filtran por
expires_at/revoked_at/used_at), pero sin este barrido crecen para siempre — un
row por sesión y por invitación/recuperación creada. Mismo patrón que
`jobs/cleanup_livianas.py` (idempotente, 1×/día, logea solo si borró algo).
"""
import logging

from auth.commands import sessions as sessions_commands
from auth.commands import magic as magic_commands

logger = logging.getLogger(__name__)


def purgar_sesiones_y_challenges_expirados() -> tuple[int, int]:
    """Corre los dos barridos y devuelve (sesiones_borradas, challenges_borrados).
    El try/except de que ninguno tumbe el scheduler vive en el CALLER
    (`jobs/scheduler.py`, mismo contrato que los otros jobs)."""
    n_sesiones = sessions_commands.purge_expired()
    n_challenges = magic_commands.purge_expired()
    if n_sesiones:
        logger.info("housekeeping auth: %s sesión(es) vencida(s) borrada(s)", n_sesiones)
    if n_challenges:
        logger.info("housekeeping auth: %s magic-link(s) muerto(s) borrado(s)", n_challenges)
    return n_sesiones, n_challenges
