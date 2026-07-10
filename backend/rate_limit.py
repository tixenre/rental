"""rate_limit.py — Instancia compartida del limiter (slowapi).

Vive en su propio módulo para que tanto `main.py` (que lo registra en la app)
como los routers (que usan `@limiter.limit(...)` en handlers sensibles) lo
importen sin ciclos.

In-memory: sirve para 1 instancia de Railway. Si se escala a multi-instancia
o se agrega Redis, pasar `storage_uri="redis://..."`.
"""

from slowapi import Limiter

from net_utils import get_client_ip

# key_func = IP real del cliente (no spoofeable por X-Forwarded-For, ver net_utils).
limiter = Limiter(
    key_func=get_client_ip,
    default_limits=["200/minute"],
    # headers_enabled=False a propósito: con True, slowapi corre _inject_headers
    # después de cada endpoint @limiter.limit y EXIGE que el handler devuelva un
    # starlette Response. Los handlers que devuelven un dict (ej. /cotizar) lo
    # rompen → 500 → el front cae a $0. Las versiones nuevas de slowapi
    # endurecieron esto (antes ignoraban el dict). El rate-limit sigue activo;
    # solo se omiten los headers informativos X-RateLimit-*.
    headers_enabled=False,
)

# Límites para escrituras ADMIN (auditoría 2026-07-02, #1184): el patrón
# @limiter.limit ya se usaba en endpoints públicos (cotizar, talleres,
# búsqueda) pero no en contabilidad/pagos — una sesión admin comprometida o
# un bug de front en loop podía golpear la DB/R2 sin ningún freno server-side.
# Más holgado que los límites públicos (es tráfico humano autenticado, no
# anónimo) pero no infinito.
ADMIN_WRITE_LIMIT = "60/minute"
ADMIN_UPLOAD_LIMIT = "20/minute"  # mismo valor que routes/talleres.py para uploads

# Límite para escrituras de CLIENTE autenticado (portal /api/cliente/*, no-admin):
# mismo criterio y valor que ADMIN_WRITE_LIMIT (tráfico humano autenticado, no
# anónimo) pero constante propia — el actor es cualquier cliente logueado, no la
# allowlist de admin. Los endpoints de cliente ya caros/sensibles (registro/claim/
# verificar-cuit/perfiles fiscales — hit a AFIP) mantienen sus límites bespoke más
# ajustados (5-10/minute) en cliente_portal/cuenta.py; esta constante cubre el
# resto (favoritos, listas, pedidos, solicitudes de modificación, reserva del
# Estudio) — barrido de seguimiento de la auditoría #1263/#1265, que solo cubrió
# routes/equipos/* y routes/specs/*.
CLIENTE_WRITE_LIMIT = "60/minute"
