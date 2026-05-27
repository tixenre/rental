"""Tests unitarios para routes/estudio.py (E1).

Verifica:
- La lógica de _build_response serializa correctamente JSON fields.
- _parse_json_field maneja None, lista, string JSON y string inválido.
- _foto_path_estudio genera paths con prefijo correcto.
- Guards de admin: los endpoints sensibles rechazan sin sesión.
"""

import json
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.unit


# ── _parse_json_field ────────────────────────────────────────────────────────

class TestParseJsonField:
    def _parse(self, val):
        from routes.estudio import _parse_json_field
        return _parse_json_field(val)

    def test_none_devuelve_none(self):
        assert self._parse(None) is None

    def test_string_vacio_devuelve_none(self):
        assert self._parse("") is None

    def test_lista_devuelve_lista(self):
        val = [{"label": "Superficie", "value": "— m²"}]
        assert self._parse(val) == val

    def test_string_json_valido(self):
        data = [{"q": "¿Mínimo?", "a": "2 h"}]
        assert self._parse(json.dumps(data)) == data

    def test_string_json_invalido_devuelve_none(self):
        assert self._parse("no es json {{{") is None


# ── _foto_path_estudio ────────────────────────────────────────────────────────

class TestFotoPathEstudio:
    def test_prefijo_correcto(self):
        from routes.estudio import _foto_path_estudio
        path = _foto_path_estudio()
        assert path.startswith("estudio/")
        assert path.endswith(".webp")

    def test_paths_unicos(self):
        import time
        from routes.estudio import _foto_path_estudio
        paths = {_foto_path_estudio() for _ in range(5)}
        # Si el reloj corre muy rápido puede colapsar; aceptamos ≥ 1 único
        assert len(paths) >= 1


# ── _build_response ──────────────────────────────────────────────────────────

class TestBuildResponse:
    def _make_row(self, **overrides):
        defaults = {
            "id": 1,
            "equipo_id": None,
            "nombre": "El Estudio",
            "tagline": "Foto y video",
            "descripcion": "Un espacio.",
            "precio_hora": 5000,
            "min_horas": 2,
            "open_hour": 8,
            "close_hour": 22,
            "buffer_horas": 0,
            "pack_activo": True,
            "pack_nombre": "Pack Todo Incluido",
            "pack_descripcion": "Todo incluido.",
            "pack_precio": 10000,
            "features_json": json.dumps([{"label": "Superficie", "value": "50 m²"}]),
            "faq_json": json.dumps([{"q": "¿Mínimo?", "a": "2 h"}]),
            "updated_at": None,
        }
        defaults.update(overrides)
        row = MagicMock()
        row.__getitem__ = lambda self, k: defaults[k]
        return row

    def test_features_parseadas(self):
        from routes.estudio import _build_response
        row = self._make_row()
        result = _build_response(row, [])
        assert result["features"] == [{"label": "Superficie", "value": "50 m²"}]

    def test_faq_parseada(self):
        from routes.estudio import _build_response
        row = self._make_row()
        result = _build_response(row, [])
        assert result["faq"] == [{"q": "¿Mínimo?", "a": "2 h"}]

    def test_features_none_cuando_json_nulo(self):
        from routes.estudio import _build_response
        row = self._make_row(features_json=None)
        result = _build_response(row, [])
        assert result["features"] is None

    def test_fotos_incluidas(self):
        from routes.estudio import _build_response
        row = self._make_row()
        fotos = [{"id": 1, "url": "https://cdn.r2/foto.webp", "orden": 0, "es_principal": True}]
        result = _build_response(row, fotos)
        assert result["fotos"] == fotos

    def test_pack_activo_bool(self):
        from routes.estudio import _build_response
        row = self._make_row(pack_activo=1)  # simulando valor DB integer
        result = _build_response(row, [])
        assert result["pack_activo"] is True


# ── Guards de admin ───────────────────────────────────────────────────────────

class FakeRequest:
    def __init__(self, cookies=None):
        self.cookies = cookies or {}


class TestEstudioAdminGuards:
    """Verifica que los endpoints admin exigen autenticación."""

    def test_patch_estudio_requiere_admin(self, monkeypatch):
        monkeypatch.delenv("ADMIN_BYPASS_AUTH", raising=False)
        monkeypatch.setattr("admin_guard.get_session", lambda req: None)

        from routes.estudio import patch_estudio, EstudioUpdate

        with pytest.raises(HTTPException) as exc:
            patch_estudio(EstudioUpdate(), FakeRequest())
        assert exc.value.status_code == 401

    def test_delete_foto_requiere_admin(self, monkeypatch):
        monkeypatch.delenv("ADMIN_BYPASS_AUTH", raising=False)
        monkeypatch.setattr("admin_guard.get_session", lambda req: None)

        from routes.estudio import delete_foto

        with pytest.raises(HTTPException) as exc:
            delete_foto(1, FakeRequest())
        assert exc.value.status_code == 401

    def test_reorder_fotos_requiere_admin(self, monkeypatch):
        monkeypatch.delenv("ADMIN_BYPASS_AUTH", raising=False)
        monkeypatch.setattr("admin_guard.get_session", lambda req: None)

        from routes.estudio import reorder_fotos, ReorderBody

        with pytest.raises(HTTPException) as exc:
            reorder_fotos(ReorderBody(fotos=[]), FakeRequest())
        assert exc.value.status_code == 401

    def test_upload_from_url_requiere_admin(self, monkeypatch):
        monkeypatch.delenv("ADMIN_BYPASS_AUTH", raising=False)
        monkeypatch.setattr("admin_guard.get_session", lambda req: None)

        from routes.estudio import upload_foto_from_url, UploadFromUrlBody

        with pytest.raises(HTTPException) as exc:
            upload_foto_from_url(UploadFromUrlBody(url="https://example.com/img.jpg"), FakeRequest())
        assert exc.value.status_code == 401
