"""
Tests de F2: foto de instructor de talleres migrada al motor de media.

Cobertura:
- _taller_to_dict incluye instructor_media_id
- admin_upload_foto_instructor llama a store_upload y actualiza media_id + url
- media_api.get_entity_media("instructor", taller_id) devuelve el asset
- Fallback: foto_url legacy cuando no hay media_id
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _fake_variant(name="display", url="https://cdn.test/display.webp", w=400, h=400):
    v = SimpleNamespace(name=name, url=url, width=w, height=h, content_type="image/webp")
    return v


def _fake_asset(asset_id=7, media_id_url="https://cdn.test/display.webp"):
    v = _fake_variant(url=media_id_url)
    asset = MagicMock()
    asset.id = asset_id
    asset.variants = [v]
    asset.variant.return_value = v
    asset.lqip = None
    asset.status = "ready"
    return asset


# ── test: _taller_to_dict incluye instructor_media_id ─────────────────────────

def test_taller_to_dict_incluye_instructor_media_id():
    """_taller_to_dict devuelve instructor_media_id cuando la columna existe."""
    from routes.talleres import _taller_to_dict

    row = {
        "id": 1,
        "slug": "foto-nivel-intermedio",
        "nombre": "Foto",
        "subtitulo": "",
        "instructor_nombre": "Ana",
        "instructor_bio": "bio",
        "instructor_proyectos": "[]",
        "descripcion": "",
        "publico_objetivo": "",
        "programa_teorica": "[]",
        "programa_practica": "[]",
        "fecha_inicio": None,
        "fecha_fin": None,
        "horario": "",
        "cupos_total": 10,
        "cupos_confirmados": 0,
        "precio_total": 0,
        "precio_sena": 0,
        "pago_alias": "",
        "pago_cbu": "",
        "pago_banco": "",
        "direccion": "",
        "instructor_foto_url": "https://cdn/old.jpg",
        "instructor_media_id": 42,
        "numero_edicion": 1,
        "proxima_edicion_slug": "",
    }
    d = _taller_to_dict(row)
    assert d["instructor_media_id"] == 42
    assert d["instructor_foto_url"] == "https://cdn/old.jpg"


def test_taller_to_dict_sin_instructor_media_id():
    """_taller_to_dict devuelve None cuando la columna no está en el row (pre-F2)."""
    from routes.talleres import _taller_to_dict

    row = {
        "id": 2,
        "slug": "x",
        "nombre": "X",
        "subtitulo": "",
        "instructor_nombre": "B",
        "instructor_bio": "",
        "instructor_proyectos": "[]",
        "descripcion": "",
        "publico_objetivo": "",
        "programa_teorica": "[]",
        "programa_practica": "[]",
        "fecha_inicio": None,
        "fecha_fin": None,
        "horario": "",
        "cupos_total": 0,
        "cupos_confirmados": 0,
        "precio_total": 0,
        "precio_sena": 0,
        "pago_alias": "",
        "pago_cbu": "",
        "pago_banco": "",
        "direccion": "",
        # instructor_media_id no está
    }
    d = _taller_to_dict(row)
    assert d["instructor_media_id"] is None


# ── test: media_api instructor handler ────────────────────────────────────────

def _make_conn_instructor(taller_id, foto_url, media_id):
    conn = MagicMock()
    row = {"id": taller_id, "instructor_foto_url": foto_url, "instructor_media_id": media_id}
    conn.execute.return_value.fetchone.return_value = row
    return conn


def test_instructor_handler_con_media_id():
    """_get_instructor_media devuelve asset con media_id cuando existe."""
    from routes.media_api import _get_instructor_media

    media_id = 5
    conn = _make_conn_instructor(10, "https://cdn/old.jpg", media_id)

    # stub _load_asset_meta y load_variants
    with (
        patch("routes.media_api._load_asset_meta", return_value={"lqip": None, "status": "ready"}),
        patch("routes.media_api._load_variants", return_value=[]),
    ):
        assets = _get_instructor_media(conn, 10)

    assert len(assets) == 1
    a = assets[0]
    assert a["media_id"] == media_id
    assert a["es_principal"] is True
    assert a["orden"] == 0


def test_instructor_handler_sin_taller():
    """_get_instructor_media devuelve [] si el taller no existe."""
    from routes.media_api import _get_instructor_media

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None

    result = _get_instructor_media(conn, 999)
    assert result == []


def test_instructor_handler_fallback_sin_media_id():
    """_get_instructor_media funciona con media_id=None (foto legacy)."""
    from routes.media_api import _get_instructor_media

    conn = _make_conn_instructor(3, "https://cdn/legacy.jpg", None)

    with (
        patch("routes.media_api._load_asset_meta", return_value={"lqip": None, "status": "ready"}),
        patch("routes.media_api._load_variants", return_value=[]),
    ):
        assets = _get_instructor_media(conn, 3)

    assert len(assets) == 1
    assert assets[0]["media_id"] is None
    # fallback: la url legacy se convierte en una variante sintética
    assert assets[0]["variants"][0]["url"] == "https://cdn/legacy.jpg"


def test_instructor_handler_sin_foto_devuelve_vacio():
    """_get_instructor_media devuelve [] cuando no hay media_id ni url."""
    from routes.media_api import _get_instructor_media

    conn = _make_conn_instructor(4, "", None)
    result = _get_instructor_media(conn, 4)
    assert result == []


def test_kind_instructor_en_handler_map():
    """'instructor' debe estar en _KIND_HANDLERS de media_api."""
    from routes.media_api import _KIND_HANDLERS
    assert "instructor" in _KIND_HANDLERS


# ── test: upload route usa store_upload ───────────────────────────────────────

def test_upload_ruta_requiere_autenticacion():
    """La ruta de upload del instructor rechaza sin sesión (401/403)."""
    from fastapi.testclient import TestClient
    import main

    client = TestClient(main.app)
    resp = client.post(
        "/api/admin/talleres/1/upload-foto-instructor",
        files={"file": ("foto.jpg", b"\xff\xd8", "image/jpeg")},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_upload_logica_llama_store_upload():
    """La lógica de upload llama store_upload y actualiza media_id en la BD."""
    asset = _fake_asset(asset_id=99, media_id_url="https://cdn.test/display.webp")

    tiny_jpeg = b"\xff\xd8\xff\xd9"  # JPEG mínimo para el form

    class FakeUploadFile:
        content_type = "image/jpeg"
        filename = "foto.jpg"
        async def read(self): return tiny_jpeg

    class FakeForm:
        def get(self, k): return FakeUploadFile() if k == "file" else None

    class FakeRequest:
        async def form(self): return FakeForm()

    fake_row = {"id": 1}
    fake_conn = MagicMock()
    fake_conn.__enter__ = lambda s: fake_conn
    fake_conn.__exit__ = MagicMock(return_value=False)
    fake_conn.execute.return_value.fetchone.return_value = fake_row

    with (
        patch("routes.talleres.require_admin", return_value=None),
        patch("routes.talleres.get_db", return_value=fake_conn),
        patch("routes.talleres.store_upload", return_value=asset) as mock_su,
    ):
        from routes.talleres import admin_upload_foto_instructor
        result = await admin_upload_foto_instructor(1, FakeRequest())

    mock_su.assert_called_once()
    call_kwargs = mock_su.call_args
    assert call_kwargs.kwargs["kind"] == "instructor"
    assert result["ok"] is True
    assert result["media_id"] == 99
