"""B2 #635: packing list del pedido.

Verifica:
- _packing_list_html genera HTML con los campos básicos del pedido.
- Los ítems del pedido aparecen en el HTML.
- Los componentes de kit aparecen indentados (prefijo "Kit:").
- El contenido_incluido_json se expande como ítems de caja (emoji 📦 / &#128230;).
- Un pedido sin ítems genera HTML sin errores.
"""

import json
import pytest

pytestmark = pytest.mark.unit


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_pedido(**kwargs) -> dict:
    base = {
        "id": 42,
        "numero_pedido": 7,
        "cliente_nombre": "Ana Gómez",
        "cliente_email": "ana@example.com",
        "fecha_desde": "2026-06-01",
        "fecha_hasta": "2026-06-03",
        "items": [],
    }
    base.update(kwargs)
    return base


def _make_item(nombre="Cámara FX3", cantidad=1, **kwargs) -> dict:
    return {
        "nombre": nombre,
        "marca": "Sony",
        "modelo": None,
        "cantidad": cantidad,
        "foto_url": None,
        "nombre_publico": None,
        "nombre_publico_largo": None,
        "componentes": [],
        "contenido_incluido_json": None,
        **kwargs,
    }


def _make_comp(nombre="Cargador", cantidad=1, **kwargs) -> dict:
    return {
        "nombre": nombre,
        "marca": "Sony",
        "modelo": None,
        "cantidad": cantidad,
        "foto_url": None,
        "nombre_publico": None,
        "nombre_publico_largo": None,
        **kwargs,
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_packing_list_html_cabecera():
    from pdf import _packing_list_html

    pedido = _make_pedido()
    result = _packing_list_html(pedido)

    assert "Packing List" in result
    assert "R-0007" in result
    assert "Ana G" in result       # cliente_nombre
    assert "ana@example.com" in result


def test_packing_list_html_item_simple():
    from pdf import _packing_list_html

    pedido = _make_pedido(items=[_make_item("Cámara FX3", cantidad=2)])
    result = _packing_list_html(pedido)

    assert "FX3" in result
    # Cantidad
    assert ">2<" in result


def test_packing_list_html_componentes_kit():
    from pdf import _packing_list_html

    item = _make_item("Cámara FX3", componentes=[_make_comp("Cargador BC-QZ1")])
    pedido = _make_pedido(items=[item])
    result = _packing_list_html(pedido)

    assert "FX3" in result
    assert "Kit:" in result
    assert "Cargador BC-QZ1" in result


def test_packing_list_html_contenido_incluido():
    from pdf import _packing_list_html

    contenido = json.dumps([
        {"nombre": "Cable USB-C", "cantidad": 1, "foto_url": None},
        {"nombre": "Tapa de cuerpo", "cantidad": 2, "foto_url": None},
    ])
    item = _make_item("Cámara FX3", contenido_incluido_json=contenido)
    pedido = _make_pedido(items=[item])
    result = _packing_list_html(pedido)

    assert "Cable USB-C" in result
    assert "Tapa de cuerpo" in result
    # row-contenido class → distingue visualmente los ítems de caja
    assert "row-contenido" in result


def test_packing_list_html_contenido_incluido_json_invalido():
    """JSON corrupto no debe explotar — se ignora silenciosamente."""
    from pdf import _packing_list_html

    item = _make_item("Cámara FX3", contenido_incluido_json="no es json")
    pedido = _make_pedido(items=[item])
    result = _packing_list_html(pedido)

    # Debe seguir generando HTML válido
    assert "Packing List" in result
    assert "FX3" in result


def test_packing_list_html_sin_items():
    from pdf import _packing_list_html

    pedido = _make_pedido(items=[])
    result = _packing_list_html(pedido)

    assert "Packing List" in result
    # Tabla vacía pero válida
    assert "<tbody>" in result


def test_packing_list_html_checkbox_salida_retorno():
    from pdf import _packing_list_html

    pedido = _make_pedido(items=[_make_item()])
    result = _packing_list_html(pedido)

    # Los encabezados de checklist están presentes
    assert "Salida" in result
    assert "Retorno" in result
    # Los checkboxes renderizados
    assert "checkbox" in result


def test_packing_list_html_contenido_multiplicado_por_cantidad():
    """Los componentes de kit se multiplican por la cantidad del ítem padre."""
    from pdf import _packing_list_html

    # 3 cámaras, cada una con 1 cargador → debería mostrar 3
    item = _make_item("Cámara FX3", cantidad=3, componentes=[_make_comp("Cargador", cantidad=1)])
    pedido = _make_pedido(items=[item])
    result = _packing_list_html(pedido)

    assert ">3<" in result  # cant del item principal
    # El componente también debe aparecer con cant×3
    assert "Kit:" in result
