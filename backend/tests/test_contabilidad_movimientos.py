"""Contabilidad (#809) — validación de movimientos (tests puros, sin DB).

Cubre la coherencia tipo↔cuentas↔categoría de `validar_estructura_movimiento`.
La parte SQL (alta/anulación/saldos) se ejerce en `test_contabilidad_db.py`.
"""

import pytest

from contabilidad.constants import TIPOS_MOVIMIENTO
from contabilidad.commands.movimientos import derivar_cambio_divisa, validar_estructura_movimiento
from contabilidad.commands.categorias import validar_categoria


class TestValidarEstructura:
    def test_gasto_ok(self):
        validar_estructura_movimiento("gasto", 1000, 3, None, 7)  # caja origen + categoría

    def test_gasto_sin_origen_falla(self):
        with pytest.raises(ValueError):
            validar_estructura_movimiento("gasto", 1000, None, None, 7)

    def test_gasto_sin_categoria_falla(self):
        with pytest.raises(ValueError):
            validar_estructura_movimiento("gasto", 1000, 3, None, None)

    def test_gasto_con_destino_falla(self):
        with pytest.raises(ValueError):
            validar_estructura_movimiento("gasto", 1000, 3, 4, 7)

    def test_transferencia_ok(self):
        validar_estructura_movimiento("transferencia", 5000, 1, 2, None)

    def test_transferencia_misma_cuenta_falla(self):
        with pytest.raises(ValueError):
            validar_estructura_movimiento("transferencia", 5000, 1, 1, None)

    def test_transferencia_sin_destino_falla(self):
        with pytest.raises(ValueError):
            validar_estructura_movimiento("transferencia", 5000, 1, None, None)

    def test_retiro_ok(self):
        validar_estructura_movimiento("retiro", 2000, 1, None, None)

    def test_retiro_con_destino_falla(self):
        with pytest.raises(ValueError):
            validar_estructura_movimiento("retiro", 2000, 1, 2, None)

    def test_aporte_ok(self):
        validar_estructura_movimiento("aporte", 2000, None, 1, None)

    def test_aporte_con_origen_falla(self):
        with pytest.raises(ValueError):
            validar_estructura_movimiento("aporte", 2000, 1, 1, None)

    def test_ajuste_necesita_una_cuenta(self):
        validar_estructura_movimiento("ajuste", 100, 3, None, None)
        with pytest.raises(ValueError):
            validar_estructura_movimiento("ajuste", 100, None, None, None)

    def test_ajuste_con_origen_y_destino_ok(self):
        # Único hueco combinatorio real entre los 5 tipos sin cubrir hasta la
        # auditoría 2026-07-02: origen Y destino a la vez (conciliación entre
        # dos cajas, sin ser una "transferencia" strictamente).
        validar_estructura_movimiento("ajuste", 100, 3, 4, None)

    def test_tipo_desconocido_falla(self):
        with pytest.raises(ValueError):
            validar_estructura_movimiento("regalo", 100, 1, None, None)

    def test_monto_no_positivo_falla(self):
        for malo in (0, -5):
            with pytest.raises(ValueError):
                validar_estructura_movimiento("gasto", malo, 3, None, 7)

    def test_monto_no_entero_falla(self):
        with pytest.raises(ValueError):
            validar_estructura_movimiento("gasto", 10.5, 3, None, 7)

    def test_categoria_solo_en_gasto(self):
        with pytest.raises(ValueError):
            validar_estructura_movimiento("transferencia", 100, 1, 2, 7)

    def test_todos_los_tipos_existen(self):
        assert set(TIPOS_MOVIMIENTO) == {"gasto", "transferencia", "retiro", "aporte", "ajuste"}


class TestDerivarCambioDivisa:
    """`derivar_cambio_divisa` — la aritmética pura de comprar/vender USD con
    ARS (bug/feature: no había flujo soportado, DECISIONES.md 2026-06-07)."""

    def test_pesos_mas_cotizacion_deriva_dolares(self):
        # "x pesos a x cambio = x dólares" — comprar dólares, origen ARS.
        origen, destino, cotiz = derivar_cambio_divisa(
            "ARS", "USD", monto_origen=125_000, cotizacion=1250,
        )
        assert (origen, destino, cotiz) == (125_000, 100, 1250.0)

    def test_pesos_mas_dolares_deriva_cotizacion(self):
        # "x pesos me dieron x dólares = x cambio" — cotización derivada.
        origen, destino, cotiz = derivar_cambio_divisa(
            "ARS", "USD", monto_origen=125_000, monto_destino=100,
        )
        assert (origen, destino, cotiz) == (125_000, 100, 1250.0)

    def test_venta_de_dolares_pesos_mas_cotizacion(self):
        # Dirección inversa: origen USD, destino ARS (vender dólares).
        origen, destino, cotiz = derivar_cambio_divisa(
            "USD", "ARS", monto_origen=100, cotizacion=1250,
        )
        assert (origen, destino, cotiz) == (100, 125_000, 1250.0)

    def test_venta_de_dolares_ambos_montos_deriva_cotizacion(self):
        origen, destino, cotiz = derivar_cambio_divisa(
            "USD", "ARS", monto_origen=100, monto_destino=125_000,
        )
        assert (origen, destino, cotiz) == (100, 125_000, 1250.0)

    def test_dolares_mas_cotizacion_deriva_pesos(self):
        # Cotización + el lado en pesos ya sabido, pero al revés: acá se conoce
        # el destino (ARS) — se deriva el origen (USD).
        origen, destino, cotiz = derivar_cambio_divisa(
            "USD", "ARS", monto_destino=125_000, cotizacion=1250,
        )
        assert (origen, destino, cotiz) == (100, 125_000, 1250.0)

    def test_misma_moneda_falla(self):
        with pytest.raises(ValueError):
            derivar_cambio_divisa("ARS", "ARS", monto_origen=1000, monto_destino=1000)

    def test_sin_lado_ars_falla(self):
        with pytest.raises(ValueError):
            derivar_cambio_divisa("USD", "USD", monto_origen=100, monto_destino=100)

    def test_faltan_dos_datos_falla(self):
        with pytest.raises(ValueError):
            derivar_cambio_divisa("ARS", "USD", cotizacion=1250)

    def test_monto_no_positivo_falla(self):
        with pytest.raises(ValueError):
            derivar_cambio_divisa("ARS", "USD", monto_origen=0, monto_destino=100)

    def test_cotizacion_no_positiva_falla(self):
        with pytest.raises(ValueError):
            derivar_cambio_divisa("ARS", "USD", monto_origen=1000, cotizacion=0)


class TestValidarCategoria:
    def test_limpia_espacios(self):
        assert validar_categoria("  Alquiler  ") == "Alquiler"

    def test_vacia_falla(self):
        with pytest.raises(ValueError):
            validar_categoria("   ")
