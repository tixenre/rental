"""Tests que validan el split de spec_key="tipo" por categoría.

Verifica que:
- El seed ya no tiene ningún spec con `key="tipo"`.
- Cada categoría que antes usaba "tipo" ahora usa su propio `<cat>_subtipo`.
- La migración `b9d4e7c3a1f5` declara los mismos enum_options que el seed
  para cada subtipo (consistencia entre upgrade y seed nuevo).
- `_collect_spec_definitions()` ya no unifica enum_options entre categorías
  (cada subtipo tiene sus opciones limpias).
"""

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

from seeds.spec_templates import TEMPLATES, _collect_spec_definitions


BACKEND_ROOT = Path(__file__).resolve().parent.parent
MIGRATION_PATH = (
    BACKEND_ROOT / "migrations" / "versions"
    / "b9d4e7c3a1f5_split_tipo_por_categoria.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("split_tipo_mig", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXPECTED_SUBTIPOS = {
    "Modificadores": "modificador_subtipo",
    "Soportes": "soporte_subtipo",
    "Grip": "grip_subtipo",
    "Sonido": "mic_subtipo",
    "Monitores y Video": "monitor_subtipo",
    "Adaptadores y Filtros": "adaptador_subtipo",
    "Energía": "energia_subtipo",
    "Media y Datos": "media_subtipo",
}


def test_seed_no_tiene_key_tipo_colisionando():
    """Ninguna categoría del seed declara más spec_key='tipo' (el bug que
    causaba la unión de enum_options entre categorías heterogéneas)."""
    for cat_nombre, specs in TEMPLATES.items():
        keys = [s["key"] for s in specs]
        assert "tipo" not in keys, (
            f"Categoría '{cat_nombre}' todavía declara spec_key='tipo' "
            "(debería usar su <cat>_subtipo propio)"
        )


def test_cada_categoria_tiene_su_subtipo():
    """Cada categoría que tenía 'tipo' antes ahora declara el subtipo
    canónico esperado (modificador_subtipo, soporte_subtipo, etc.)."""
    for cat_nombre, expected_key in EXPECTED_SUBTIPOS.items():
        assert cat_nombre in TEMPLATES, f"Categoría '{cat_nombre}' falta en TEMPLATES"
        keys = [s["key"] for s in TEMPLATES[cat_nombre]]
        assert expected_key in keys, (
            f"Categoría '{cat_nombre}' debe declarar '{expected_key}'; "
            f"keys actuales: {keys}"
        )


def test_collect_spec_definitions_no_unifica_subtipos():
    """`_collect_spec_definitions()` colapsa por spec_key. Cada subtipo
    aparece UNA sola vez (su categoría dueña) con sus enum_options
    propios — no se mezclan entre categorías."""
    defs = _collect_spec_definitions()
    for cat_nombre, expected_key in EXPECTED_SUBTIPOS.items():
        assert expected_key in defs, f"Subtipo '{expected_key}' falta en defs"
        opciones = defs[expected_key]["enum_options"]
        # Cada subtipo trae solo sus opciones (sin mezcla cross-categoría).
        seed_spec = next(
            s for s in TEMPLATES[cat_nombre] if s["key"] == expected_key
        )
        assert sorted(opciones) == sorted(seed_spec["enum_options"]), (
            f"'{expected_key}' tiene enum_options distinto al del seed "
            "(¿alguien más lo está declarando?)"
        )


def test_migracion_declara_mismos_subtipos_y_options_que_seed():
    """La lista CATEGORIA_SUBTIPOS de la migración debe matchear los
    subtipos y enum_options del seed. Si el seed cambia, la migración
    debe sincronizar."""
    mig = _load_migration_module()
    mig_by_cat = {c["categoria_nombre"]: c for c in mig.CATEGORIA_SUBTIPOS}
    for cat_nombre, expected_key in EXPECTED_SUBTIPOS.items():
        assert cat_nombre in mig_by_cat, (
            f"Migración no contempla la categoría '{cat_nombre}'"
        )
        mig_entry = mig_by_cat[cat_nombre]
        assert mig_entry["new_spec_key"] == expected_key, (
            f"Migración usa spec_key '{mig_entry['new_spec_key']}' para "
            f"'{cat_nombre}', el seed espera '{expected_key}'"
        )
        seed_spec = next(
            s for s in TEMPLATES[cat_nombre] if s["key"] == expected_key
        )
        assert mig_entry["enum_options"] == seed_spec["enum_options"], (
            f"enum_options divergen entre migración y seed para "
            f"'{expected_key}' (cat '{cat_nombre}')"
        )


def test_migracion_revision_chain():
    """La migración baja de a8c1b3d5e9f2 (output_config), que era el HEAD
    antes de este commit."""
    mig = _load_migration_module()
    assert mig.revision == "b9d4e7c3a1f5"
    assert mig.down_revision == "a8c1b3d5e9f2"
