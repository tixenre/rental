"""Candado (F3): los consumidores de la SELECCIÓN del carrito (compartir / listas)
derivan del normalizador único `services.carrito`, no de un normalizador propio.

Espeja el patrón de `test_contenido_sql_safety.py` (inspect.getsource + assert sobre
el texto). Blinda la migración F3: si alguien re-inlinea el dedup/clamp/filtro de la
selección —o el SQL `SELECT id FROM equipos WHERE id = ANY(...)`— en uno de los
consumidores migrados, este test falla y obliga a volver a la puerta única.

Detecta el patrón SQL real del filtro de equipos y un normalizador propio definido en
el módulo, no menciones en prosa — así un comentario no genera falso positivo.
"""
import inspect

import pytest

from routes import compartir as rutas_compartir
from routes.cliente_portal import listas as rutas_listas

pytestmark = pytest.mark.unit

# Consumidores migrados a la puerta única (F3): su código NO debe contener su propio
# normalizador ni el SQL del filtro de equipos — delegan en services.carrito.
_MIGRADOS = [rutas_compartir, rutas_listas]

# El SQL del filtro de equipos existentes que vivía duplicado en ambos normalizadores.
_SQL_FILTRO = "select id from equipos where id = any"


def _src(mod) -> str:
    return inspect.getsource(mod).lower()


@pytest.mark.parametrize("mod", _MIGRADOS, ids=lambda m: m.__name__)
def test_consumidor_no_define_normalizador_propio(mod):
    src = _src(mod)
    assert "def _normalizar_items" not in src, (
        f"{mod.__name__} define un normalizador propio (_normalizar_items) — "
        f"debe delegar en services.carrito.normalizar_seleccion."
    )


@pytest.mark.parametrize("mod", _MIGRADOS, ids=lambda m: m.__name__)
def test_consumidor_no_inlinea_el_sql_de_filtro(mod):
    src = _src(mod)
    assert _SQL_FILTRO not in src, (
        f"{mod.__name__} arma inline el SQL del filtro de equipos de la selección — "
        f"debe derivar de services.carrito.normalizar_seleccion."
    )


def test_la_puerta_si_es_la_que_normaliza():
    """Sanity inverso: el módulo único SÍ contiene el SQL del filtro de la selección."""
    from services.carrito import seleccion

    assert _SQL_FILTRO in inspect.getsource(seleccion).lower(), (
        "services.carrito.seleccion debería ser la única fuente del filtro de equipos "
        "de la selección (dedup/clamp/filtro)."
    )
