"""Candado (F5): el precio por jornada EFECTIVO se resuelve en UN solo lugar
(`services.precios.precio_jornada_efectivo`) para los 3 caminos que persisten plata —
cotizar, crear pedido del cliente, modificar pedido del cliente— de modo que un COMBO
cotice y se cobre igual (cierra el drift cotizado≠cobrado de #635).

Dos blindajes, ambos corren en el CI normal (sin Postgres):

1. **Resolutor (unit):** con un `conn` falso + `precio_combo` monkeypatcheado, verifica
   la semántica: combo → deriva de componentes, kit/simple → su precio propio,
   inexistente → None, precio nulo → 0.
2. **Source-scan (candado):** los 3 consumidores llaman `precio_jornada_efectivo` y
   NINGUNO inlinea `precio_combo(` ni el `SELECT ... tipo FROM equipos` de la rama de
   combo → no pueden reintroducir su propia resolución (que es como nacía el drift).
   Espeja `test_carrito_normalizar_safety.py` / `test_contenido_sql_safety.py`.
"""
import inspect

import pytest

import services.precios as precios
from routes.alquileres import cotizacion as ruta_cotizar
from routes.cliente_portal import pedidos as ruta_crear
from routes.cliente_portal import solicitudes as ruta_modificar

pytestmark = pytest.mark.unit


# ── 1 · Resolutor (unit, sin DB) ──────────────────────────────────────────────


class _FakeCursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConn:
    """Responde el único SELECT de `precio_jornada_efectivo` con la fila dada."""

    def __init__(self, row):
        self._row = row

    def execute(self, _sql, _params=None):
        return _FakeCursor(self._row)


def test_combo_deriva_de_componentes(monkeypatch):
    monkeypatch.setattr(precios, "precio_combo", lambda conn, eid: 777)
    conn = _FakeConn({"precio_jornada": 100, "tipo": "combo"})
    assert precios.precio_jornada_efectivo(conn, 5) == 777


def test_simple_usa_su_precio_propio(monkeypatch):
    # precio_combo NO debe llamarse para un equipo que no es combo.
    monkeypatch.setattr(
        precios, "precio_combo",
        lambda *a: pytest.fail("precio_combo no debe llamarse para un equipo simple"),
    )
    conn = _FakeConn({"precio_jornada": 100, "tipo": "simple"})
    assert precios.precio_jornada_efectivo(conn, 5) == 100


def test_inexistente_es_none():
    assert precios.precio_jornada_efectivo(_FakeConn(None), 5) is None


def test_precio_nulo_es_cero():
    conn = _FakeConn({"precio_jornada": None, "tipo": "simple"})
    assert precios.precio_jornada_efectivo(conn, 5) == 0


# ── 2 · Source-scan (candado: una sola fuente) ────────────────────────────────

# Los 3 caminos que ponen el precio que se PERSISTE. Cada uno mantiene su propio gate
# de seguridad, pero la resolución del precio efectivo delega en la fuente única.
_CONSUMIDORES = [ruta_cotizar, ruta_crear, ruta_modificar]


def _src(mod) -> str:
    return inspect.getsource(mod)


@pytest.mark.parametrize("mod", _CONSUMIDORES, ids=lambda m: m.__name__)
def test_consumidor_usa_el_resolutor_unico(mod):
    assert "precio_jornada_efectivo" in _src(mod), (
        f"{mod.__name__} debe resolver el precio por jornada vía "
        f"services.precios.precio_jornada_efectivo (fuente única)."
    )


@pytest.mark.parametrize("mod", _CONSUMIDORES, ids=lambda m: m.__name__)
def test_consumidor_no_inlinea_la_resolucion_de_combo(mod):
    src = _src(mod)
    assert "precio_combo(" not in src, (
        f"{mod.__name__} inlinea precio_combo() — debe delegar en "
        f"precio_jornada_efectivo para no reintroducir el drift de combos."
    )
    assert "tipo FROM equipos" not in src and "tipo from equipos" not in src.lower(), (
        f"{mod.__name__} arma inline el SELECT de la rama de combo (precio_jornada + "
        f"tipo) — debe delegar en precio_jornada_efectivo."
    )


def test_la_fuente_unica_si_resuelve_el_combo():
    """Sanity inverso: el resolutor único SÍ contiene la rama de combo."""
    src = inspect.getsource(precios.precio_jornada_efectivo)
    assert "precio_combo(" in src and 'tipo' in src, (
        "precio_jornada_efectivo debería ser el único lugar que resuelve combo vs. "
        "precio propio."
    )
