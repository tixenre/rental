"""Tests de seguridad de routes/cliente_portal.py::cliente_crear_pedido.

Regresión del issue #507: el endpoint POST /api/cliente/pedidos NO debe
confiar en el `precio_jornada` que manda el cliente; tiene que resolverlo
desde `equipos.precio_jornada`.
"""

import pytest
from fastapi import BackgroundTasks

from routes.cliente_portal import (
    cliente_crear_pedido,
    CartItemIn,
    PedidoClienteCreate,
)


pytestmark = pytest.mark.unit


class FakeRequest:
    def __init__(self, cookies=None):
        self.cookies = cookies or {}


class FakeRow(dict):
    """sqlite3.Row-like — subscriptable y .keys()."""
    def __getitem__(self, k):
        return super().__getitem__(k)


class FakeConn:
    """Conn fake que devuelve precios desde un mapa {equipo_id: precio}.

    Simula un cliente verificado (dni_validado_at no-NULL) para que el gate de
    verificación en cliente_crear_pedido no bloquee los tests de seguridad de precios.
    """
    def __init__(self, precios_catalogo: dict[int, int]):
        self._precios = precios_catalogo
        self._pending_eq_id: int | None = None
        self._pending_query: str = ""

    def execute(self, sql, params=()):
        self._pending_query = sql
        if "FROM equipos WHERE id" in sql:
            self._pending_eq_id = params[0] if params else None
        return self

    def fetchone(self):
        sql = self._pending_query
        # Gate de verificación de identidad: devuelve cliente verificado.
        if "dni_validado_at" in sql and "FROM clientes" in sql:
            return FakeRow(dni_validado_at="2026-01-01T00:00:00")
        eq_id = self._pending_eq_id
        self._pending_eq_id = None
        if eq_id is None or eq_id not in self._precios:
            return None
        return FakeRow(precio_jornada=self._precios[eq_id])

    def fetchall(self):
        return []

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

    # 1. Sesión cliente válida (saltea require_cliente).
    monkeypatch.setattr(
        "routes.cliente_portal.require_cliente",
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
        "routes.cliente_portal.get_db",
        lambda: FakeConn(precios_catalogo),
    )

    # 4. Interceptar `create_pedido` (no la ejecutamos de verdad) para
    #    capturar el payload que recibió.
    captured = {}

    def fake_create_pedido(payload, background=None):
        captured["payload"] = payload
        return {"id": 1, "ok": True}

    monkeypatch.setattr(
        "routes.alquileres.create_pedido",
        fake_create_pedido,
    )

    # 5. Llamar al endpoint con un body que intenta colar precio_jornada=1.
    body = PedidoClienteCreate(
        fecha_desde="2030-01-01T10:00",
        fecha_hasta="2030-01-02T10:00",
        items=[CartItemIn(equipo_id=7, cantidad=3, precio_jornada=1)],
    )
    cliente_crear_pedido(body, FakeRequest(), BackgroundTasks())

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
        "routes.cliente_portal.require_cliente",
        lambda req: {"cliente_id": 42, "email": "cliente@test.com"},
    )
    monkeypatch.setattr(
        "routes.alquileres._validar_horarios_habilitados",
        lambda conn, desde, hasta: None,
    )
    monkeypatch.setattr(
        "routes.cliente_portal.get_db",
        lambda: FakeConn({}),  # catálogo vacío
    )

    body = PedidoClienteCreate(
        fecha_desde="2030-01-01T10:00",
        fecha_hasta="2030-01-02T10:00",
        items=[CartItemIn(equipo_id=999, cantidad=1, precio_jornada=1000)],
    )
    with pytest.raises(HTTPException) as exc:
        cliente_crear_pedido(body, FakeRequest(), BackgroundTasks())
    assert exc.value.status_code == 404
    assert "999" in exc.value.detail
