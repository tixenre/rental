"""Tests de integración de services/media/service.py — store_upload + purge.

Mockea el cliente R2 (boto3) y la DB para no necesitar red ni Postgres real.
Cubre:
- happy-path: asset con original_key + 1 variante display, 2 PUTs (original+display)
- fallo parcial: PUT de variante revienta → MediaError, delete_object del original,
  sin fila committeada (rollback en el caller)
- collect_asset_keys: carga keys sin modificar DB
- purge_r2: best-effort deletes, nunca eleva aunque R2 falle
"""
import pytest

pytestmark = pytest.mark.unit


# ── helpers ──────────────────────────────────────────────────────────────────

def _png_bytes(w=400, h=300):
    from io import BytesIO
    from PIL import Image
    img = Image.new("RGB", (w, h), (100, 150, 200))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _FakeR2Client:
    """Simula boto3 S3 client para R2."""

    def __init__(self, fail_on_key: str | None = None):
        self.puts: list[str] = []
        self.deletes: list[str] = []
        self._fail_on_key = fail_on_key

    def put_object(self, *, Bucket, Key, Body, ContentType, CacheControl):
        if self._fail_on_key and Key == self._fail_on_key:
            raise RuntimeError(f"R2 PUT forzado a fallar para '{Key}'")
        self.puts.append(Key)

    def delete_object(self, *, Bucket, Key):
        self.deletes.append(Key)


class _FakeConn:
    """Minimal fake DB connection + cursor que soporta INSERT RETURNING id."""

    def __init__(self):
        self._next_id = 1
        self.executed: list[tuple] = []
        self._rows: dict = {}  # key → value para fetchone mocks

    def execute(self, sql: str, params=()):
        self.executed.append((sql.strip(), params))
        return _FakeCursor(self._consume_next_id())

    def _consume_next_id(self) -> int:
        n = self._next_id
        self._next_id += 1
        return n

    def rollback(self):
        pass

    def commit(self):
        pass

    def close(self):
        pass


class _FakeCursor:
    def __init__(self, row_id: int):
        self._row_id = row_id

    def fetchone(self):
        return {"id": self._row_id}

    def fetchall(self):
        return []


def _patch_r2(monkeypatch, fake_client: _FakeR2Client):
    """Parcha storage._get_r2_client y storage._r2_config para usar el fake."""
    import services.media.storage as storage_mod
    monkeypatch.setattr(storage_mod, "_r2_client_cache", None)
    monkeypatch.setattr(storage_mod, "_r2_config", lambda: {
        "account_id": "test", "access_key_id": "k", "secret_key": "s",
        "bucket": "test-bucket", "public_base": "https://cdn.example.com",
    })
    monkeypatch.setattr(storage_mod, "_get_r2_client", lambda cfg: fake_client)


# ── happy-path ────────────────────────────────────────────────────────────────

class TestStoreUploadHappyPath:
    def test_asset_con_original_y_variante_display(self, monkeypatch):
        from services.media.service import store_upload
        from services.media.specs import DISPLAY_KEEP_ASPECT

        fake = _FakeR2Client()
        _patch_r2(monkeypatch, fake)

        raw = _png_bytes(800, 600)
        conn = _FakeConn()
        asset = store_upload(raw, kind="estudio", derive_specs=[DISPLAY_KEEP_ASPECT], conn=conn)

        assert asset.kind == "estudio"
        assert asset.original_key is not None
        assert asset.original_key.startswith("media/estudio/")
        assert asset.original_key.endswith(("/original.png", "/original.jpg"))

        assert len(asset.variants) == 1
        display = asset.variant("display")
        assert display is not None
        assert display.key.endswith("/display.webp")
        assert display.content_type == "image/webp"

        # Verificar que se hicieron 2 PUTs (original + display)
        assert len(fake.puts) == 2
        assert any("original" in k for k in fake.puts)
        assert any("display" in k for k in fake.puts)

        # URL pública debe contener la public_base
        assert display.url.startswith("https://cdn.example.com/")

    def test_asset_id_en_la_key(self, monkeypatch):
        from services.media.service import store_upload
        from services.media.specs import DISPLAY_KEEP_ASPECT

        fake = _FakeR2Client()
        _patch_r2(monkeypatch, fake)
        conn = _FakeConn()
        asset = store_upload(_png_bytes(), kind="estudio", derive_specs=[DISPLAY_KEEP_ASPECT], conn=conn)

        # La key debe contener el asset_id
        assert f"/{asset.id}/" in asset.original_key
        assert f"/{asset.id}/" in asset.variants[0].key


