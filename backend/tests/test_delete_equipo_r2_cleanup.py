"""Regresión: al borrar un equipo con HTML scrapeado en R2, el blob se borra.

Verifica que `delete_equipo` llama a `_delete_from_r2` con la key derivada
de la URL (sin el prefijo público), usando `_r2_config` para resolver el
public_base. El cleanup es best-effort (envuelto en try/except).
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
    """Conn mínima: devuelve un equipo con html_source_url en el SELECT, y
    acepta el UPDATE/commit del soft-delete."""

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

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def close(self):
        pass


def test_delete_equipo_borra_blob_r2(monkeypatch):
    """Con html_source_url presente, delete_equipo llama a _delete_from_r2
    con la key derivada de la URL (sin el prefijo público)."""
    row = {"id": 7, "html_source_url": "https://cdn.example.com/equipos/7_cam/scrape.html"}
    conn = _FakeConn(row)
    monkeypatch.setattr(eq, "get_db", lambda: conn)

    cfg = {"bucket": "equipos-fotos", "public_base": "https://cdn.example.com"}
    monkeypatch.setattr(eq, "_r2_config", lambda: cfg)
    monkeypatch.setattr(eq, "require_admin", lambda request: {"email": "admin@test.com"})

    deleted_keys = []
    monkeypatch.setattr(eq, "_delete_from_r2", lambda key: deleted_keys.append(key) or True)

    eq.delete_equipo(7, request=None)

    assert deleted_keys == ["equipos/7_cam/scrape.html"]


def test_delete_equipo_sin_html_no_toca_r2(monkeypatch):
    """Si el equipo no tiene html_source_url, no se llama a _delete_from_r2."""
    row = {"id": 8, "html_source_url": None}
    conn = _FakeConn(row)
    monkeypatch.setattr(eq, "get_db", lambda: conn)
    monkeypatch.setattr(eq, "require_admin", lambda request: {"email": "admin@test.com"})

    called = {"r2": False}
    def _boom(key):
        called["r2"] = True
        raise AssertionError("no debería tocar R2 sin html_source_url")
    monkeypatch.setattr(eq, "_delete_from_r2", _boom)

    eq.delete_equipo(8, request=None)
    assert called["r2"] is False


def test_delete_from_r2_esta_importado():
    """Guard directo del bug: los símbolos que el cleanup usa deben estar
    resueltos en el namespace de routes.equipos (no NameError latente)."""
    assert hasattr(eq, "_delete_from_r2"), "_delete_from_r2 debe estar importado en routes.equipos"
    assert hasattr(eq, "_r2_config")
