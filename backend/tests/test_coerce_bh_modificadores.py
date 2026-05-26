"""Tests Fase 6f — coerción de valores B&H para modificadores.

Cubre:
- _coerce_bool con patrones B&H: "Yes (Included)", "Yes (Not Included)",
  "Yes, Removable", "Foldable", "Click/Locking Type".
- _coerce_enum con labels B&H: "Item Type" → modificador_subtipo, "Light
  Compatibility" → montura_luz (substring match).
- Aliases en el registry: las keys reales de B&H resuelven a la spec_key
  canónica.
"""

import pytest

pytestmark = pytest.mark.unit

from services.spec_coerce import _coerce_bool, _coerce_enum


# ── _coerce_bool: patrones B&H ────────────────────────────────────────────────


@pytest.mark.parametrize("raw,expected", [
    # Patrones B&H con calificadores parentéticos
    ("Yes (Included)",       "true"),
    ("Yes (Not Included)",   "false"),
    ("yes (not included)",   "false"),   # case-insensitive
    ("Yes (Sold Separately)", "true"),   # paréntesis sin "not"
    # Patrones con coma
    ("Yes, Removable",       "true"),
    ("Yes, Included",        "true"),
    # Valores estándar
    ("Yes",                  "true"),
    ("No",                   "false"),
    ("true",                 "true"),
    ("false",                "false"),
    # Aliases para plegable
    ("Foldable",             "true"),
    ("Collapsible",          "true"),
])
def test_coerce_bool_bh_patterns(raw, expected):
    assert _coerce_bool(raw) == expected


def test_coerce_bool_click_locking_no_coerce():
    # "Click/Locking Type" no es un valor booleano estándar → None (fallback al raw).
    assert _coerce_bool("Click/Locking Type") is None


# ── _coerce_enum: substring match para B&H ───────────────────────────────────


def test_coerce_enum_item_type_softbox():
    """'Parabolic Softbox (16-Sided Hexadecagon Shape)' → 'Softbox' por substring."""
    opts = ["Softbox", "Spotlight", "Fresnel", "Difusor", "Bandera Negra", "Reflector"]
    result = _coerce_enum("Parabolic Softbox (16-Sided Hexadecagon Shape)", opts)
    assert result == "Softbox"


def test_coerce_enum_item_type_lantern():
    opts = ["Softbox", "Spotlight", "Fresnel", "Difusor", "Bandera Negra", "Reflector"]
    # "Lantern" no está en opts; si B&H dice "Lantern Softbox" → "Softbox".
    result = _coerce_enum("Lantern Softbox", opts)
    assert result == "Softbox"


def test_coerce_enum_light_compatibility_bowens():
    """'Includes Speed Ring with Bowens S Mount' → 'Bowens' por substring."""
    opts = ["Bowens", "Elinchrom", "Profoto", "Godox", "Broncolor", "M11 (Aputure)"]
    result = _coerce_enum("Includes Speed Ring with Bowens S Mount", opts)
    assert result == "Bowens"


def test_coerce_enum_light_compatibility_bowens_builtin():
    opts = ["Bowens", "Elinchrom", "Profoto", "Godox", "Broncolor", "M11 (Aputure)"]
    result = _coerce_enum("Built-In Speed Ring with Bowens S Mount", opts)
    assert result == "Bowens"


# ── Aliases en el registry ────────────────────────────────────────────────────


def _build_alias_index(specs: list) -> dict:
    """Mapea alias.lower() → spec_key, igual que el extractor."""
    import re
    idx = {}
    for s in specs:
        for alias in s.aliases:
            key = re.sub(r"\s*\([^)]*\)\s*$", "", alias.lower().strip())
            idx[key] = s.key
        idx[s.label.lower().strip()] = s.key
    return idx


def test_alias_item_type_resuelve_modificador_subtipo():
    from specs.categorias.modificadores import CAT
    idx = _build_alias_index(CAT.specs)
    assert idx.get("item type") == "modificador_subtipo"


def test_alias_accepts_grids_resuelve_incluye_grid():
    from specs.categorias.modificadores import CAT
    idx = _build_alias_index(CAT.specs)
    assert idx.get("accepts grids") == "incluye_grid"


def test_alias_interior_baffle_resuelve_incluye_difusor():
    from specs.categorias.modificadores import CAT
    idx = _build_alias_index(CAT.specs)
    assert idx.get("interior baffle") == "incluye_difusor"


def test_alias_quick_open_type_resuelve_plegable():
    from specs.categorias.modificadores import CAT
    idx = _build_alias_index(CAT.specs)
    assert idx.get("quick open type") == "plegable"


def test_alias_light_loss_gain_resuelve_light_loss_stops():
    from specs.categorias.modificadores import CAT
    idx = _build_alias_index(CAT.specs)
    assert idx.get("light loss/gain") == "light_loss_stops"


def test_alias_light_compatibility_resuelve_montura_luz():
    from specs.shared.lighting import montura_luz
    spec = montura_luz()
    aliases_lower = [a.lower() for a in spec.aliases]
    assert "light compatibility" in aliases_lower
