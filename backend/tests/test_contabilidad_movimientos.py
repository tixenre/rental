"""Contabilidad (#809) — validación de movimientos (tests puros, sin DB).

Cubre la coherencia tipo↔cuentas↔categoría de `validar_estructura_movimiento`.
La parte SQL (alta/anulación/saldos) se ejerce en `test_contabilidad_db.py`.
"""

import pytest

from contabilidad.constants import TIPOS_MOVIMIENTO
from contabilidad.commands.movimientos import validar_estructura_movimiento
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


class TestValidarCategoria:
    def test_limpia_espacios(self):
        assert validar_categoria("  Alquiler  ") == "Alquiler"

    def test_vacia_falla(self):
        with pytest.raises(ValueError):
            validar_categoria("   ")
