"""net_utils.py — Resolución de la IP real del cliente detrás de proxies.

Detrás de Railway (y opcionalmente Cloudflare) `request.client.host` es la IP
del proxy, no la del cliente. Y `X-Forwarded-For` es spoofeable: el cliente
puede mandar entradas falsas que quedan a la IZQUIERDA. Las entradas confiables
son las que AGREGAN los proxies de confianza, que quedan a la DERECHA.

Con N proxies de confianza, la IP real del cliente es la N-ésima desde la
derecha (`ips[-N]`). `TRUSTED_PROXY_HOPS` configura N (default 1 = solo Railway;
si se agrega Cloudflare adelante, subir a 2).
"""

import os

from fastapi import Request

_TRUSTED_PROXY_HOPS = max(1, int(os.getenv("TRUSTED_PROXY_HOPS", "1")))


def get_client_ip(request: Request) -> str:
    """Devuelve la IP real del cliente, resistente a spoofing de X-Forwarded-For."""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        ips = [p.strip() for p in fwd.split(",") if p.strip()]
        if ips:
            idx = len(ips) - _TRUSTED_PROXY_HOPS
            return ips[idx if idx >= 0 else 0]
    client = request.client
    return client.host if client else "unknown"
