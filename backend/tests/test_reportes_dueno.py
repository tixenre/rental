"""Reporte por dueño (#88, fase 1) — helpers puros (sin DB).

Cubre la validación del rango de fechas y la serialización CSV. La agregación SQL
se valida en staging con datos reales (plan de prueba en la PR).
"""

import pytest

from fastapi import HTTPException

from routes.estadisticas import _validar_rango, _reporte_dueno_csv


class TestValidarRango:
    def test_rango_valido_no_lanza(self):
        _validar_rango("2026-05-01", "2026-05-31")  # no debe lanzar

    def test_fecha_mal_formada(self):
        with pytest.raises(HTTPException) as exc:
            _validar_rango("01/05/2026", "2026-05-31")
        assert exc.value.status_code == 400

    def test_desde_posterior_a_hasta(self):
        with pytest.raises(HTTPException) as exc:
            _validar_rango("2026-06-01", "2026-05-01")
        assert exc.value.status_code == 400


class TestReporteDuenoCsv:
    def test_csv_una_fila_por_equipo_mas_total(self):
        data = {
            "duenos": [
                {
                    "dueno": "Rambla",
                    "ingreso_ars": 150000,
                    "items": 3,
                    "pedidos": 2,
                    "equipos": [
                        {"equipo": "Sony FX3", "ingreso_ars": 100000, "veces": 2},
                        {"equipo": "Canon R5", "ingreso_ars": 50000, "veces": 1},
                    ],
                },
                {
                    "dueno": "Juan",
                    "ingreso_ars": 30000,
                    "items": 1,
                    "pedidos": 1,
                    "equipos": [{"equipo": "Aputure 600d", "ingreso_ars": 30000, "veces": 1}],
                },
            ],
        }
        csv_text = _reporte_dueno_csv(data)
        lines = [ln for ln in csv_text.splitlines() if ln.strip()]
        # header + 2 equipos Rambla + total Rambla + 1 equipo Juan + total Juan = 6
        assert len(lines) == 6
        assert lines[0].startswith("Dueño,Equipo")
        assert "Sony FX3" in csv_text and "Canon R5" in csv_text
        assert "Rambla — TOTAL" in csv_text and "Juan — TOTAL" in csv_text
        # el total de Rambla aparece en su fila TOTAL
        assert "150000" in csv_text

    def test_csv_sin_duenos_solo_header(self):
        csv_text = _reporte_dueno_csv({"duenos": []})
        lines = [ln for ln in csv_text.splitlines() if ln.strip()]
        assert len(lines) == 1  # solo el header
