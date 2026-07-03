"""Candado del módulo orquestador `services.finanzas_flujo` (auditoría cruzada de
plata, 2026-07-02): los consumidores del desglose de un pedido deben pasar por la
fachada, ninguno reimplementa el cálculo inline. Mismo patrón que
`test_carrito_precio_efectivo.py`.

El bug real que esto blinda: `pdf_templates.py` reimplementaba
`precio_jornada * cantidad * jornadas` desde cero (sin `cobro_modo`), y
`services/facturacion/engine.py` importaba `_enriquecer_pedido_con_total` de
`routes.alquileres` (un service importando de un route) en vez de la fachada.
"""
import inspect

import pytest

import pdf_templates
import services.finanzas_flujo.pedido as finanzas_pedido
from services.facturacion import engine as facturacion_engine

pytestmark = pytest.mark.unit


def _src(obj) -> str:
    return inspect.getsource(obj)


def test_pdf_usa_el_helper_cobro_modo_aware():
    """`_pedido_html`/`_sum_bruto` deben delegar en `_bruto_item_pdf` (que sí
    respeta `cobro_modo`), no reimplementar `precio_jornada * cantidad * j`
    directo sobre el ítem principal."""
    src = _src(pdf_templates)
    assert "_bruto_item_pdf(" in src, (
        "pdf_templates debe usar _bruto_item_pdf para el bruto de un ítem "
        "(cobro_modo-aware) — no reimplementar la multiplicación inline."
    )


def test_bruto_item_pdf_respeta_cobro_modo():
    src = _src(pdf_templates._bruto_item_pdf)
    assert "cobro_modo" in src, (
        "_bruto_item_pdf debe chequear cobro_modo (una línea 'fijo' no se "
        "multiplica por jornadas) — mismo criterio que services.precios.bruto_linea."
    )


def test_facturacion_engine_usa_la_fachada_no_el_route():
    """`services/facturacion/engine.py` es un SERVICE — no debe importar el
    desglose de plata de un ROUTE (`routes.alquileres`); debe pasar por
    `services.finanzas_flujo.pedido`."""
    src = _src(facturacion_engine._get_pedido)
    assert "finanzas_flujo" in src, (
        "_get_pedido debe importar desglose_de_pedido de services.finanzas_flujo.pedido, "
        "no _enriquecer_pedido_con_total de routes.alquileres."
    )
    assert "_enriquecer_pedido_con_total" not in src, (
        "_get_pedido ya no debe importar _enriquecer_pedido_con_total (el wrapper de "
        "routes.alquileres) — un service no debe depender de un route."
    )


def test_desglose_de_pedido_es_cobro_modo_aware():
    """Sanity: la fachada realmente arma cobro_modo al llamar calcular_total
    (no lo pierde como hacía el bug original)."""
    src = _src(finanzas_pedido.desglose_de_pedido)
    assert '"cobro_modo"' in src or "'cobro_modo'" in src, (
        "desglose_de_pedido debe incluir cobro_modo en items_para_total."
    )
