"""Tests del endpoint de cotización canónica (`POST /api/cotizar`).

El endpoint es la fuente única del total del carrito: el front manda solo
`items` (equipo_id + cantidad) y fechas; el backend pone los precios (de
`equipos`), el perfil/descuento del cliente y devuelve el desglose de
`services.precios.calcular_total`. Reemplaza el cálculo duplicado del front
(`src/lib/cart-total.ts`). Ver #617.

Estilo unitario (sin TestClient): se llama a la función con un FakeConn y
`get_session` monkeypatcheado, como el resto de los tests del módulo.
"""

import pytest

import routes.alquileres as alq
from routes.alquileres import cotizar, CotizarRequest, CotizarItem


pytestmark = pytest.mark.unit


class FakeConn:
    """Conn fake: precios por equipo, fila de cliente y puntos de descuento
    por jornadas, resueltos según el SQL que llega."""

    def __init__(self, precios, perfil=None, descuento=0, descuentos_jornada=None):
        self.precios = precios                       # {equipo_id: precio_jornada}
        self.perfil = perfil
        self.descuento = descuento
        self.descuentos_jornada = descuentos_jornada or []
        self._sql = ""
        self._params = ()

    def execute(self, sql, params=()):
        self._sql = sql
        self._params = params
        return self

    def fetchone(self):
        if "FROM equipos" in self._sql:
            eid = self._params[0]
            if eid in self.precios:
                return {"precio_jornada": self.precios[eid]}
            return None
        if "FROM clientes" in self._sql:
            return {"perfil_impuestos": self.perfil, "descuento": self.descuento}
        return None

    def fetchall(self):
        if "FROM descuentos_jornada" in self._sql:
            return [{"jornadas": j, "pct": p} for j, p in self.descuentos_jornada]
        return []


@pytest.fixture
def patch_db(monkeypatch):
    """Devuelve un setter que instala un FakeConn + sesión en el módulo."""

    def _install(conn, session=None):
        monkeypatch.setattr(alq, "get_db", lambda: conn)
        monkeypatch.setattr(alq, "get_session", lambda request: session)

    return _install


def _req(items, fecha_desde=None, fecha_hasta=None):
    return CotizarRequest(
        items=[CotizarItem(equipo_id=e, cantidad=c) for e, c in items],
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )


class TestAnonimo:
    """Sin sesión → consumidor_final, sin descuento de cliente, sin IVA."""

    def test_sin_fechas_una_jornada(self, patch_db):
        patch_db(FakeConn(precios={7: 10000}), session=None)
        out = cotizar(_req([(7, 1)]), request=None)

        assert out["jornadas"] == 1
        assert out["bruto"] == 10000
        assert out["neto"] == 10000
        assert out["con_iva"] is False
        assert out["iva_monto"] == 0
        assert out["total_final"] == 10000

    def test_con_fechas_siete_jornadas(self, patch_db):
        patch_db(FakeConn(precios={7: 10000}), session=None)
        out = cotizar(
            _req([(7, 1)], "2026-06-01T10:00:00", "2026-06-08T10:00:00"),
            request=None,
        )

        assert out["jornadas"] == 7
        assert out["bruto"] == 70000
        assert out["total_final"] == 70000

    def test_varios_items(self, patch_db):
        patch_db(FakeConn(precios={1: 5000, 2: 3000}), session=None)
        out = cotizar(_req([(1, 2), (2, 1)]), request=None)

        # (5000×2 + 3000×1) × 1 jornada = 13000
        assert out["bruto"] == 13000
        assert out["total_final"] == 13000


class TestResponsableInscripto:
    """Cliente logueado RI → IVA 21% sobre el neto."""

    def test_iva_sobre_neto(self, patch_db):
        patch_db(
            FakeConn(precios={7: 10000}, perfil="responsable_inscripto"),
            session={"role": "cliente", "cliente_id": 42},
        )
        out = cotizar(
            _req([(7, 1)], "2026-06-01T10:00:00", "2026-06-08T10:00:00"),
            request=None,
        )

        # 70000 neto + 21% = 84700
        assert out["neto"] == 70000
        assert out["con_iva"] is True
        assert out["iva_pct"] == 21.0
        assert out["iva_monto"] == 14700
        assert out["total_final"] == 84700

    def test_descuento_cliente_y_iva(self, patch_db):
        patch_db(
            FakeConn(precios={7: 10000}, perfil="responsable_inscripto", descuento=10),
            session={"role": "cliente", "cliente_id": 42},
        )
        out = cotizar(_req([(7, 1)]), request=None)

        # 10000 bruto - 10% = 9000 neto; IVA 21% = 1890; total 10890
        assert out["descuento_monto"] == 1000
        assert out["neto"] == 9000
        assert out["iva_monto"] == 1890
        assert out["total_final"] == 10890


class TestPreciosDesdeBackend:
    """El precio lo pone el backend (de equipos), nunca el front."""

    def test_equipo_inexistente_se_ignora(self, patch_db):
        # equipo 99 no está en precios → se excluye (best-effort).
        patch_db(FakeConn(precios={7: 10000}), session=None)
        out = cotizar(_req([(7, 1), (99, 5)]), request=None)

        assert out["bruto"] == 10000  # solo el 7, el 99 ignorado

    def test_cantidad_no_positiva_se_ignora(self, patch_db):
        patch_db(FakeConn(precios={7: 10000}), session=None)
        out = cotizar(_req([(7, 0), (7, -3)]), request=None)

        assert out["bruto"] == 0
        assert out["total_final"] == 0

    def test_carrito_vacio(self, patch_db):
        patch_db(FakeConn(precios={}), session=None)
        out = cotizar(_req([]), request=None)

        assert out["bruto"] == 0
        assert out["total_final"] == 0


class TestDescuentoJornadas:
    def test_interpola_y_aplica(self, patch_db):
        # Puntos (1,0%) (7,10%): a 7 jornadas → 10%.
        patch_db(
            FakeConn(precios={7: 10000}, descuentos_jornada=[(1, 0), (7, 10)]),
            session=None,
        )
        out = cotizar(
            _req([(7, 1)], "2026-06-01T10:00:00", "2026-06-08T10:00:00"),
            request=None,
        )

        # 70000 - 10% = 63000
        assert out["descuento_pct"] == 10.0
        assert out["descuento_monto"] == 7000
        assert out["neto"] == 63000
