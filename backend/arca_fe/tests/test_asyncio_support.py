"""Tests de arca_fe.asyncio_support — wrappers cooperativos vía asyncio.to_thread.

Confirma que delegan al cliente sync (fakes, sin red) y devuelven lo mismo que la
llamada sync — no duplican lógica, solo corren en un thread."""
from __future__ import annotations

import pytest

from arca_fe.asyncio_support import (
    get_persona_async,
    login_async,
    login_con_cert_async,
    solicitar_cae_async,
)

pytestmark = pytest.mark.unit


class _FakeWsfeClient:
    def solicitar_cae(self, comprobante, numero):
        return ("cae-resultado", comprobante, numero)


class _FakePadronClient:
    def get_persona(self, cuit):
        return ("persona-resultado", cuit)


@pytest.mark.asyncio
async def test_solicitar_cae_async_delega_al_cliente_sync():
    client = _FakeWsfeClient()
    resultado = await solicitar_cae_async(client, "comprobante-fake", 7)
    assert resultado == ("cae-resultado", "comprobante-fake", 7)


@pytest.mark.asyncio
async def test_get_persona_async_delega_al_cliente_sync():
    client = _FakePadronClient()
    resultado = await get_persona_async(client, "20301234563")
    assert resultado == ("persona-resultado", "20301234563")


@pytest.mark.asyncio
async def test_login_async_delega_a_wsaa_login(monkeypatch):
    llamadas = []

    def _fake_login(tra_cms, endpoint, *, timeout=30.0):
        llamadas.append((tra_cms, endpoint, timeout))
        return ("tok", "sign", "expira")

    monkeypatch.setattr("arca_fe.wsaa.login", _fake_login)

    resultado = await login_async(b"cms", "https://endpoint.fake", timeout=45.0)

    assert resultado == ("tok", "sign", "expira")
    assert llamadas == [(b"cms", "https://endpoint.fake", 45.0)]


@pytest.mark.asyncio
async def test_login_con_cert_async_delega_a_wsaa_login_con_cert(monkeypatch):
    """El atajo de alto nivel (construir_tra+firmar_tra+login en una llamada) tiene que tener
    equivalente async, igual que login_async lo tiene para login — antes faltaba, rompiendo la
    simetría de cobertura del facade."""
    llamadas = []

    def _fake_login_con_cert(servicio, cert_pem, key_pem, endpoint, *, ahora=None, timeout=30.0, key_password=None):
        llamadas.append((servicio, cert_pem, key_pem, endpoint, ahora, timeout, key_password))
        return ("tok", "sign", "expira")

    monkeypatch.setattr("arca_fe.wsaa.login_con_cert", _fake_login_con_cert)

    resultado = await login_con_cert_async(
        "wsfe", b"cert", b"key", "https://endpoint.fake", timeout=45.0
    )

    assert resultado == ("tok", "sign", "expira")
    assert llamadas == [("wsfe", b"cert", b"key", "https://endpoint.fake", None, 45.0, None)]
