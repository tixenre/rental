"""Tests de seguridad de routes/cliente_portal.py::cliente_crear_pedido.

Regresión del issue #507: el endpoint POST /api/cliente/pedidos NO debe
confiar en el `precio_jornada` que manda el cliente; tiene que resolverlo
desde `equipos.precio_jornada`.
"""

import pytest
from fastapi import BackgroundTasks
from starlette.requests import Request

from routes.cliente_portal import (
    cliente_crear_pedido,
    CartItemIn,
    PedidoClienteCreate,
)


pytestmark = pytest.mark.unit


def _fake_request() -> Request:
    """Request real (no un stub crudo) — cliente_crear_pedido lleva
    `@limiter.limit` (barrido de seguimiento #1263/#1265): slowapi exige una
    instancia genuina de `starlette.requests.Request`. Sin conexión real —
    alcanza con el scope ASGI mínimo."""
    return Request(
        {"type": "http", "method": "POST", "path": "/api/cliente/pedidos", "headers": [], "client": ("127.0.0.1", 0)}
    )


class FakeRow(dict):
    """sqlite3.Row-like — subscriptable y .keys()."""
    def __getitem__(self, k):
        return super().__getitem__(k)


class FakeConn:
    """Conn fake que devuelve precios desde un mapa {equipo_id: precio}. El gate de
    visibilidad y el precio se resuelven en LOTE (`= ANY(%s)` + `fetchall`,
    `services/carrito/readiness.py::_equipos_visibles_catalogo`/
    `services/precios.py::precios_efectivos_batch` — batch para evitar N+1, ver
    `docs/SISTEMA_FINANZAS_FLUJO.md` hallazgo #12), así que este double simula esas
    dos queries en lote en vez de una por equipo_id."""
    def __init__(self, precios_catalogo: dict[int, int]):
        self._precios = precios_catalogo
        self._pending_query: str = ""
        self._pending_params: tuple = ()

    def execute(self, sql, params=()):
        self._pending_query = sql
        self._pending_params = params
        return self

    def fetchone(self):
        sql = self._pending_query
        # Verificación de existencia del cliente (SELECT id FROM clientes).
        if "FROM clientes" in sql and "WHERE id" in sql:
            return FakeRow(id=42)
        return None

    def fetchall(self):
        sql = self._pending_query
        ids = self._pending_params[0] if self._pending_params else []
        if "id = ANY(%s)" not in sql:
            return []
        vivos = [i for i in ids if i in self._precios]
        if "SELECT id, precio_jornada, tipo" in sql:
            # `tipo` lo lee `precios_efectivos_batch` (resuelve combo vs. precio
            # propio). Equipo simple → toma su `precio_jornada` tal cual.
            return [FakeRow(id=i, precio_jornada=self._precios[i], tipo="simple") for i in vivos]
        # Gate de visibilidad en lote (`SELECT id FROM equipos WHERE id = ANY(%s) ...`).
        return [FakeRow(id=i) for i in vivos]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def close(self):
        pass


def test_cliente_no_decide_precio_jornada(monkeypatch):
    """Caso atacante: el body manda precio_jornada=1 pero el server
    debe usar el del catálogo (50000) al construir el PedidoCreate."""

    # 1. Sesión cliente válida y verificada (saltea require_cliente_verificado,
    #    que el handler usa como gate: existencia + identidad). Este test aísla la
    #    lógica de precio, no el gate.
    monkeypatch.setattr(
        "routes.cliente_portal.pedidos.require_cliente_verificado",
        lambda req: {"cliente_id": 42, "email": "cliente@test.com"},
    )

    # 2. Saltea la validación de horarios habilitados.
    monkeypatch.setattr(
        "routes.alquileres._validar_horarios_habilitados",
        lambda conn, desde, hasta: None,
    )

    # 3. Conn fake con precio de catálogo conocido.
    precios_catalogo = {7: 50000}
    monkeypatch.setattr(
        "routes.cliente_portal.pedidos.get_db",
        lambda: FakeConn(precios_catalogo),
    )

    # 4. Interceptar `create_pedido_retry` —la puerta ÚNICA de creación que usa
    #    el endpoint (envuelve a `create_pedido` con reintento de deadlock)— sin
    #    ejecutarla de verdad, para capturar el payload que recibió.
    captured = {}

    def fake_create_pedido_retry(payload, background=None):
        captured["payload"] = payload
        return {"id": 1, "ok": True}

    monkeypatch.setattr(
        "routes.alquileres.create_pedido_retry",
        fake_create_pedido_retry,
    )

    # 5. Llamar al endpoint con un body que intenta colar precio_jornada=1.
    body = PedidoClienteCreate(
        fecha_desde="2030-01-01T10:00",
        fecha_hasta="2030-01-02T10:00",
        items=[CartItemIn(equipo_id=7, cantidad=3, precio_jornada=1)],
    )
    cliente_crear_pedido(body, _fake_request(), BackgroundTasks())

    # 6. El payload final debe tener el precio del CATÁLOGO, no el del body.
    payload = captured["payload"]
    assert len(payload.items) == 1
    item = payload.items[0]
    assert item.equipo_id == 7
    assert item.cantidad == 3
    assert item.precio_jornada == 50000, (
        f"El server respetó el precio_jornada del cliente ({item.precio_jornada}) "
        f"en vez de leerlo del catálogo (50000). #507 NO está cerrado."
    )


def test_equipo_inexistente_devuelve_404(monkeypatch):
    """Si el cliente manda un equipo_id que no existe, el endpoint debe
    devolver 404 (no crear pedido fantasma con precio=0)."""
    from fastapi import HTTPException

    monkeypatch.setattr(
        "routes.cliente_portal.pedidos.require_cliente_verificado",
        lambda req: {"cliente_id": 42, "email": "cliente@test.com"},
    )
    monkeypatch.setattr(
        "routes.alquileres._validar_horarios_habilitados",
        lambda conn, desde, hasta: None,
    )
    monkeypatch.setattr(
        "routes.cliente_portal.pedidos.get_db",
        lambda: FakeConn({}),  # catálogo vacío
    )

    body = PedidoClienteCreate(
        fecha_desde="2030-01-01T10:00",
        fecha_hasta="2030-01-02T10:00",
        items=[CartItemIn(equipo_id=999, cantidad=1, precio_jornada=1000)],
    )
    with pytest.raises(HTTPException) as exc:
        cliente_crear_pedido(body, _fake_request(), BackgroundTasks())
    assert exc.value.status_code == 404
    assert "999" in exc.value.detail
