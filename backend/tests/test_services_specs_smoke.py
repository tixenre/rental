"""Smoke del paquete services/specs/ (Fase 0 — andamiaje, ver #1163).

Cero comportamiento todavía: solo confirma que el paquete importa limpio y que
el barrel + los errores tipados tienen la forma esperada. Se va a ir llenando
a medida que avancen las fases del rediseño (docs/PLAN_SPECS_REDISENO.md).
"""

import services.specs as specs
from services.specs.errors import ErrorSpec, SpecNoExiste, ValorNoCanonico


def test_import_no_crashea():
    assert specs is not None


def test_all_es_lista():
    assert isinstance(specs.__all__, list)


def test_errores_tipados_heredan_de_error_spec():
    assert issubclass(SpecNoExiste, ErrorSpec)
    assert issubclass(ValorNoCanonico, ErrorSpec)
    assert issubclass(ErrorSpec, ValueError)
