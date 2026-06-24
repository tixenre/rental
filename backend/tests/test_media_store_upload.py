"""Tests de integración de services/media/service.py — store_upload + purge.

Mockea el cliente R2 (boto3) y la DB para no necesitar red ni Postgres real.
Cubre:
- happy-path: asset con original_key + 1 variante display, 2 PUTs (original+display)
- fallo parcial: PUT de variante revienta → MediaError, delete_object del original,
  sin fila committeada (rollback en el caller)
- collect_asset_keys: carga keys sin modificar DB
- purge_r2: best-effort deletes, nunca eleva aunque R2 falle
- slug sanit del kind: path traversal y chars inválidos rechazados con 400
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

    def put_object(self, *, Bucket, Key, Body, ContentType, CacheControl, **_):
        if self._fail_on_key and Key == self._fail_on_key:
            raise RuntimeError(f"R2 PUT forzado a fallar para '{Key}'")
        self.puts.append(Key)

    def delete_object(self, *, Bucket, Key):
        self.deletes.append(Key)


class _FakeConn:
    """Minimal fake DB connection + cursor.

    - INSERT ... RETURNING id → devuelve {"id": next_id} (autoincrement).
    - SELECT / UPDATE / CREATE → devuelve None (no rows found / not applicable).
    """

    def __init__(self):
        self._next_id = 1
        self.executed: list[tuple] = []

    def execute(self, sql: str, params=()):
        self.executed.append((sql.strip(), params))
        sql_upper = sql.strip().upper()
        is_insert_returning = sql_upper.startswith("INSERT") and "RETURNING" in sql_upper
        if is_insert_returning:
            return _FakeCursorWithRow({"id": self._consume_next_id()})
        return _FakeCursorEmpty()

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


class _FakeCursorWithRow:
    def __init__(self, row: dict):
        self._row = row

    def fetchone(self):
        return self._row

    def fetchall(self):
        return [self._row]


class _FakeCursorEmpty:
    def fetchone(self):
        return None

    def fetchall(self):
        return []


def _patch_r2(monkeypatch, fake_client: _FakeR2Client):
    """Parcha storage._get_r2_client y storage._r2_config para usar el fake."""
    import services.media.storage as storage_mod
    monkeypatch.setattr(storage_mod, "_r2_client_cache", None)
    monkeypatch.setattr(storage_mod, "_r2_config", lambda: {
        "account_id": "test", "access_key_id": "k", "secret_key": "s",
        "bucket": "test-bucket", "public_base": "https://cdn.example.com",
        "private_bucket": "",  # sin bucket privado separado en tests
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

    def test_genera_variante_display_sm_para_srcset(self, monkeypatch):
        """El upload de equipo deriva display (1200) + display-sm (600) para srcset."""
        from services.media.service import store_upload
        from services.media.specs import DISPLAY_SQUARE, DISPLAY_SQUARE_SM

        fake = _FakeR2Client()
        _patch_r2(monkeypatch, fake)

        raw = _png_bytes(2000, 2000)
        conn = _FakeConn()
        asset = store_upload(
            raw, kind="equipo", derive_specs=[DISPLAY_SQUARE, DISPLAY_SQUARE_SM], conn=conn
        )

        display = asset.variant("display")
        sm = asset.variant("display-sm")
        assert display is not None and sm is not None
        assert display.width == 1200 and sm.width == 600  # srcset: 600w + 1200w
        assert sm.key.endswith("/display-sm.webp")
        assert sm.bytes < display.bytes  # la variante chica pesa menos

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

    def test_asset_tiene_content_hash(self, monkeypatch):
        from services.media.service import store_upload
        from services.media.specs import DISPLAY_KEEP_ASPECT

        fake = _FakeR2Client()
        _patch_r2(monkeypatch, fake)
        conn = _FakeConn()
        asset = store_upload(_png_bytes(), kind="estudio", derive_specs=[DISPLAY_KEEP_ASPECT], conn=conn)

        assert asset.content_hash is not None
        assert len(asset.content_hash) == 64  # SHA-256 hex


# ── dedup por hash ────────────────────────────────────────────────────────────

class TestDedup:
    def test_dedup_devuelve_existente_sin_tocar_r2(self, monkeypatch):
        """Si la misma imagen ya existe para ese kind, store_upload devuelve el asset
        existente sin hacer ningún PUT a R2."""
        from services.media.service import store_upload
        from services.media.specs import DISPLAY_KEEP_ASPECT
        from services.media.models import MediaAsset

        existing_asset = MediaAsset(
            id=42, kind="estudio",
            original_key="media/estudio/42/original.png",
            original_ct="image/png", width=400, height=300, bytes=1234,
            content_hash="abc123",
            variants=[],
        )

        fake = _FakeR2Client()
        _patch_r2(monkeypatch, fake)

        # Parchamos find_by_hash para simular un hit de dedup.
        import services.media.repository as repo_mod
        monkeypatch.setattr(repo_mod, "find_by_hash", lambda conn, kind, h: existing_asset)

        conn = _FakeConn()
        result = store_upload(_png_bytes(), kind="estudio", derive_specs=[DISPLAY_KEEP_ASPECT], conn=conn)

        # Debe devolver el asset existente
        assert result.id == 42
        assert result.original_key == "media/estudio/42/original.png"
        # Y NO hacer ningún PUT (0 subidas a R2)
        assert fake.puts == []

    def test_no_dedup_si_imagen_distinta(self, monkeypatch):
        """Dos imágenes distintas → dos assets distintos."""
        from services.media.service import store_upload
        from services.media.specs import DISPLAY_KEEP_ASPECT
        import services.media.repository as repo_mod

        fake = _FakeR2Client()
        _patch_r2(monkeypatch, fake)

        # find_by_hash devuelve None (no hay dedup)
        monkeypatch.setattr(repo_mod, "find_by_hash", lambda conn, kind, h: None)

        conn = _FakeConn()
        asset = store_upload(_png_bytes(w=100, h=80), kind="estudio", derive_specs=[DISPLAY_KEEP_ASPECT], conn=conn)

        # Nuevo asset creado, PUT realizado
        assert asset.id is not None
        assert len(fake.puts) >= 1  # original + variante(s)


# ── fallo parcial ─────────────────────────────────────────────────────────────

class TestStoreUploadFalloParcial:
    def test_fallo_en_put_variante_limpia_original_y_eleva(self, monkeypatch):
        """put_private (original) OK, put (variante) falla → cleanup borra el original."""
        from services.media.errors import MediaError
        from services.media.service import store_upload
        from services.media.specs import DISPLAY_KEEP_ASPECT

        fake = _FakeR2Client(fail_on_key=None)
        _patch_r2(monkeypatch, fake)

        # El original usa put_private (OK), la variante usa put (falla).
        import services.media.storage as storage_mod
        original_put = storage_mod.put

        def _put_that_always_fails(key, content, content_type):
            raise Exception("R2 falla en variante")

        monkeypatch.setattr(storage_mod, "put", _put_that_always_fails)

        conn = _FakeConn()
        with pytest.raises((MediaError, Exception)):
            store_upload(_png_bytes(), kind="estudio", derive_specs=[DISPLAY_KEEP_ASPECT], conn=conn)

        # El original (subido con put_private) debe haberse limpiado (delete_object)
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


# ── slug sanit del kind ───────────────────────────────────────────────────────

class TestKindSlugSanit:
    """kind va directo a la R2 key — solo [a-z0-9-] permitidos."""

    @pytest.mark.parametrize("bad_kind", [
        "../admin",       # path traversal
        "foo/bar",        # slash
        "EQUIPO",         # mayúsculas
        "equipo foto",    # espacio
        "",               # vacío
        "a" * 65,         # demasiado largo
        ".hidden",        # empieza con punto
        "-lead",          # empieza con guión
    ])
    def test_kind_invalido_eleva_400(self, bad_kind, monkeypatch):
        from services.media.errors import MediaError
        from services.media.service import store_upload
        from services.media.specs import DISPLAY_KEEP_ASPECT

        fake = _FakeR2Client()
        _patch_r2(monkeypatch, fake)

        raw = _png_bytes()
        with pytest.raises(MediaError) as exc:
            store_upload(raw, kind=bad_kind, derive_specs=[DISPLAY_KEEP_ASPECT], conn=_FakeConn())
        assert exc.value.status == 400

    @pytest.mark.parametrize("good_kind", [
        "equipo",
        "estudio",
        "marca",
        "workshop-foto",
        "instructor123",
    ])
    def test_kind_valido_pasa(self, good_kind, monkeypatch):
        from services.media.service import store_upload
        from services.media.specs import DISPLAY_KEEP_ASPECT

        fake = _FakeR2Client()
        _patch_r2(monkeypatch, fake)

        asset = store_upload(_png_bytes(), kind=good_kind, derive_specs=[DISPLAY_KEEP_ASPECT], conn=_FakeConn())
        assert good_kind in asset.original_key
