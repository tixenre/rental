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
from starlette.requests import Request as StarletteRequest

import routes.alquileres.cotizacion as alq
from routes.alquileres import cotizar, CotizarRequest, CotizarItem

# slowapi valida con isinstance(request, StarletteRequest) → necesita una instancia real.
_TEST_SCOPE = {
    "type": "http",
    "method": "POST",
    "path": "/api/cotizar",
    "headers": [],
    "query_string": b"",
    "client": ("127.0.0.1", 1234),
    "app": type("_App", (), {"state": type("_State", (), {})()})(),
}


def FakeReq() -> StarletteRequest:
    return StarletteRequest(_TEST_SCOPE)


pytestmark = pytest.mark.unit


class FakeConn:
    """Conn fake: precios por equipo, fila de cliente y puntos de descuento
    por jornadas, resueltos según el SQL que llega."""

    def __init__(self, precios, perfil=None, descuento=0, descuentos_jornada=None,
                 perfiles_por_id=None):
        self.precios = precios                       # {equipo_id: precio_jornada}
        self.perfil = perfil
        self.descuento = descuento
        self.descuentos_jornada = descuentos_jornada or []
        # {cliente_id: (perfil, descuento)} — para verificar QUÉ cliente se usó.
        self.perfiles_por_id = perfiles_por_id
        self._sql = ""
        self._params = ()
        self.closed = 0  # cuántas veces se devolvió la conexión al pool

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def close(self):
        self.closed += 1

    def execute(self, sql, params=()):
        self._sql = sql
        self._params = params
        return self

    def fetchone(self):
        if "FROM equipos" in self._sql:
            eid = self._params[0]
            if eid in self.precios:
                return {"precio_jornada": self.precios[eid], "tipo": "simple"}
            return None
        if "FROM clientes" in self._sql:
            if self.perfiles_por_id is not None:
                row = self.perfiles_por_id.get(self._params[0])
                return {"perfil_impuestos": row[0], "descuento": row[1]} if row else None
            return {"perfil_impuestos": self.perfil, "descuento": self.descuento}
        return None

    def fetchall(self):
        if "FROM descuentos_jornada" in self._sql:
            return [{"jornadas": j, "pct": p} for j, p in self.descuentos_jornada]
        # Batch query para equipos: SELECT id, precio_jornada, tipo FROM equipos WHERE id IN (...)
        if "FROM equipos" in self._sql and "IN" in self._sql:
            return [
                {"id": eid, "precio_jornada": precio, "tipo": "simple"}
                for eid, precio in self.precios.items()
                if eid in self._params
            ]
        return []


@pytest.fixture
def patch_db(monkeypatch):
    """Devuelve un setter que instala un FakeConn + sesión en el módulo.

    También deshabilita la inyección de headers de rate-limit: cotizar()
    devuelve un dict (no un starlette Response), y slowapi con headers_enabled
    falla al intentar inyectar en un dict. No afecta el comportamiento del
    endpoint — solo elimina la necesidad de un objeto Response real en tests.
    """
    import rate_limit
    monkeypatch.setattr(rate_limit.limiter, "_inject_headers", lambda *a, **kw: None)

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
        # Sin fechas y sin cliente → estimado de UNA jornada, sin IVA/descuento.
        patch_db(FakeConn(precios={7: 10000}), session=None)
        out = cotizar(_req([(7, 1)]), FakeReq())

        assert out["jornadas"] == 1
        assert out["bruto"] == 10000
        assert out["neto"] == 10000
        assert out["con_iva"] is False
        assert out["iva_monto"] == 0
        assert out["total_final"] == 10000
        assert out["subtotal_por_jornada"] == 10000
        assert out["descuento_origen"] == "ninguno"

    def test_sin_fechas_cliente_ri_sigue_siendo_estimado(self, patch_db):
        # Aunque haya cliente RI logueado, sin fechas NO se suma IVA (estimado).
        patch_db(
            FakeConn(precios={7: 10000}, perfil="responsable_inscripto", descuento=10),
            session={"role": "cliente", "cliente_id": 42},
        )
        out = cotizar(_req([(7, 1)]), FakeReq())

        assert out["jornadas"] == 1
        assert out["con_iva"] is False
        assert out["iva_monto"] == 0
        assert out["descuento_monto"] == 0
        assert out["total_final"] == 10000

    def test_con_fechas_siete_jornadas(self, patch_db):
        patch_db(FakeConn(precios={7: 10000}), session=None)
        out = cotizar(
            _req([(7, 1)], "2026-06-01T10:00:00", "2026-06-08T10:00:00"),
            FakeReq(),
        )

        assert out["jornadas"] == 7
        assert out["bruto"] == 70000
        assert out["total_final"] == 70000

    def test_varios_items(self, patch_db):
        patch_db(FakeConn(precios={1: 5000, 2: 3000}), session=None)
        out = cotizar(_req([(1, 2), (2, 1)]), FakeReq())

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
            FakeReq(),
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
        # Con fechas (1 jornada por ser mismo día +) → modo firme.
        out = cotizar(
            _req([(7, 1)], "2026-06-01T10:00:00", "2026-06-02T10:00:00"),
            FakeReq(),
        )

        # 10000 bruto - 10% = 9000 neto; IVA 21% = 1890; total 10890
        assert out["descuento_monto"] == 1000
        assert out["neto"] == 9000
        assert out["iva_monto"] == 1890
        assert out["total_final"] == 10890
        assert out["descuento_origen"] == "cliente"


