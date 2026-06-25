"""Tests del endpoint GET /api/media/entity/{kind}/{entity_id}.

Cubre: variantes desde media_variants, fallback legacy (sin media_id),
kind inválido (400), kind no soportado (404).
"""
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


@pytest.fixture
def client(monkeypatch):
    """TestClient con get_db parchado — sin Postgres real."""
    from fastapi import FastAPI
    from routes.media_api import router

    _app = FastAPI()
    _app.include_router(router, prefix="/api")

    monkeypatch.setattr("routes.media_api.get_db", _fake_get_db)

    return TestClient(_app)


# ── Fake DB ───────────────────────────────────────────────────────────────────

class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


def _row(d: dict):
    """Simula una fila tipo psycopg2 RealDictRow (acceso por key)."""
    class _R(dict):
        pass
    r = _R(d)
    return r


_FOTOS_EQUIPO = [
    _row({"id": 1, "url": "https://cdn/eq1/display.webp", "media_id": 10, "orden": 0, "es_principal": True}),
    _row({"id": 2, "url": "https://cdn/eq1/display_old.webp", "media_id": None, "orden": 1, "es_principal": False}),
]

_VARIANTS_10 = [
    _row({"name": "display",       "url": "https://cdn/display.webp",    "width": 1200, "height": 1200, "content_type": "image/webp"}),
    _row({"name": "display-sm",    "url": "https://cdn/display-sm.webp", "width": 600,  "height": 600,  "content_type": "image/webp"}),
    _row({"name": "display-thumb", "url": "https://cdn/thumb.webp",      "width": 160,  "height": 160,  "content_type": "image/webp"}),
]


class _FakeConn:
    def execute(self, sql, params=()):
        sql_up = sql.strip().upper()
        if "EQUIPO_FOTOS" in sql_up and "EQUIPO_ID" in sql_up:
            return _FakeCursor(_FOTOS_EQUIPO)
        if "ESTUDIO_FOTOS" in sql_up:
            return _FakeCursor([])
        if "MEDIA_VARIANTS" in sql_up:
            asset_id = params[0] if params else None
            if asset_id == 10:
                return _FakeCursor(_VARIANTS_10)
            return _FakeCursor([])
        return _FakeCursor([])

    def __enter__(self): return self
    def __exit__(self, *_): pass


from contextlib import contextmanager

@contextmanager
def _fake_get_db():
    yield _FakeConn()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestGetEntityMedia:
    def test_equipo_con_variantes(self, client):
        r = client.get("/api/media/entity/equipo/42")
        assert r.status_code == 200
        data = r.json()
        assert "assets" in data
        assets = data["assets"]
        assert len(assets) == 2

        # Primer asset: tiene media_id → variantes reales
        a0 = assets[0]
        assert a0["id"] == 1
        assert a0["es_principal"] is True
        assert a0["media_id"] == 10
        assert len(a0["variants"]) == 3
        names = {v["name"] for v in a0["variants"]}
        assert names == {"display", "display-sm", "display-thumb"}
        display = next(v for v in a0["variants"] if v["name"] == "display")
        assert display["width"] == 1200
        assert display["height"] == 1200

    def test_foto_legacy_sin_media_id(self, client):
        """Foto sin media_id → variante sintética con la url directa."""
        r = client.get("/api/media/entity/equipo/42")
        assert r.status_code == 200
        assets = r.json()["assets"]

        a1 = assets[1]
        assert a1["media_id"] is None
        assert len(a1["variants"]) == 1
        v = a1["variants"][0]
        assert v["name"] == "display"
        assert v["url"] == "https://cdn/eq1/display_old.webp"
        assert v["width"] == 0  # sin datos de dimensión

    def test_kind_invalido_400(self, client):
        r = client.get("/api/media/entity/../admin/1")
        # path traversal → 404 o 400
        assert r.status_code in (400, 404, 422)

    def test_kind_no_soportado_404(self, client):
        r = client.get("/api/media/entity/workshop/1")
        assert r.status_code == 404
        assert "no soportado" in r.json()["detail"]

    def test_estudio_sin_fotos_devuelve_lista_vacia(self, client):
        r = client.get("/api/media/entity/estudio/1")
        assert r.status_code == 200
        assert r.json()["assets"] == []
