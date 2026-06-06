"""Los datos de contacto/identidad del pedido (nombre, email, teléfono) se
muestran SIEMPRE en vivo desde la ficha del cliente (decisión 2026-06-06).

El pedido guarda una foto al crearse, pero al mostrarlo se sobrescribe con el
dato actual del cliente — en cualquier estado. La plata (precio/descuento) NO
se toca acá: eso queda congelado en confirmados/finalizados.
"""

import pytest

from routes.alquileres import (
    _enriquecer_pedido_con_cliente,
    _enriquecer_pedidos_con_cliente,
)


pytestmark = pytest.mark.unit


class FakeConn:
    """Devuelve filas de `clientes` desde un mapa {id: dict}."""

    def __init__(self, clientes: dict[int, dict]):
        self._clientes = clientes
        self._sql = ""
        self._params = ()

    def execute(self, sql, params=()):
        self._sql = sql
        self._params = params or ()
        return self

    def fetchone(self):
        if "FROM clientes WHERE id" in self._sql:
            return self._clientes.get(self._params[0])
        return None

    def fetchall(self):
        if "FROM clientes WHERE id IN" in self._sql:
            return [self._clientes[i] for i in self._params if i in self._clientes]
        return []

    def close(self):
        pass


def _foto():
    """Pedido con la foto vieja del cliente."""
    return {
        "id": 1,
        "cliente_id": 7,
        "cliente_nombre": "Perez, Juan",
        "cliente_email": "viejo@mail.com",
        "cliente_telefono": "111-viejo",
        "descuento_pct": 30,  # la plata no se toca
    }


def test_sobrescribe_con_el_dato_actual():
    conn = FakeConn({7: {"nombre": "Juan", "apellido": "Pereyra",
                         "email": "nuevo@mail.com", "telefono": "222-nuevo"}})
    p = _foto()
    _enriquecer_pedido_con_cliente(conn, p)
    assert p["cliente_nombre"] == "Juan Pereyra"   # apellido corregido, "Nombre Apellido"
    assert p["cliente_email"] == "nuevo@mail.com"
    assert p["cliente_telefono"] == "222-nuevo"
    assert p["descuento_pct"] == 30                  # plata intacta


def test_sin_cliente_vinculado_conserva_la_foto():
    conn = FakeConn({})
    p = _foto()
    p["cliente_id"] = None
    _enriquecer_pedido_con_cliente(conn, p)
    assert p["cliente_nombre"] == "Perez, Juan"
    assert p["cliente_email"] == "viejo@mail.com"


def test_cliente_inexistente_conserva_la_foto():
    conn = FakeConn({})  # id 7 no está
    p = _foto()
    _enriquecer_pedido_con_cliente(conn, p)
    assert p["cliente_nombre"] == "Perez, Juan"


def test_email_vacio_en_ficha_no_borra_el_contacto():
    # Si la ficha tiene email/teléfono vacíos, se conserva la foto (no perder
    # el contacto). El nombre siempre se refresca (apellido/nombre son obligatorios).
    conn = FakeConn({7: {"nombre": "Juan", "apellido": "Pereyra",
                         "email": "", "telefono": None}})
    p = _foto()
    _enriquecer_pedido_con_cliente(conn, p)
    assert p["cliente_nombre"] == "Juan Pereyra"
    assert p["cliente_email"] == "viejo@mail.com"
    assert p["cliente_telefono"] == "111-viejo"


def test_batch_listado():
    conn = FakeConn({
        7: {"id": 7, "nombre": "Juan", "apellido": "Pereyra",
            "email": "n@mail.com", "telefono": "222"},
        9: {"id": 9, "nombre": "Ana", "apellido": "Gómez",
            "email": "a@mail.com", "telefono": "333"},
    })
    pedidos = [
        {"id": 1, "cliente_id": 7, "cliente_nombre": "Perez, Juan",
         "cliente_email": "x", "cliente_telefono": "x"},
        {"id": 2, "cliente_id": 9, "cliente_nombre": "Viejo, Ana",
         "cliente_email": "x", "cliente_telefono": "x"},
        {"id": 3, "cliente_id": None, "cliente_nombre": "Manual",
         "cliente_email": "manual@mail.com", "cliente_telefono": "000"},
    ]
    _enriquecer_pedidos_con_cliente(conn, pedidos)
    assert pedidos[0]["cliente_nombre"] == "Juan Pereyra"
    assert pedidos[1]["cliente_nombre"] == "Ana Gómez"
    assert pedidos[2]["cliente_nombre"] == "Manual"  # sin cliente vinculado, intacto
