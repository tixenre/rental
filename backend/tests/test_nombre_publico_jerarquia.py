"""Jerarquía de resolución del nombre público (2026-07 — molde vivo por categoría).

Cubre `construir_nombre_publico` (función pura): override manual → molde de
categoría (manda) → molde por-ficha (fallback) → vacío. El molde de categoría
gana sobre el de ficha; un molde presente que rinde vacío no bloquea al
siguiente. Ver services/nombre_builder.py y la decisión de 2026-07.
"""

import pytest

pytestmark = pytest.mark.unit

from services.nombre_builder import construir_nombre_publico


SPECS_CAMARA = [
    {"label": "Formato", "value": "Super 35", "tipo": "enum"},
    {"label": "Montura", "value": "RF", "tipo": "enum"},
]


def _build(**kw):
    base = dict(
        nombre_interno="RED Komodo X (interno)",
        marca="RED",
        modelo="Komodo X",
        categoria_raiz="Cámaras",
        specs_en_nombre=SPECS_CAMARA,
    )
    base.update(kw)
    return construir_nombre_publico(**base)


def test_molde_categoria_arma_nombre_desde_specs():
    corto, largo = _build(categoria_template="{marca} {modelo} {spec:Formato} {spec:Montura}")
    assert corto == "RED Komodo X Super 35 RF"
    assert largo == corto


def test_override_manual_gana_sobre_todo():
    corto, _ = _build(
        categoria_template="{marca} {modelo} {spec:Formato}",
        template_override="{marca} {modelo}",
        nombre_publico_override="Nombre a mano",
    )
    assert corto == "Nombre a mano"


def test_molde_categoria_manda_sobre_ficha():
    # Ambos moldes presentes → gana el de categoría (manda).
    corto, _ = _build(
        categoria_template="{marca} {modelo} {spec:Formato}",
        template_override="solo-ficha {modelo}",
    )
    assert corto == "RED Komodo X Super 35"


def test_molde_categoria_vacio_cae_a_ficha():
    # El molde de categoría referencia un spec inexistente → rinde vacío →
    # no bloquea: cae al molde de ficha en vez de dejar el nombre en blanco.
    corto, _ = _build(
        categoria_template="{spec:NoExiste}",
        template_override="{marca} {modelo}",
    )
    assert corto == "RED Komodo X"


def test_sin_ningun_molde_devuelve_vacio():
    corto, largo = _build()
    assert corto == ""
    assert largo == ""


def test_solo_ficha_sin_categoria_funciona():
    # Compat: equipos cuya categoría no tiene molde siguen usando el de ficha.
    corto, _ = _build(categoria_template=None, template_override="{marca} {modelo}")
    assert corto == "RED Komodo X"
