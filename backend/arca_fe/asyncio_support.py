"""arca_fe.asyncio_support — facade async. PORTABLE (solo stdlib: `asyncio`).

Wrappers cooperativos vía `asyncio.to_thread` — delegan al cliente SYNC existente corriendo en un
thread del pool default de asyncio. **NO son un cliente async nativo** (no usan `httpx.AsyncClient`
ni una variante async de `zeep`/`requests`) — siguen siendo I/O bloqueante, solo dejan de bloquear
el event loop del consumidor mientras esperan. Cero lógica duplicada: toda la lógica real vive en
los módulos sync (`wsfe.py`, `padron.py`, `wsaa.py`), esto solo la corre en otro thread.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .modelos import CaeResult, ComprobanteRequest
    from .padron import PadronClient, PersonaArca
    from .wsfe import WsfeClient


async def solicitar_cae_async(
    client: "WsfeClient", comprobante: "ComprobanteRequest", numero: int
) -> "CaeResult":
    """Wrapper cooperativo de `WsfeClient.solicitar_cae` — corre la llamada SOAP bloqueante en un
    thread aparte, no bloquea el event loop del consumidor."""
    return await asyncio.to_thread(client.solicitar_cae, comprobante, numero)


async def get_persona_async(client: "PadronClient", cuit: str) -> "PersonaArca":
    """Wrapper cooperativo de `PadronClient.get_persona`."""
    return await asyncio.to_thread(client.get_persona, cuit)


async def login_async(
    tra_cms: bytes, endpoint: str, *, timeout: float = 30.0
) -> tuple[str, str, datetime]:
    """Wrapper cooperativo de `wsaa.login` — misma firma, mismo resultado
    `(token, sign, expira_at)`."""
    from .wsaa import login

    return await asyncio.to_thread(login, tra_cms, endpoint, timeout=timeout)
