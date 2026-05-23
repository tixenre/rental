"""Tests del orchestrator (puro filesystem, sin DB)."""

import json
import tempfile
from pathlib import Path

import pytest

from dataio import orchestrator


pytestmark = pytest.mark.unit


class TestHasCatalogData:
    def test_dir_no_existe(self):
        assert orchestrator.has_catalog_data(Path("/tmp/no-existe-12345")) is False

    def test_dir_vacio(self):
        with tempfile.TemporaryDirectory() as tmp:
            assert orchestrator.has_catalog_data(Path(tmp)) is False

    def test_equipos_json_vacio(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "equipos.json").write_text("[]")
            assert orchestrator.has_catalog_data(Path(tmp)) is False

    def test_equipos_json_con_filas(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "equipos.json").write_text(
                json.dumps([{"slug": "sony-fx3", "nombre": "Sony FX3"}])
            )
            assert orchestrator.has_catalog_data(Path(tmp)) is True

    def test_equipos_json_invalido(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "equipos.json").write_text("not json at all {{{")
            # Defensivo: invalid JSON cuenta como "sin data"
            assert orchestrator.has_catalog_data(Path(tmp)) is False


class TestValidateDir:
    def test_dir_vacio_devuelve_zeros(self):
        with tempfile.TemporaryDirectory() as tmp:
            counts = orchestrator.validate_dir(Path(tmp))
            for entity, n in counts.items():
                assert n == 0, f"{entity} debería estar vacío"

    def test_marcas_validas(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "marcas.json").write_text(
                json.dumps([
                    {"nombre": "Sony"},
                    {"nombre": "Canon", "visible": False, "orden": 5},
                ])
            )
            counts = orchestrator.validate_dir(Path(tmp))
            assert counts["marcas"] == 2

    def test_marcas_invalidas_falla(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "marcas.json").write_text(
                json.dumps([{"nombre": "Sony", "campo_inventado": True}])
            )
            with pytest.raises(Exception, match="marcas"):
                orchestrator.validate_dir(Path(tmp))