class TestAdmin:
    """El builder admin cotiza para OTRO cliente vía `cliente_id`."""

    def test_admin_usa_cliente_id(self, patch_db, monkeypatch):
        monkeypatch.setattr(alq, "is_admin_email", lambda email: True)
        patch_db(
            FakeConn(precios={7: 10000}, perfil="responsable_inscripto"),
            session={"email": "admin@test.com"},  # sesión admin, sin cliente_id
        )
        data = CotizarRequest(
            items=[CotizarItem(equipo_id=7, cantidad=1)],
            fecha_desde="2026-06-01T10:00:00",
            fecha_hasta="2026-06-08T10:00:00",
            cliente_id=99,
        )
        out = cotizar(data, FakeReq())

        # Aplicó el perfil RI del cliente 99 → IVA sobre 70000.
        assert out["con_iva"] is True
        assert out["total_final"] == 84700

    def test_admin_override_descuento(self, patch_db, monkeypatch):
        # El admin edita el descuento en vivo → override sobre el del cliente.
        monkeypatch.setattr(alq, "is_admin_email", lambda email: True)
        patch_db(
            FakeConn(precios={7: 10000}, perfil="consumidor_final", descuento=0),
            session={"email": "admin@test.com"},
        )
        data = CotizarRequest(
            items=[CotizarItem(equipo_id=7, cantidad=1)],
            fecha_desde="2026-06-01T10:00:00",
            fecha_hasta="2026-06-08T10:00:00",
            cliente_id=99,
            descuento_pct=20,
        )
        out = cotizar(data, FakeReq())

        # 70000 - 20% = 56000 (cliente tenía 0% guardado; ganó el override).
        assert out["descuento_pct"] == 20.0
        assert out["descuento_monto"] == 14000
        assert out["neto"] == 56000

    def test_no_admin_ignora_descuento_override(self, patch_db, monkeypatch):
        monkeypatch.setattr(alq, "is_admin_email", lambda email: False)
        patch_db(
            FakeConn(precios={7: 10000}),
            session={"role": "cliente", "cliente_id": 42},
        )
        data = CotizarRequest(
            items=[CotizarItem(equipo_id=7, cantidad=1)],
            fecha_desde="2026-06-01T10:00:00",
            fecha_hasta="2026-06-08T10:00:00",
            descuento_pct=50,
        )
        out = cotizar(data, FakeReq())

        # Cliente no puede auto-aplicarse descuento → 0%.
        assert out["descuento_monto"] == 0
        assert out["neto"] == 70000

    def test_cliente_logueado_no_puede_cotizar_para_otro(self, patch_db, monkeypatch):
        # Seguridad: un cliente logueado que manda el cliente_id de OTRO no
        # cotiza con el perfil ajeno → se usa SIEMPRE el del logueado.
        monkeypatch.setattr(alq, "is_admin_email", lambda email: False)
        patch_db(
            FakeConn(
                precios={7: 10000},
                perfiles_por_id={
                    42: ("consumidor_final", 0),       # el logueado
                    99: ("responsable_inscripto", 0),  # otro (RI)
                },
            ),
            session={"role": "cliente", "cliente_id": 42},
        )
        data = CotizarRequest(
            items=[CotizarItem(equipo_id=7, cantidad=1)],
            fecha_desde="2026-06-01T10:00:00",
            fecha_hasta="2026-06-08T10:00:00",
            cliente_id=99,  # intenta cotizar como el cliente 99 (RI)
        )
        out = cotizar(data, FakeReq())

        # Usó el perfil del 42 (consumidor_final) → sin IVA. Ignoró el 99.
        assert out["con_iva"] is False
        assert out["total_final"] == 70000

    def test_no_admin_ignora_cliente_id(self, patch_db, monkeypatch):
        # Sesión NO admin no puede cotizar para terceros → sin perfil aplicado.
        monkeypatch.setattr(alq, "is_admin_email", lambda email: False)
        patch_db(
            FakeConn(precios={7: 10000}, perfil="responsable_inscripto"),
            session={"email": "rando@test.com"},
        )
        data = CotizarRequest(
            items=[CotizarItem(equipo_id=7, cantidad=1)],
            fecha_desde="2026-06-01T10:00:00",
            fecha_hasta="2026-06-08T10:00:00",
            cliente_id=99,
        )
        out = cotizar(data, FakeReq())

        assert out["con_iva"] is False
        assert out["total_final"] == 70000


