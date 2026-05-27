"""Consistencia del registro de entidades dataio + grupos de backup.

Sin DB: chequea que cada entidad declarada tenga modelo + exporter + importer,
y que los grupos de backup (Configuración / Clientes / Pedidos) referencien
entidades válidas. Blinda que sumar una entidad nueva no quede a medias.
"""
import pytest

from dataio.exporters import EXPORTERS
from dataio.importers import IMPORTERS
from dataio.schema import ENTITY_MODELS
from dataio import paths

pytestmark = pytest.mark.unit


class TestRegistryConsistency:
    def test_cada_entidad_tiene_modelo_exporter_importer(self):
        for entity in paths.ENTITY_ORDER:
            assert entity in ENTITY_MODELS, f"{entity} sin modelo Pydantic"
            assert entity in EXPORTERS, f"{entity} sin exporter"
            assert entity in IMPORTERS, f"{entity} sin importer"

    def test_no_hay_exporters_sin_importer_ni_modelo(self):
        assert set(EXPORTERS) == set(IMPORTERS)
        assert set(EXPORTERS) == set(ENTITY_MODELS)

    def test_entidades_nuevas_de_config_registradas(self):
        for entity in ("app_settings", "email_templates", "descuentos_jornada"):
            assert entity in ENTITY_MODELS
            assert entity in EXPORTERS
            assert entity in IMPORTERS
            assert entity in paths.ENTITY_ORDER


class TestBackupGroups:
    def test_grupos_referencian_entidades_validas(self):
        for grupo, entities in paths.BACKUP_GROUPS.items():
            assert entities, f"grupo {grupo} vacío"
            for e in entities:
                assert e in paths.ENTITY_ORDER, f"{grupo}: {e} no está en ENTITY_ORDER"

    def test_configuracion_incluye_catalogo_y_config(self):
        grupo = set(paths.BACKUP_GROUPS["configuracion"])
        assert set(paths.CATALOG_ENTITIES) <= grupo
        assert set(paths.CONFIG_ENTITIES) <= grupo
        # No debe filtrar datos personales en "configuración".
        assert "clientes" not in grupo
        assert "alquileres" not in grupo

    def test_clientes_y_pedidos_separados(self):
        assert paths.BACKUP_GROUPS["clientes"] == ("clientes",)
        assert paths.BACKUP_GROUPS["pedidos"] == ("alquileres",)
