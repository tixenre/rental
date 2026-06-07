"""Contabilidad (#809) — tests puros del motor (sin DB).

Cubre la validación de cuentas y el cálculo de saldos (la matemática: saldo_inicial
+ ingresos derivados + entradas − egresos). La parte SQL (derivación real de
`alquiler_pagos`) se valida en `test_contabilidad_db.py` contra Postgres real.
"""

import pytest

from contabilidad.cuentas import SOCIOS, TIPOS_CUENTA, validar_cuenta
from contabilidad.saldos import calcular_saldos


class TestValidarCuenta:
    def test_caja_simple_ok(self):
        validar_cuenta({"nombre": "Efectivo", "tipo": "caja"})  # no lanza

    def test_cuenta_socio_ok(self):
        validar_cuenta({"nombre": "Caja Tincho", "tipo": "socio", "socio": "Tincho"})

    def test_todos_los_tipos_son_validos(self):
        for tipo in TIPOS_CUENTA:
            data = {"nombre": f"X {tipo}", "tipo": tipo}
            if tipo == "socio":
                data["socio"] = "Pablo"
            validar_cuenta(data)

    def test_rechaza_nombre_vacio(self):
        with pytest.raises(ValueError):
            validar_cuenta({"nombre": "  ", "tipo": "caja"})

    def test_rechaza_tipo_desconocido(self):
        with pytest.raises(ValueError):
            validar_cuenta({"nombre": "X", "tipo": "billetera"})

    def test_rechaza_socio_en_cuenta_no_socio(self):
        with pytest.raises(ValueError):
            validar_cuenta({"nombre": "Efectivo", "tipo": "caja", "socio": "Pablo"})

    def test_rechaza_socio_invalido(self):
        with pytest.raises(ValueError):
            validar_cuenta({"nombre": "Caja X", "tipo": "socio", "socio": "Mariano"})

    def test_cuenta_socio_sin_socio_falla(self):
        with pytest.raises(ValueError):
            validar_cuenta({"nombre": "Caja X", "tipo": "socio"})

    def test_rechaza_saldo_no_entero(self):
        with pytest.raises(ValueError):
            validar_cuenta({"nombre": "X", "tipo": "caja", "saldo_inicial": "1000"})

    def test_socios_son_los_dos_fisicos(self):
        assert set(SOCIOS) == {"Pablo", "Tincho"}


class TestCalcularSaldos:
    def _cuentas(self):
        return [
            {"id": 1, "nombre": "Caja Tincho", "tipo": "socio", "socio": "Tincho", "saldo_inicial": 0},
            {"id": 2, "nombre": "Caja Pablo", "tipo": "socio", "socio": "Pablo", "saldo_inicial": 0},
            {"id": 3, "nombre": "Efectivo", "tipo": "caja", "socio": None, "saldo_inicial": 50000},
            {"id": 5, "nombre": "Fondo Rambla", "tipo": "fondo", "socio": None, "saldo_inicial": 0},
        ]

    def test_ingreso_derivado_va_a_la_caja_del_socio(self):
        filas = calcular_saldos(self._cuentas(), [], {"Tincho": 480000, "Pablo": 120000})
        by = {f["nombre"]: f for f in filas}
        assert by["Caja Tincho"]["saldo"] == 480000
        assert by["Caja Tincho"]["ingresos_alquiler"] == 480000
        assert by["Caja Pablo"]["saldo"] == 120000
        # Una caja sin socio NO recibe ingresos derivados.
        assert by["Efectivo"]["ingresos_alquiler"] == 0
        assert by["Efectivo"]["saldo"] == 50000  # solo su saldo inicial

    def test_movimientos_mueven_plata(self):
        movs = [
            {"monto": 25000, "cuenta_origen_id": 3, "cuenta_destino_id": None},   # gasto desde Efectivo
            {"monto": 100000, "cuenta_origen_id": 1, "cuenta_destino_id": 5},     # transf Tincho→Fondo
            {"monto": 30000, "cuenta_origen_id": None, "cuenta_destino_id": 2},   # aporte a Caja Pablo
        ]
        filas = calcular_saldos(self._cuentas(), movs, {"Tincho": 480000, "Pablo": 120000})
        by = {f["nombre"]: f for f in filas}
        # Tincho: 0 + 480000 (ingresos) − 100000 (transf out) = 380000
        assert by["Caja Tincho"]["saldo"] == 380000
        assert by["Caja Tincho"]["egresos"] == 100000
        # Pablo: 0 + 120000 + 30000 (aporte) = 150000
        assert by["Caja Pablo"]["saldo"] == 150000
        assert by["Caja Pablo"]["entradas"] == 30000
        # Efectivo: 50000 − 25000 (gasto) = 25000
        assert by["Efectivo"]["saldo"] == 25000
        assert by["Efectivo"]["egresos"] == 25000
        # Fondo Rambla: 0 + 100000 (transf in) = 100000
        assert by["Fondo Rambla"]["saldo"] == 100000
        assert by["Fondo Rambla"]["entradas"] == 100000

    def test_ingreso_de_socio_sin_caja_se_ignora(self):
        # Un destinatario que no tiene caja en la lista no rompe ni se pierde
        # silenciosamente en otra cuenta (la reconciliación lo cazará aparte).
        filas = calcular_saldos(self._cuentas(), [], {"Tincho": 100, "Fantasma": 999})
        total_ingresos = sum(f["ingresos_alquiler"] for f in filas)
        assert total_ingresos == 100  # los 999 del fantasma no entran a ninguna caja

    def test_sin_cuentas_da_lista_vacia(self):
        assert calcular_saldos([], [], {}) == []
