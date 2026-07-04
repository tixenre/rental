"""Candado de `_documentos_disponibles` (routes/cliente_portal/core.py).

Remito, Contrato y Certificado de seguro (albarán) están disponibles desde
"presupuesto" — apenas se solicita el pedido, antes de que Rambla lo
confirme — para que el cliente tenga tiempo de leerlos o consultar a su
aseguradora sin esperar la confirmación. "borrador" (solo admin, nunca un
pedido de cliente) y "cancelado" quedan afuera.
"""
import pytest

from routes.cliente_portal.core import _documentos_disponibles

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "estado",
    ["presupuesto", "confirmado", "retirado", "devuelto", "finalizado"],
)
def test_documentos_disponibles_desde_presupuesto(estado):
    docs = _documentos_disponibles(estado)
    assert docs == {"remito": True, "contrato": True, "albaran": True}


@pytest.mark.parametrize("estado", ["borrador", "cancelado", "", None])
def test_documentos_no_disponibles_borrador_cancelado_o_vacio(estado):
    docs = _documentos_disponibles(estado)
    assert docs == {"remito": False, "contrato": False, "albaran": False}


def test_documentos_disponibles_es_case_insensitive():
    assert _documentos_disponibles("Presupuesto") == {
        "remito": True,
        "contrato": True,
        "albaran": True,
    }
