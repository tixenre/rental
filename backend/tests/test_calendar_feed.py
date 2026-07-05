"""Tests del endpoint público del feed iCal (`routes/calendar.py`).

Patrón FakeConn + monkeypatch de `get_db` (como `test_email_service.py`). El
filtrado real de estados ocurre en SQL; acá verificamos el contrato del endpoint
(token, headers, contenido) y que la query pida SOLO los estados confirmados.
"""
import pytest
from starlette.requests import Request as StarletteRequest

from routes import calendar as cal_mod

pytestmark = pytest.mark.unit


# slowapi valida con isinstance(request, StarletteRequest) → necesita una
# instancia real (mismo patrón que test_cotizar_endpoint).
_SCOPE = {
    "type": "http",
    "method": "GET",
    "path": "/calendar/feed.ics",
    "headers": [],
    "query_string": b"",
    "client": ("127.0.0.1", 1234),
    "app": type("_App", (), {"state": type("_State", (), {})()})(),
}


def _req() -> StarletteRequest:
    return StarletteRequest(_SCOPE)


@pytest.fixture(autouse=True)
def _no_ratelimit_headers(monkeypatch):
    # feed_ical devuelve un Response, pero homogeneizamos con el resto de la
    # suite: el rate-limit sigue activo, solo no inyecta headers en el test.
    import rate_limit

    monkeypatch.setattr(rate_limit.limiter, "_inject_headers", lambda *a, **kw: None)


class FakeRow(dict):
    pass


class FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeConn:
    def __init__(self, token, reservas=(), items=()):
        self.token = token
        self.reservas = reservas
        self.items = items
        self.reservas_params = None
        self.closed = False

    def execute(self, sql, params=()):
        s = " ".join(sql.split()).upper()
        if "FROM APP_SETTINGS" in s:
            return FakeCursor([FakeRow(value=self.token)] if self.token is not None else [])
        if "FROM ALQUILERES" in s:
            self.reservas_params = params
            return FakeCursor(self.reservas)
        if "FROM ALQUILER_ITEMS" in s:
            return FakeCursor(self.items)
        return FakeCursor([])

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def close(self):
        self.closed = True


def _reserva(**over):
    base = {
        "id": 1, "numero_pedido": 50, "cliente_nombre": "Juan",
        "estado": "confirmado", "tipo": "diaria",
        "fecha_desde": "2026-06-10T00:00:00", "fecha_hasta": "2026-06-12T00:00:00",
    }
    base.update(over)
    return FakeRow(**base)


def _patch_db(monkeypatch, conn):
    monkeypatch.setattr("routes.calendar.get_db", lambda: conn)


# ── Token ─────────────────────────────────────────────────────────────────────

class TestToken:
    def test_token_correcto_devuelve_200_con_evento(self, monkeypatch):
        conn = FakeConn(token="secreto", reservas=[_reserva()])
        _patch_db(monkeypatch, conn)
        resp = cal_mod.feed_ical(_req(), token="secreto")
        assert resp.status_code == 200
        body = resp.body.decode("utf-8")
        assert "BEGIN:VCALENDAR" in body
        assert "UID:alquiler-1@rambla.house" in body
        assert "Pedido #50" in body
        assert conn.closed

    def test_token_incorrecto_es_404(self, monkeypatch):
        conn = FakeConn(token="secreto", reservas=[_reserva()])
        _patch_db(monkeypatch, conn)
        resp = cal_mod.feed_ical(_req(), token="otro")
        assert resp.status_code == 404

    def test_token_vacio_es_404(self, monkeypatch):
        conn = FakeConn(token="secreto")
        _patch_db(monkeypatch, conn)
        assert cal_mod.feed_ical(_req(), token="").status_code == 404

    def test_sin_token_configurado_es_404(self, monkeypatch):
        # app_settings con value '' → feed deshabilitado.
        conn = FakeConn(token="")
        _patch_db(monkeypatch, conn)
        assert cal_mod.feed_ical(_req(), token="cualquiera").status_code == 404


# ── Contenido / contrato ──────────────────────────────────────────────────────

class TestContenido:
    def test_headers_de_calendario(self, monkeypatch):
        conn = FakeConn(token="t", reservas=[_reserva()])
        _patch_db(monkeypatch, conn)
        resp = cal_mod.feed_ical(_req(), token="t")
        assert resp.media_type == "text/calendar; charset=utf-8"
        assert "max-age" in resp.headers.get("Cache-Control", "")

    def test_query_pide_solo_estados_confirmados(self, monkeypatch):
        conn = FakeConn(token="t", reservas=[_reserva()])
        _patch_db(monkeypatch, conn)
        cal_mod.feed_ical(_req(), token="t")
        estados_en_query = [p for p in conn.reservas_params if isinstance(p, str)]
        assert "presupuesto" not in estados_en_query
        assert "cancelado" not in estados_en_query
        assert "confirmado" in estados_en_query

    def test_evento_incluye_equipos(self, monkeypatch):
        conn = FakeConn(
            token="t", reservas=[_reserva()],
            items=[FakeRow(pedido_id=1, nombre="FX3", marca="Sony", cantidad=2)],
        )
        _patch_db(monkeypatch, conn)
        body = cal_mod.feed_ical(_req(), token="t").body.decode("utf-8")
        assert "2× Sony FX3" in body

    def test_feed_no_lleva_recordatorios(self, monkeypatch):
        # Los clientes ignoran VALARM de feeds suscritos → no los incluimos.
        conn = FakeConn(token="t", reservas=[_reserva()])
        _patch_db(monkeypatch, conn)
        body = cal_mod.feed_ical(_req(), token="t").body.decode("utf-8")
        assert "BEGIN:VALARM" not in body

    def test_db_caida_devuelve_calendario_vacio_no_500(self, monkeypatch):
        def boom():
            raise RuntimeError("db down")
        monkeypatch.setattr("routes.calendar.get_db", boom)
        resp = cal_mod.feed_ical(_req(), token="t")
        assert resp.status_code == 200
        body = resp.body.decode("utf-8")
        assert "BEGIN:VCALENDAR" in body
        assert "BEGIN:VEVENT" not in body
