"""Tests de `services.pedidos_enriquecimiento._resolver_datos_fiscales_pedido` (#1240) —
los 3 niveles de prioridad para "a nombre de quién factura este pedido":
productora elegida > perfil personal elegido > perfil default de la cuenta."""

from __future__ import annotations

import pytest

from services.pedidos_enriquecimiento import (
    _resolver_datos_fiscales_pedido,
    _enriquecer_pedido_con_cliente_fiscal,
)

pytestmark = pytest.mark.unit


class _FakeConn:
    """Fake conn — enruta por la tabla que aparece en el FROM del SELECT."""

    def __init__(self, productoras=None, perfiles=None, clientes=None):
        self.productoras = productoras or {}
        self.perfiles = perfiles or {}
        self.clientes = clientes or {}

    def execute(self, sql, params=None):
        sql_norm = " ".join(sql.split())

        class _R:
            def __init__(self_inner, row):
                self_inner._row = row

            def fetchone(self_inner):
                return self_inner._row

        if "FROM productoras" in sql_norm:
            return _R(self.productoras.get(params[0]))
        if "FROM cliente_perfiles_fiscales" in sql_norm:
            perfil_id, cliente_id = params
            row = self.perfiles.get(perfil_id)
            if row and row.get("cliente_id") != cliente_id:
                row = None
            return _R(row)
        if "FROM clientes" in sql_norm:
            return _R(self.clientes.get(params[0]))
        raise AssertionError(f"SQL inesperado: {sql_norm}")


def _fiscal(cuit="20111111112", perfil="responsable_inscripto", cliente_id=None):
    d = {
        "perfil_impuestos": perfil,
        "razon_social": f"Razón {cuit}",
        "domicilio_fiscal": f"Domicilio {cuit}",
        "email_facturacion": None,
        "cuit": cuit,
    }
    if cliente_id is not None:
        d["cliente_id"] = cliente_id
    return d


def test_sin_target_usa_el_default_de_clientes():
    conn = _FakeConn(clientes={7: _fiscal(cuit="20000000007", perfil="consumidor_final")})

    resultado = _resolver_datos_fiscales_pedido(conn, cliente_id=7)

    assert resultado["cuit"] == "20000000007"
    assert resultado["perfil_impuestos"] == "consumidor_final"


def test_perfil_personal_elegido_gana_sobre_el_default():
    conn = _FakeConn(
        clientes={7: _fiscal(cuit="20000000007", perfil="consumidor_final")},
        perfiles={42: _fiscal(cuit="20111111112", perfil="monotributo", cliente_id=7)},
    )

    resultado = _resolver_datos_fiscales_pedido(conn, cliente_id=7, perfil_fiscal_id=42)

    assert resultado["cuit"] == "20111111112"
    assert resultado["perfil_impuestos"] == "monotributo"


def test_productora_elegida_gana_sobre_perfil_personal_y_default():
    conn = _FakeConn(
        clientes={7: _fiscal(cuit="20000000007", perfil="consumidor_final")},
        perfiles={42: _fiscal(cuit="20111111112", perfil="monotributo", cliente_id=7)},
        productoras={5: _fiscal(cuit="30555555550", perfil="responsable_inscripto")},
    )

    resultado = _resolver_datos_fiscales_pedido(
        conn, cliente_id=7, perfil_fiscal_id=42, productora_id=5
    )

    assert resultado["cuit"] == "30555555550"
    assert resultado["perfil_impuestos"] == "responsable_inscripto"


def test_perfil_personal_de_otro_cliente_no_se_usa_cae_al_default():
    """Defensivo: un `perfil_fiscal_id` que no pertenece a `cliente_id` (no
    debería poder pasar la validación del endpoint, pero acá se verifica que
    el helper mismo no lo usa igual) cae al perfil default."""
    conn = _FakeConn(
        clientes={7: _fiscal(cuit="20000000007", perfil="consumidor_final")},
        perfiles={42: _fiscal(cuit="20111111112", perfil="monotributo", cliente_id=99)},
    )

    resultado = _resolver_datos_fiscales_pedido(conn, cliente_id=7, perfil_fiscal_id=42)

    assert resultado["cuit"] == "20000000007"


def test_enriquecer_pedido_lee_perfil_fiscal_id_y_productora_id_del_pedido():
    """`_enriquecer_pedido_con_cliente_fiscal` lee `perfil_fiscal_id`/`productora_id`
    directo del dict de pedido (columnas reales de `alquileres` tras un `SELECT *`)."""
    conn = _FakeConn(
        clientes={7: _fiscal(cuit="20000000007", perfil="consumidor_final")},
        productoras={5: _fiscal(cuit="30555555550", perfil="responsable_inscripto")},
    )
    pedido = {"cliente_id": 7, "perfil_fiscal_id": None, "productora_id": 5}

    resultado = _enriquecer_pedido_con_cliente_fiscal(conn, pedido)

    assert resultado["cliente_cuit"] == "30555555550"
    assert resultado["cliente_perfil_impuestos"] == "responsable_inscripto"


def test_enriquecer_pedido_sin_cliente_id_no_hace_nada():
    pedido = {"cliente_id": None}
    resultado = _enriquecer_pedido_con_cliente_fiscal(_FakeConn(), pedido)
    assert resultado == pedido
