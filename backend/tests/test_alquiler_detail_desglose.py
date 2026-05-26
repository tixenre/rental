"""Test del enriquecimiento canónico del detail con desglose (neto/IVA/total).

Cierra #496: admin, portal, carrito y PDF deben mostrar el MISMO total,
con IVA solo para responsable_inscripto. La fuente de verdad es
`services/precios.calcular_total`. El backend lo agrega al detail vía
`_enriquecer_pedido_con_total`.

Verifica el wiring (que los campos quedan en el dict del pedido). La
fórmula en sí está cubierta por `test_precios_service.py`.
"""

import pytest

from routes.alquileres import _enriquecer_pedido_con_total


pytestmark = pytest.mark.unit


class FakeConn:
    """Conn fake que devuelve un perfil_impuestos configurable cuando se
    consulta `SELECT perfil_impuestos FROM clientes WHERE id = ?`."""

    def __init__(self, perfil_cliente: str | None = None):
        self._perfil = perfil_cliente
        self._last_sql = ""

    def execute(self, sql, params=()):
        self._last_sql = sql
        return self

    def fetchone(self):
        if "FROM clientes" in self._last_sql and self._perfil is not None:
            return {"perfil_impuestos": self._perfil}
        return None


def _pedido_base() -> dict:
    """Pedido típico: 7 jornadas, 1 ítem × $10.000/jornada = $70.000 bruto.
    Sin descuento. Sin cliente cargado (consumidor final por default)."""
    return {
        "id": 1,
        "cliente_id": 42,
        "fecha_desde": "2026-06-01T10:00:00",
        "fecha_hasta": "2026-06-08T10:00:00",
        "descuento_pct": 0,
        "descuento_jornadas_pct": 0,
        "items": [{"equipo_id": 7, "cantidad": 1, "precio_jornada": 10000}],
    }


class TestConsumidorFinal:
    """Sin IVA — total = neto."""

    def test_sin_descuento(self):
        pedido = _pedido_base()
        _enriquecer_pedido_con_total(FakeConn("consumidor_final"), pedido)

        assert pedido["bruto"] == 70000
        assert pedido["descuento_monto"] == 0
        assert pedido["monto_neto"] == 70000
        assert pedido["con_iva"] is False
        assert pedido["iva_monto"] == 0
        assert pedido["total_con_iva"] == 70000
        assert pedido["cantidad_jornadas"] == 7

    def test_con_descuento_jornadas(self):
        pedido = _pedido_base()
        pedido["descuento_jornadas_pct"] = 10.0
        _enriquecer_pedido_con_total(FakeConn("consumidor_final"), pedido)

        # 70000 - 10% = 63000
        assert pedido["bruto"] == 70000
        assert pedido["descuento_monto"] == 7000
        assert pedido["monto_neto"] == 63000
        assert pedido["iva_monto"] == 0
        assert pedido["total_con_iva"] == 63000


class TestResponsableInscripto:
    """Con IVA discriminado (21% sobre el neto, no sobre el bruto)."""

    def test_sin_descuento(self):
        pedido = _pedido_base()
        _enriquecer_pedido_con_total(FakeConn("responsable_inscripto"), pedido)

        # 70000 neto + 21% = 84700
        assert pedido["monto_neto"] == 70000
        assert pedido["con_iva"] is True
        assert pedido["iva_pct"] == 21.0
        assert pedido["iva_monto"] == 14700
        assert pedido["total_con_iva"] == 84700

    def test_con_descuento_iva_sobre_neto(self):
        """Regresión: el IVA se calcula sobre el neto (con descuento), no
        sobre el bruto. Era el bug de #502 en el PDF."""
        pedido = _pedido_base()
        pedido["descuento_jornadas_pct"] = 10.0
        _enriquecer_pedido_con_total(FakeConn("responsable_inscripto"), pedido)

        # bruto 70000, descuento 10% → neto 63000.
        # IVA 21% sobre 63000 = 13230. Total = 76230.
        assert pedido["monto_neto"] == 63000
        assert pedido["iva_monto"] == 13230
        assert pedido["total_con_iva"] == 76230


class TestEdgeCases:
    def test_sin_cliente_carga_perfil_consumidor_final_default(self):
        """Pedido sin cliente_id (atípico): tratado como sin IVA."""
        pedido = _pedido_base()
        pedido["cliente_id"] = None
        _enriquecer_pedido_con_total(FakeConn(None), pedido)

        assert pedido["con_iva"] is False
        assert pedido["total_con_iva"] == 70000

    def test_perfil_ya_cargado_no_reconsulta(self):
        """Si el caller ya puso `cliente_perfil_impuestos` (ej. PDF lo
        carga aparte), no reconsultamos la BD."""
        pedido = _pedido_base()
        pedido["cliente_perfil_impuestos"] = "responsable_inscripto"
        # FakeConn que devolvería None si fuera consultado.
        _enriquecer_pedido_con_total(FakeConn(None), pedido)

        # Aplicó IVA → leyó del dict, no de la BD.
        assert pedido["con_iva"] is True
        assert pedido["iva_monto"] == 14700

    def test_pedido_sin_fechas_jornadas_uno(self):
        """Pedido en borrador sin fechas: jornadas=1, sin sumar."""
        pedido = _pedido_base()
        pedido["fecha_desde"] = None
        pedido["fecha_hasta"] = None
        _enriquecer_pedido_con_total(FakeConn("consumidor_final"), pedido)

        # 1 item × $10000 × 1 jornada = $10000
        assert pedido["cantidad_jornadas"] == 1
        assert pedido["bruto"] == 10000
        assert pedido["total_con_iva"] == 10000

    def test_monotributo_no_es_ri(self):
        """Monotributo no factura IVA discriminado en este negocio."""
        pedido = _pedido_base()
        _enriquecer_pedido_con_total(FakeConn("monotributo"), pedido)

        assert pedido["con_iva"] is False
        assert pedido["total_con_iva"] == 70000
