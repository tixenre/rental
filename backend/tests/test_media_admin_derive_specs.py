"""Regresión #1054: el re-derive del admin NO debe perder las variantes AVIF.

`_ALL_DERIVE_SPECS` (routes/media_admin.py) es la lista que usa POST /admin/media/rederive
para regenerar TODAS las variantes de un asset desde el original. Si no incluye las specs
AVIF, re-derivar desde el back-office regenera solo webp y PIERDE el AVIF → el catálogo cae
al fallback webp para ese equipo. Espeja el conjunto canónico EQUIPO_DERIVE_SPECS.
"""
import pytest

pytestmark = pytest.mark.unit


def test_all_derive_specs_incluye_avif():
    from routes.media_admin import _ALL_DERIVE_SPECS

    fmts = {s.fmt for s in _ALL_DERIVE_SPECS}
    assert "avif" in fmts, "el re-derive del admin perdería el AVIF (#1054)"


def test_all_derive_specs_cubre_los_3_anchos_avif():
    from routes.media_admin import _ALL_DERIVE_SPECS

    avif_names = {s.name for s in _ALL_DERIVE_SPECS if s.fmt == "avif"}
    # display (full) + sm (srcset mobile) + thumb (slots chicos del catálogo)
    assert {"display-avif", "display-sm-avif", "display-thumb-avif"} <= avif_names
