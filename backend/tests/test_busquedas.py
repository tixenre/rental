"""Tests de routes/busquedas.py — registro de búsquedas del catálogo.

Cubre:
- `normalizar_busqueda`: minúsculas, sin acentos, espacios colapsados, y el
  descarte de términos demasiado cortos.
- `log_search`: ignora términos cortos (no toca la BD) y guarda el raw + norm
  cuando el término es útil.
"""

import pytest

pytestmark = pytest.mark.unit


class _FakeConn:
    def __init__(self):
        self.inserts = []
        self.committed = False
        self.closed = False

    def execute(self, query, params=None):
        self.inserts.append((query, params))

        class _Result:
            def fetchall(self_inner):
                return []

        return _Result()

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


# ── normalizar_busqueda ──────────────────────────────────────────────────────


def test_normaliza_minusculas_y_acentos():
    from routes.busquedas import normalizar_busqueda

    assert normalizar_busqueda("Cámara") == "camara"
    assert normalizar_busqueda("SONY") == "sony"
    assert normalizar_busqueda("  Trípode   grande  ") == "tripode grande"


def test_normaliza_agrupa_variantes():
    from routes.busquedas import normalizar_busqueda

    # Todas las variantes de acento/caja colapsan al mismo término.
    variantes = ["Cámara", "camara", "CAMARA", "cámara "]
    assert len({normalizar_busqueda(v) for v in variantes}) == 1


def test_normaliza_descarta_cortos():
    from routes.busquedas import normalizar_busqueda

    assert normalizar_busqueda("") is None
    assert normalizar_busqueda("a") is None
    assert normalizar_busqueda("   ") is None


# ── log_search ───────────────────────────────────────────────────────────────


# El handler está envuelto por @limiter.limit (slowapi); para testear la lógica
# pura sin el rate-limiter, usamos la función original vía __wrapped__.


def test_log_search_ignora_termino_corto(monkeypatch):
    import routes.busquedas as mod
    from routes.busquedas import SearchLogBody

    fake = _FakeConn()
    monkeypatch.setattr(mod, "get_db", lambda: fake)

    res = mod.log_search.__wrapped__(SearchLogBody(query="a", result_count=5), request=None)
    assert res == {"ok": True, "logged": False}
    # No debe tocar la BD para un término inútil.
    assert fake.inserts == []


def test_log_search_guarda_raw_y_norm(monkeypatch):
    import routes.busquedas as mod
    from routes.busquedas import SearchLogBody

    fake = _FakeConn()
    monkeypatch.setattr(mod, "get_db", lambda: fake)

    res = mod.log_search.__wrapped__(
        SearchLogBody(query="  Cámara Sony ", result_count=3), request=None
    )
    assert res == {"ok": True, "logged": True}
    assert fake.committed is True
    assert len(fake.inserts) == 1
    _, params = fake.inserts[0]
    # Guarda el crudo (trim) y la versión normalizada, con el conteo.
    assert params == ("Cámara Sony", "camara sony", 3)
