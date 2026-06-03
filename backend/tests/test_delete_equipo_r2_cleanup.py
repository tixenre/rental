"""Regresión: al borrar un equipo con HTML scrapeado en R2, el blob se borra.

Mockea _delete_from_r2 directamente para verificar que delete_equipo lo llama
con la key correcta cuando el equipo tiene html_source_url.
"""
import pytest

import routes.equipos as eq

pytestmark = pytest.mark.unit


class _FakeCursor:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConn:
    def __init__(self, row):
        self._row = row
        self.executed = []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        if sql.strip().upper().startswith("SELECT"):
            return _FakeCursor(self._row)
        return _FakeCursor(None)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def test_delete_equipo_borra_blob_r2(monkeypatch):
    """Con html_source_url presente, delete_equipo invoca _r2_config y
    client.delete_object con el bucket y la key derivada de la URL."""
    row = {"id": 7, "html_source_url": "https://cdn.example.com/equipos/7_cam/scrape.html"}
    conn = _FakeConn(row)
    monkeypatch.setattr(eq, "get_db", lambda: conn)

    cfg = {"bucket": "equipos-fotos", "public_base": "https://cdn.example.com"}

    class _FakeClient:
        def __init__(self):
            self.deleted = []
        def delete_object(self, Bucket, Key):
            self.deleted.append((Bucket, Key))

    fake_client = _FakeClient()
    monkeypatch.setattr(eq, "_r2_config", lambda: cfg)
    monkeypatch.setattr(eq, "_get_r2_client", lambda c: fake_client)

    eq.delete_equipo(7)

    assert fake_client.deleted == [("equipos-fotos", "equipos/7_cam/scrape.html")]


def test_delete_equipo_sin_html_no_toca_r2(monkeypatch):
    """Si el equipo no tiene html_source_url, no se llama a R2 en absoluto."""
    row = {"id": 8, "html_source_url": None}
    conn = _FakeConn(row)
    monkeypatch.setattr(eq, "get_db", lambda: conn)

    called = {"r2": False}

    def _boom(*a, **k):
        called["r2"] = True
        raise AssertionError("no debería tocar R2 sin html_source_url")

    monkeypatch.setattr(eq, "_get_r2_client", _boom)

    eq.delete_equipo(8)
    assert called["r2"] is False


def test_r2_helpers_importados():
    """Guard: los helpers de R2 que usa delete_equipo deben estar en el namespace."""
    assert hasattr(eq, "_get_r2_client"), "_get_r2_client debe estar importado en routes.equipos"
    assert hasattr(eq, "_r2_config")