class TestPreciosDesdeBackend:
    """El precio lo pone el backend (de equipos), nunca el front."""

    def test_equipo_inexistente_se_ignora(self, patch_db):
        # equipo 99 no está en precios → se excluye (best-effort).
        patch_db(FakeConn(precios={7: 10000}), session=None)
        out = cotizar(_req([(7, 1), (99, 5)]), FakeReq())

        assert out["bruto"] == 10000  # solo el 7, el 99 ignorado

    def test_cantidad_no_positiva_se_ignora(self, patch_db):
        patch_db(FakeConn(precios={7: 10000}), session=None)
        out = cotizar(_req([(7, 0), (7, -3)]), FakeReq())

        assert out["bruto"] == 0
        assert out["total_final"] == 0

    def test_carrito_vacio(self, patch_db):
        patch_db(FakeConn(precios={}), session=None)
        out = cotizar(_req([]), FakeReq())

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
            FakeReq(),
        )

        # 70000 - 10% = 63000
        assert out["descuento_pct"] == 10.0
        assert out["descuento_monto"] == 7000
        assert out["neto"] == 63000


class TestConexion:
    """El handler debe devolver SIEMPRE la conexión al pool (close()).

    Regresión: la primera versión hacía `conn = get_db()` sin cerrarla nunca.
    Como `get_db()` toma del ThreadedConnectionPool (maxconn=10) y el pool
    retiene la referencia en `_used`, cada cotización filtraba una conexión de
    forma permanente → tras ~10 llamadas el pool se agotaba y el endpoint colgaba
    en producción. El fix envolvió el cuerpo en try/finally con `conn.close()`.
    """

    def test_devuelve_conexion_al_pool(self, patch_db):
        conn = FakeConn(precios={7: 10000})
        patch_db(conn, session=None)
        cotizar(_req([(7, 1)]), FakeReq())
        assert conn.closed == 1, "cotizar debe cerrar (devolver) la conexión exactamente una vez"

    def test_devuelve_conexion_aunque_falle(self, patch_db):
        # Si algo explota a mitad, la conexión igual se devuelve (finally).
        conn = FakeConn(precios={7: 10000})
        patch_db(conn, session=None)
        # Forzamos un fallo dentro del handler: items None rompe la iteración.
        bad = CotizarRequest.model_construct(items=None, fecha_desde=None, fecha_hasta=None)
        with pytest.raises(Exception):
            cotizar(bad, FakeReq())
        assert conn.closed == 1, "aún ante error, cotizar debe devolver la conexión"


class TestLineasPorEquipo:
    """Desglose POR LÍNEA (`lineas`) — el front lo MUESTRA, no lo calcula (FASE 3).

    Cada línea trae `subtotal_por_jornada` (el "$X/día" del ítem), y `bruto`/`neto`
    del período. Así el caján/teasers renderizan números del backend en vez de
    multiplicar `precio × cantidad × jornadas × (1-desc)` a mano.
    """

    def test_sin_fechas_subtotal_por_jornada_por_linea(self, patch_db):
        patch_db(FakeConn(precios={7: 10000, 9: 5000}), session=None)
        out = cotizar(_req([(7, 2), (9, 1)]), FakeReq())

        lineas = {l["equipo_id"]: l for l in out["lineas"]}
        # 7: 10000 × 2 = 20000/jornada; sin fechas (1 jornada, sin desc) → bruto=neto=20000.
        assert lineas[7]["subtotal_por_jornada"] == 20000
        assert lineas[7]["bruto"] == 20000
        assert lineas[7]["neto"] == 20000
        assert lineas[7]["cantidad"] == 2
        assert lineas[9]["subtotal_por_jornada"] == 5000
        # La suma de subtotales por jornada coincide con el agregado top-level.
        assert sum(l["subtotal_por_jornada"] for l in out["lineas"]) == out["subtotal_por_jornada"]

    def test_con_fechas_y_descuento_neto_por_linea(self, patch_db):
        # Cliente con 10% de descuento, 7 jornadas.
        patch_db(
            FakeConn(precios={7: 10000}, descuento=10),
            session={"role": "cliente", "cliente_id": 42},
        )
        out = cotizar(
            _req([(7, 1)], "2026-06-01T10:00:00", "2026-06-08T10:00:00"),
            FakeReq(),
        )
        linea = out["lineas"][0]
        # bruto = 10000 × 1 × 7 = 70000; neto = 70000 − 10% = 63000.
        assert linea["bruto"] == 70000
        assert linea["neto"] == 63000
        assert out["descuento_pct"] == 10
