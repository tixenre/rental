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
