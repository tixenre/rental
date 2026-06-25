"""Tests de services/media/youtube.py — extracción de video_id, URL nocookie,
descarga de poster (con mock HTTP) y validaciones de seguridad.
"""
import pytest

pytestmark = pytest.mark.unit

from services.media.youtube import (
    extract_video_id,
    youtube_nocookie_url,
    fetch_youtube_poster,
)
from services.media.errors import MediaError


class TestExtractVideoId:
    @pytest.mark.parametrize("url,expected", [
        # URL larga
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        # URL corta
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        # Shorts
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        # Embed
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        # ID directo
        ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        # Con parámetros extra
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s", "dQw4w9WgXcQ"),
        # youtu.be con parámetros
        ("https://youtu.be/dQw4w9WgXcQ?si=abc", "dQw4w9WgXcQ"),
    ])
    def test_extrae_correctamente(self, url, expected):
        assert extract_video_id(url) == expected

    @pytest.mark.parametrize("bad", [
        "",
        None,
        "https://vimeo.com/123456",
        "not-a-url",
        "dQw4w9WgX",      # demasiado corto (9 chars)
        "dQw4w9WgXcQXXX",  # demasiado largo (15 chars)
        "dQw4w9Wg XcQ",   # espacio en el ID
        "https://youtube.com/watch",  # sin ?v=
    ])
    def test_url_invalida_devuelve_none(self, bad):
        assert extract_video_id(bad) is None


class TestYoutubeNocookieUrl:
    def test_usa_nocookie(self):
        url = youtube_nocookie_url("dQw4w9WgXcQ")
        assert "youtube-nocookie.com" in url
        assert "dQw4w9WgXcQ" in url

    def test_no_usa_youtube_com(self):
        url = youtube_nocookie_url("abc12345678")
        # No debe usar youtube.com (solo el dominio nocookie)
        assert "//www.youtube.com" not in url


class TestFetchYoutubePoster:
    def test_descarga_poster_ok(self, monkeypatch):
        """Mock HTTP: maxresdefault responde con bytes de imagen JPEG válida."""
        from io import BytesIO
        from PIL import Image

        def _fake_jpeg() -> bytes:
            buf = BytesIO()
            Image.new("RGB", (1280, 720), (200, 50, 50)).save(buf, format="JPEG")
            return buf.getvalue()

        class _FakeResp:
            status_code = 200
            content = _fake_jpeg()
            headers = {"content-type": "image/jpeg"}

        class _FakeClient:
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def get(self, url, **_): return _FakeResp()

        import httpx
        monkeypatch.setattr(httpx, "Client", lambda **_: _FakeClient())
        raw = fetch_youtube_poster("dQw4w9WgXcQ")
        assert len(raw) > 1000
        # Verificar que es un JPEG válido
        img = Image.open(BytesIO(raw))
        assert img.width == 1280

    def test_video_id_invalido_eleva_400(self):
        with pytest.raises(MediaError) as exc:
            fetch_youtube_poster("INVALID!!!")
        assert exc.value.status == 400

    def test_sin_httpx_eleva_500(self, monkeypatch):
        import builtins
        _orig_import = builtins.__import__

        def _no_httpx(name, *args, **kwargs):
            if name == "httpx":
                raise ImportError("httpx no disponible")
            return _orig_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _no_httpx)
        with pytest.raises(MediaError) as exc:
            fetch_youtube_poster("dQw4w9WgXcQ")
        assert exc.value.status == 500

    def test_http_falla_eleva_502(self, monkeypatch):
        """Si todos los fallbacks fallan, eleva MediaError(502)."""
        class _FakeResp:
            status_code = 404
            content = b""
            headers = {}

        class _FakeClient:
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def get(self, url, **_): return _FakeResp()

        import httpx
        monkeypatch.setattr(httpx, "Client", lambda **_: _FakeClient())
        with pytest.raises(MediaError) as exc:
            fetch_youtube_poster("dQw4w9WgXcQ")
        assert exc.value.status == 502
