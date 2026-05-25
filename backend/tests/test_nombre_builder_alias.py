"""Tests del alias de labels renombrados en placeholders `{spec:...}`.

Al renombrar el label `lens_mount` de "Lens mount" → "Montura", los
templates guardados que aún referencian `{spec:Lens mount}` deben seguir
resolviendo (vía `_LABEL_ALIASES` en nombre_builder).
"""

import pytest

pytestmark = pytest.mark.unit

from services.nombre_builder import _render_template


SPECS = [{"label": "Montura", "value": "E", "tipo": "enum"}]
VARS = {"marca": "Sony", "modelo": "FX3"}


def test_placeholder_label_nuevo_resuelve():
    out = _render_template("{marca} {modelo} {spec:Montura}", VARS, SPECS)
    assert out == "Sony FX3 E"


def test_placeholder_label_viejo_resuelve_via_alias():
    # Template viejo con {spec:Lens mount} sigue funcionando.
    out = _render_template("{marca} {modelo} {spec:Lens mount}", VARS, SPECS)
    assert out == "Sony FX3 E"


def test_alias_case_y_tilde_insensible():
    out = _render_template("{spec:LENS MOUNT}", VARS, SPECS)
    assert out == "E"
