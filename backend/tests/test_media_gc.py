"""Tests del GC de media (F0d): reconcile_media + rederive_variants.

Usa DB y R2 completamente falsos — sin Postgres ni R2 real.
"""
import pytest

pytestmark = pytest.mark.unit

# ── Fake DB ───────────────────────────────────────────────────────────────────

class _FakeRow(dict):
    pass


def _row(**kw):
    return _FakeRow(kw)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = [_row(**r) if isinstance(r, dict) else r for r in rows]

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    """Simula la DB con dos assets: 1 referenciado, 1 huérfano."""

    def __init__(self):
        self.deleted_ids: list[int] = []
        # asset 1: referenciado por equipo_fotos
        # asset 2: huérfano
        self._equipo_fotos = {1}  # media_ids referenciados por equipo_fotos

    def execute(self, sql: str, params=()):
        sql_up = sql.strip().upper()

        if "NOT EXISTS" in sql_up and "MEDIA_ASSETS" in sql_up:
            # Consulta de huérfanos: asset 2 es huérfano
            return _FakeCursor([_row(id=2)])

        if "SELECT ORIGINAL_KEY FROM MEDIA_ASSETS" in sql_up:
            asset_id = params[0] if params else None
            if asset_id == 2:
                return _FakeCursor([_row(original_key="media/equipo/2/original.jpg")])
            return _FakeCursor([])

        if "SELECT ORIGINAL_KEY, ORIGINAL_CT FROM MEDIA_ASSETS" in sql_up:
            return _FakeCursor([_row(original_key="media/equipo/1/original.jpg", original_ct="image/jpeg")])

        if "SELECT KIND FROM MEDIA_ASSETS" in sql_up:
            return _FakeCursor([_row(kind="equipo")])

        if "SELECT KEY FROM MEDIA_VARIANTS" in sql_up:
            return _FakeCursor([_row(key="media/equipo/2/display.webp")])

        if "DELETE FROM MEDIA_ASSETS" in sql_up:
            asset_id = params[0] if params else None
            self.deleted_ids.append(asset_id)
            return _FakeCursor([])

        if "SELECT" in sql_up and "MEDIA_VARIANTS" in sql_up:
            if "ORIGINAL_KEY" not in sql_up:
                return _FakeCursor([_row(key="media/equipo/2/display.webp")])

        return _FakeCursor([])

    def __enter__(self): return self
    def __exit__(self, *_): pass


# ── Fake storage ──────────────────────────────────────────────────────────────

class _FakeStorage:
    def __init__(self):
        self.deleted: list[str] = []
        self.puts: list[str] = []

    def delete_object(self, key: str, *, private: bool = False) -> bool:
        self.deleted.append(key)
        return True

    def get_original(self, key: str) -> bytes:
        from io import BytesIO
        from PIL import Image
        buf = BytesIO()
        Image.new("RGB", (100, 56)).save(buf, format="JPEG")
        return buf.getvalue()

    def put(self, key: str, content: bytes, ct: str) -> str:
        self.puts.append(key)
        return f"https://cdn.example.com/{key}"


# ── Tests: reconcile_media ────────────────────────────────────────────────────

class TestReconcileMedia:
    def test_detecta_huerfanos(self, monkeypatch):
        from services.media import gc as gc_mod
        fake_storage = _FakeStorage()
        monkeypatch.setattr("services.media.storage", fake_storage)

        conn = _FakeConn()
        result = gc_mod.reconcile_media(conn, dry_run=False)

        assert result.orphans_found == 1
        assert result.orphans_purged == 1
        assert 2 in conn.deleted_ids

    def test_dry_run_no_borra(self, monkeypatch):
        from services.media import gc as gc_mod
        fake_storage = _FakeStorage()
        monkeypatch.setattr("services.media.storage", fake_storage)

        conn = _FakeConn()
        result = gc_mod.reconcile_media(conn, dry_run=True)

        assert result.dry_run is True
        assert result.orphans_found == 1
        assert result.orphans_purged == 0
        assert conn.deleted_ids == []
        assert fake_storage.deleted == []

    def test_sin_huerfanos_no_hace_nada(self, monkeypatch):
        from services.media import gc as gc_mod

        class _NoOrphansConn(_FakeConn):
            def execute(self, sql, params=()):
                if "NOT EXISTS" in sql.upper() and "MEDIA_ASSETS" in sql.upper():
                    return _FakeCursor([])  # sin huérfanos
                return super().execute(sql, params)

        fake_storage = _FakeStorage()
        monkeypatch.setattr("services.media.storage", fake_storage)

        result = gc_mod.reconcile_media(_NoOrphansConn())
        assert result.orphans_found == 0
        assert result.orphans_purged == 0
        assert fake_storage.deleted == []

    def test_result_to_dict(self, monkeypatch):
        from services.media import gc as gc_mod
        monkeypatch.setattr("services.media.storage", _FakeStorage())
        result = gc_mod.reconcile_media(_FakeConn(), dry_run=True)
        d = result.to_dict()
        assert "orphans_found" in d
        assert "dry_run" in d
        assert d["dry_run"] is True


# ── Tests: _find_orphan_ids ───────────────────────────────────────────────────

class TestFindOrphanIds:
    def test_filtra_por_kind(self, monkeypatch):
        from services.media.gc import _find_orphan_ids

        class _KindConn:
            def execute(self, sql, params=()):
                # Verificar que se filtra por kind
                assert params and params[-1] == "equipo"
                return _FakeCursor([_row(id=5)])

        ids = _find_orphan_ids(_KindConn(), kind="equipo")
        assert ids == [5]

    def test_sin_kind_no_filtra(self):
        from services.media.gc import _find_orphan_ids

        class _AllKindsConn:
            def execute(self, sql, params=()):
                assert params == ()  # sin kind param
                return _FakeCursor([_row(id=3), _row(id=7)])

        ids = _find_orphan_ids(_AllKindsConn())
        assert ids == [3, 7]
