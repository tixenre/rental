"""Validación del campo SpecDef.value_aliases (embudo de alias de valor,
#1163 Fase 2). Puro Pydantic, sin DB — ver test_specs_value_aliases_db.py
para el seeder/mapear_valor contra Postgres real.
"""
import pytest

from services.specs.registry.models import SpecDef

pytestmark = pytest.mark.unit


def test_value_aliases_valido_en_enum():
    spec = SpecDef(
        key="formato", label="Formato", tipo="enum",
        enum_options=["Full-frame", "Super 35"],
        value_aliases={"Full-frame": ["FF", "full frame"]},
    )
    assert spec.value_aliases == {"Full-frame": ["FF", "full frame"]}


def test_value_aliases_default_vacio():
    spec = SpecDef(key="peso_g", label="Peso", tipo="number")
    assert spec.value_aliases == {}


def test_value_aliases_rechaza_clave_fuera_de_enum_options():
    with pytest.raises(ValueError, match="fuera de"):
        SpecDef(
            key="formato", label="Formato", tipo="enum",
            enum_options=["Full-frame"],
            value_aliases={"Super 35": ["S35"]},
        )


def test_value_aliases_rechaza_tipo_no_enum():
    with pytest.raises(ValueError, match="no debe tener value_aliases"):
        SpecDef(key="peso_g", label="Peso", tipo="number", value_aliases={"x": ["y"]})


def test_value_aliases_permitido_en_multi_enum():
    spec = SpecDef(
        key="alimentacion", label="Alimentación", tipo="multi_enum",
        enum_options=["AC", "V-mount"],
        value_aliases={"V-mount": ["Vmount", "V mount"]},
    )
    assert spec.value_aliases["V-mount"] == ["Vmount", "V mount"]