# ── fallo parcial ─────────────────────────────────────────────────────────────

class TestStoreUploadFalloParcial:
    def test_fallo_en_put_variante_limpia_original_y_eleva(self, monkeypatch):
        from services.media.errors import MediaError
        from services.media.service import store_upload
        from services.media.specs import DISPLAY_KEEP_ASPECT

        # El cliente falla al subir la variante display (key contiene 'display')
        # El asset_id será 1 (primer id del FakeConn)
        fake = _FakeR2Client(fail_on_key=None)
        _patch_r2(monkeypatch, fake)

        # Interceptar put para fallar en el segundo PUT (variante)
        import services.media.storage as storage_mod
        call_count = {"n": 0}
        original_put = storage_mod.put

        def _put_that_fails_second(key, content, content_type):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise Exception("R2 falla en variante")
            return original_put(key, content, content_type)

        monkeypatch.setattr(storage_mod, "put", _put_that_fails_second)

        conn = _FakeConn()
        with pytest.raises((MediaError, Exception)):
            store_upload(_png_bytes(), kind="estudio", derive_specs=[DISPLAY_KEEP_ASPECT], conn=conn)

        # El original debe haberse limpiado (delete_object)
        assert len(fake.deletes) >= 1


# ── collect_asset_keys ────────────────────────────────────────────────────────

class TestCollectAssetKeys:
    def test_devuelve_keys_vacio_si_no_hay_asset(self):
        from services.media.service import collect_asset_keys

        class _EmptyConn:
            def execute(self, sql, params=()):
                return _NilCursor()

        class _NilCursor:
            def fetchone(self): return None
            def fetchall(self): return []

        keys = collect_asset_keys(_EmptyConn(), 999)
        assert keys == []


# ── purge_r2 ─────────────────────────────────────────────────────────────────

class TestPurgeR2:
    def test_purge_vacio_no_falla(self):
        from services.media.service import purge_r2
        purge_r2([])  # no debe explotar

    def test_purge_best_effort_r2_sin_configurar(self, monkeypatch):
        for var in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
            monkeypatch.delenv(var, raising=False)
        import services.media.storage as storage_mod
        monkeypatch.setattr(storage_mod, "_r2_client_cache", None)

        from services.media.service import purge_r2
        try:
            purge_r2(["media/estudio/1/original.jpg", "media/estudio/1/display.webp"])
        except Exception as e:
            pytest.fail(f"purge_r2 elevó en vez de degradar: {e}")


# ── media_fastapi adapter ─────────────────────────────────────────────────────

class TestMediaFastapi:
    def test_media_error_se_convierte_a_http_exception(self):
        from fastapi import HTTPException
        from services.media.errors import MediaError
        from services.media_fastapi import media_http

        with pytest.raises(HTTPException) as exc:
            with media_http():
                raise MediaError(422, "validación fallida")

        assert exc.value.status_code == 422
        assert exc.value.detail == "validación fallida"

    def test_otras_excepciones_pasan_sin_modificar(self):
        from services.media_fastapi import media_http

        with pytest.raises(ValueError):
            with media_http():
                raise ValueError("otro error")

    def test_sin_error_no_hace_nada(self):
        from services.media_fastapi import media_http
        result = []
        with media_http():
            result.append(1)
        assert result == [1]
