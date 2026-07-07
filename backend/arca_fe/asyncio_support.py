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
    from .modelos_exportacion import ComprobanteExportacionRequest
    from .padron import PadronClient, PersonaArca
    from .wsfe import WsfeClient
    from .wsfex import WsfexClient


async def solicitar_cae_async(
    client: "WsfeClient", comprobante: "ComprobanteRequest", numero: int
) -> "CaeResult":
    """Wrapper cooperativo de `WsfeClient.solicitar_cae` — corre la llamada SOAP bloqueante en un
    thread aparte, no bloquea el event loop del consumidor."""
    return await asyncio.to_thread(client.solicitar_cae, comprobante, numero)


async def autorizar_async(
    client: "WsfexClient", comprobante: "ComprobanteExportacionRequest", numero: int
) -> "CaeResult":
    """Wrapper cooperativo de `WsfexClient.autorizar` (WSFEXv1, Factura de Exportación) — mismo
    criterio que `solicitar_cae_async` para WSFEv1: corre la llamada SOAP bloqueante en un thread
    aparte, no bloquea el event loop del consumidor."""
    return await asyncio.to_thread(client.autorizar, comprobante, numero)


async def get_persona_async(client: "PadronClient", cuit: str) -> "PersonaArca":
    """Wrapper cooperativo de `PadronClient.get_persona` — corre la llamada SOAP bloqueante en
    un thread aparte, no bloquea el event loop del consumidor.

    `client`: instancia ya construida de `PadronClient`.
    `cuit`: CUIT a consultar (con o sin guiones — mismo comportamiento que `get_persona`).

    Devuelve la `PersonaArca` resuelta; levanta lo mismo que `get_persona` (`ArcaBusinessError`/
    `ArcaResponseError`/`ArcaAuthError`/`ArcaNetworkError`)."""
    return await asyncio.to_thread(client.get_persona, cuit)


async def login_async(
    tra_cms: bytes, endpoint: str, *, timeout: float = 30.0
) -> tuple[str, str, datetime]:
    """Wrapper cooperativo de `wsaa.login` — misma firma, mismo resultado
    `(token, sign, expira_at)`."""
    from .wsaa import login

    return await asyncio.to_thread(login, tra_cms, endpoint, timeout=timeout)


async def login_con_cert_async(
    servicio: str,
    cert_pem: bytes,
    key_pem: bytes,
    endpoint: str,
    *,
    ahora: datetime | None = None,
    timeout: float = 30.0,
    key_password: bytes | None = None,
) -> tuple[str, str, datetime]:
    """Wrapper cooperativo de `wsaa.login_con_cert` — mismo atajo de alto nivel (construye el TRA,
    lo firma y autentica en una sola llamada) que `login_async` ya ofrece para `login`, pero para
    el caso más común (el consumidor solo tiene cert/key, no un TRA ya firmado a mano). Misma
    firma, mismo resultado `(token, sign, expira_at)`; levanta lo mismo que `login_con_cert`
    (`ArcaAuthError`/`ArcaNetworkError`/`ArcaResponseError`)."""
    from .wsaa import login_con_cert

    return await asyncio.to_thread(
        login_con_cert,
        servicio, cert_pem, key_pem, endpoint,
        ahora=ahora, timeout=timeout, key_password=key_password,
    )
