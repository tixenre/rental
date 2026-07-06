"""Guard (F3): los consumidores de DISPLAY de "qué incluye un kit/combo" derivan
de la puerta única `services.contenido`, no de SQL inline contra `kit_componentes`.

Espeja el patrón de `test_reservas_sql_safety.py` (inspect.getsource + assert sobre
el texto). Blinda la migración F2: si alguien re-inlinea una query de
`kit_componentes` en uno de los consumidores migrados, este test falla y obliga a
volver a la puerta.

Detecta el patrón SQL real (`FROM`/`JOIN kit_componentes`), no menciones en prosa
— así un comentario que nombre la tabla no genera falso positivo.

EXCEPCIÓN DOCUMENTADA (no migrada en F2, a propósito): `services/
pedidos_enriquecimiento.py::_batch_get_alquiler_items` devuelve `kc.*` crudo y
alimenta mails/cotización (superficie de plata); su consolidación es follow-up
con test dedicado. NO está en la lista de abajo, por eso no la marca.

`routes/alquileres/detalle.py::_get_alquiler_items` (movido de `core.py` en el
split #1254) migró a la puerta única — ver `_MIGRADAS` abajo.
"""
import inspect

import pytest

from database import equipos as db_equipos
from routes.alquileres import documentos as rutas_docs
from routes.alquileres import detalle as rutas_detalle
from routes.equipos import core as rutas_core
from routes.equipos import kit as rutas_kit

pytestmark = pytest.mark.unit

# Consumidores de DISPLAY ya migrados a la puerta única (F2): su código NO debe
# contener una query SQL contra kit_componentes — derivan de services.contenido.
_MIGRADAS = [
    db_equipos.attach_kit,
    rutas_kit.get_kit,
    rutas_core.get_equipo,
    rutas_docs._add_componentes,
    rutas_detalle._get_alquiler_items,
]


def _lee_kit_componentes_en_sql(func) -> bool:
    src = inspect.getsource(func).lower()
    return "from kit_componentes" in src or "join kit_componentes" in src


@pytest.mark.parametrize("func", _MIGRADAS, ids=lambda f: f.__name__)
def test_consumidor_display_no_inlinea_kit_componentes(func):
    assert not _lee_kit_componentes_en_sql(func), (
        f"{func.__name__} arma SQL inline contra kit_componentes para mostrar — "
        f"debe derivar de la puerta única services.contenido (contenido_de / "
        f"contenido_de_batch)."
    )


def test_la_puerta_si_es_la_que_lee_kit_componentes():
    """Sanity inverso: la puerta SÍ es la fuente que arma el SQL de kit_componentes."""
    from services.contenido import contenido

    assert "kit_componentes" in inspect.getsource(contenido), (
        "la puerta debería ser la única que arma el SQL de kit_componentes para display"
    )
