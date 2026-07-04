"""Tests de arca_fe.ejemplos — la galería de muestra con datos ficticios."""
from __future__ import annotations

import pytest

from arca_fe.ejemplos import (
    ESCENAS,
    _EMISOR_RAZON_SOCIAL_EJEMPLO,
    _RECEPTOR_NOMBRE_EJEMPLO,
    _comprobante_ejemplo,
    generar_galeria_html,
)
from arca_fe.render import renderizar_comprobante_html

pytestmark = pytest.mark.unit

# Nombres que NUNCA deberían aparecer en los datos de ejemplo — si alguna vez se coló un dato real
# durante el desarrollo, este test lo cazaría (regresión concreta: "Ignacio Beramendi" apareció en
# fixtures de test en algún momento y casi se filtró a un preview visual real).
_NOMBRES_PROHIBIDOS = ("Ignacio Beramendi",)


def test_escenas_cubre_las_3_letras_la_nc_y_los_3_layouts():
    letras_cbte = {cbte_tipo for _, cbte_tipo, _ in ESCENAS}
    layouts = {layout for _, _, layout in ESCENAS}
    assert layouts == {"oficial", "detallada", "simplificada"}
    # Al menos una Factura (no-NC) de cada letra A/B/C, más alguna Nota de Crédito.
    from arca_fe import CbteTipo

    assert CbteTipo.FACTURA_A in letras_cbte
    assert CbteTipo.FACTURA_B in letras_cbte
    assert CbteTipo.FACTURA_C in letras_cbte
    assert any(t in letras_cbte for t in (
        CbteTipo.NOTA_CREDITO_A, CbteTipo.NOTA_CREDITO_B, CbteTipo.NOTA_CREDITO_C,
    ))


@pytest.mark.parametrize("titulo,cbte_tipo,layout", ESCENAS)
def test_cada_escena_renderiza_sin_romper(titulo, cbte_tipo, layout):
    datos = _comprobante_ejemplo(cbte_tipo)
    html = renderizar_comprobante_html(datos, layout=layout)
    assert html.startswith("<!DOCTYPE html>")


def test_galeria_html_incluye_las_4_escenas():
    html = generar_galeria_html()
    assert html.count("<iframe") == len(ESCENAS)
    for titulo, _, _ in ESCENAS:
        assert titulo in html


def test_galeria_html_avisa_que_los_datos_son_ficticios():
    html = generar_galeria_html()
    assert "ficticio" in html.lower()


def test_datos_de_ejemplo_no_contienen_nombres_reales_conocidos():
    html = generar_galeria_html()
    for nombre in _NOMBRES_PROHIBIDOS:
        assert nombre not in html


def test_emisor_y_receptor_de_ejemplo_son_genericos():
    """Nombres tipo 'Empresa de Ejemplo'/'Cliente de Ejemplo' — no un nombre propio real."""
    assert "Ejemplo" in _EMISOR_RAZON_SOCIAL_EJEMPLO
    assert "Ejemplo" in _RECEPTOR_NOMBRE_EJEMPLO
