"""Reporte de liquidación (#88) — tests puros del motor (sin DB).

Cubre el modelo de comisiones (reparto + validación) y la agregación
(prorrateo ya viene en las filas; acá se testea reparto + buckets mes/día +
detalle por dueño). La parte SQL se valida en staging con datos reales.
"""

import pytest

from reportes.comisiones import DEFAULT_MODELO, repartir, validar_modelo
from reportes.liquidacion import agregar


class TestRepartir:
    def test_rambla_se_lleva_todo(self):
        assert repartir("Rambla", 100000, DEFAULT_MODELO) == {"Rambla": 100000}

    def test_pablo_50_45_5(self):
        r = repartir("Pablo", 100000, DEFAULT_MODELO)
        assert r == {"Pablo": 50000, "Rambla": 45000, "Tincho": 5000}

    def test_tincho_50_45_5(self):
        r = repartir("Tincho", 100000, DEFAULT_MODELO)
        assert r == {"Tincho": 50000, "Rambla": 45000, "Pablo": 5000}

    def test_dueno_desconocido_cobra_todo(self):
        # Un valor legacy fuera del modelo no pierde plata: 100% a sí mismo.
        assert repartir("Legacy SA", 100000, DEFAULT_MODELO) == {"Legacy SA": 100000}

    def test_reparto_suma_el_monto(self):
        for dueno in ("Rambla", "Pablo", "Tincho"):
            assert sum(repartir(dueno, 123456, DEFAULT_MODELO).values()) == pytest.approx(123456)


class TestValidarModelo:
    def test_default_es_valido(self):
        validar_modelo(DEFAULT_MODELO)  # no lanza

    def test_rechaza_no_suma_100(self):
        with pytest.raises(ValueError):
            validar_modelo({"Pablo": {"Pablo": 50, "Rambla": 40}})  # suma 90

    def test_rechaza_pct_fuera_de_rango(self):
        with pytest.raises(ValueError):
            validar_modelo({"Rambla": {"Rambla": 150}})

    def test_rechaza_vacio(self):
        with pytest.raises(ValueError):
            validar_modelo({})

    def test_rechaza_pct_no_numerico(self):
        with pytest.raises(ValueError):
            validar_modelo({"Rambla": {"Rambla": "100"}})


class TestAgregar:
    def _filas(self):
        # Un pedido de Pablo saldado en mayo, uno de Rambla saldado en junio.
        return [
            {"fecha": "2026-05-10", "pedido_id": 1, "dueno": "Pablo",
             "equipo": "Sony FX3", "monto": 100000},
            {"fecha": "2026-06-03", "pedido_id": 2, "dueno": "Rambla",
             "equipo": "Canon R5", "monto": 40000},
        ]

    def test_resumen_total_y_reparto(self):
        d = agregar(self._filas(), DEFAULT_MODELO)
        assert d["resumen"]["total"] == 140000
        pb = d["resumen"]["por_beneficiario"]
        # Pablo: 50k; Rambla: 45k (de Pablo) + 40k (suyo) = 85k; Tincho: 5k.
        assert pb["Pablo"] == 50000
        assert pb["Rambla"] == 85000
        assert pb["Tincho"] == 5000

    def test_buckets_por_mes_atribuyen_al_mes_de_saldado(self):
        d = agregar(self._filas(), DEFAULT_MODELO)
        meses = {m["mes"]: m for m in d["por_mes"]}
        assert set(meses) == {"2026-05", "2026-06"}
        assert meses["2026-05"]["total"] == 100000
        assert meses["2026-06"]["total"] == 40000

    def test_por_dia_y_por_dueno(self):
        d = agregar(self._filas(), DEFAULT_MODELO)
        dias = {x["dia"] for x in d["por_dia"]}
        assert dias == {"2026-05-10", "2026-06-03"}
        duenos = {x["dueno"]: x for x in d["por_dueno"]}
        assert duenos["Pablo"]["monto_generado"] == 100000
        assert duenos["Pablo"]["reparto"]["Rambla"] == 45000
        assert duenos["Pablo"]["equipos"][0]["equipo"] == "Sony FX3"

    def test_cuenta_veces_alquilado(self):
        # Mismo equipo de Pablo en 2 pedidos distintos → veces == 2; total pedidos == 3.
        filas = [
            {"fecha": "2026-06-03", "pedido_id": 1, "dueno": "Pablo",
             "equipo": "Sony FX3", "monto": 100000},
            {"fecha": "2026-06-10", "pedido_id": 2, "dueno": "Pablo",
             "equipo": "Sony FX3", "monto": 60000},
            {"fecha": "2026-06-15", "pedido_id": 3, "dueno": "Rambla",
             "equipo": "Canon R5", "monto": 40000},
        ]
        d = agregar(filas, DEFAULT_MODELO)
        assert d["resumen"]["pedidos"] == 3
        pablo = {x["dueno"]: x for x in d["por_dueno"]}["Pablo"]
        assert pablo["pedidos"] == 2
        assert pablo["equipos"][0]["veces"] == 2

    def test_filas_vacias(self):
        d = agregar([], DEFAULT_MODELO)
        assert d["resumen"]["total"] == 0
        assert d["resumen"]["pedidos"] == 0
        assert d["por_mes"] == [] and d["por_dia"] == [] and d["por_dueno"] == []
