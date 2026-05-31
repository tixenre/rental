"""A2 #635 — validación del modelo KitItem (componente de kit/combo).

Bug que cierra: `descuento_pct=None` iba a `kit_componentes.descuento_pct` (NOT NULL)
→ IntegrityError al agregar un componente sin descuento (el caso por default). Fix:
default 0.0 (nunca None) + validación de rango (descuento 0..100, cantidad ≥1).
"""
import pytest
from pydantic import ValidationError

from routes.equipos import KitItem

pytestmark = pytest.mark.unit


def test_descuento_default_cero_no_none():
    # Sin descuento → 0.0, NO None (evita el IntegrityError en la columna NOT NULL).
    item = KitItem(componente_id=5)
    assert item.descuento_pct == 0.0
    assert item.cantidad == 1
    assert item.esencial is True


def test_descuento_fuera_de_rango_rechazado():
    with pytest.raises(ValidationError):
        KitItem(componente_id=5, descuento_pct=150)
    with pytest.raises(ValidationError):
        KitItem(componente_id=5, descuento_pct=-1)


def test_cantidad_menor_a_uno_rechazada():
    with pytest.raises(ValidationError):
        KitItem(componente_id=5, cantidad=0)


def test_valores_validos_ok():
    item = KitItem(componente_id=5, cantidad=2, descuento_pct=70, esencial=False)
    assert item.descuento_pct == 70
    assert item.cantidad == 2
    assert item.esencial is False
