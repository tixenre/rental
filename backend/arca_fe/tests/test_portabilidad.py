"""Guard de portabilidad: el core arca_fe NO puede importar backend.* ni frameworks."""
from __future__ import annotations

import pathlib
import re

# Módulos que pertenecen al core portable (los únicos permitidos)
_CORE_PKG = pathlib.Path(__file__).parent.parent  # .../backend/arca_fe/


def _iter_core_sources():
    """Itera los .py del core, excluyendo los tests (que sí pueden importar lo que quieran)."""
    for py in _CORE_PKG.glob("*.py"):
        if not py.name.startswith("test_"):
            yield py


def test_sin_imports_backend():
    """Ningún módulo del core importa backend.* ."""
    pattern = re.compile(r"^\s*(import\s+backend|from\s+backend)\b", re.MULTILINE)
    violators = []
    for py in _iter_core_sources():
        if pattern.search(py.read_text()):
            violators.append(py.name)
    assert not violators, f"arca_fe core no debe importar backend.*: {violators}"


def test_sin_imports_fastapi():
    """Ningún módulo del core importa fastapi."""
    pattern = re.compile(r"^\s*(import\s+fastapi|from\s+fastapi)\b", re.MULTILINE)
    violators = []
    for py in _iter_core_sources():
        if pattern.search(py.read_text()):
            violators.append(py.name)
    assert not violators, f"arca_fe core no debe importar fastapi: {violators}"


def test_sin_imports_psycopg():
    """Ningún módulo del core importa psycopg (acceso a BD)."""
    pattern = re.compile(r"^\s*(import\s+psycopg|from\s+psycopg)\b", re.MULTILINE)
    violators = []
    for py in _iter_core_sources():
        if pattern.search(py.read_text()):
            violators.append(py.name)
    assert not violators, f"arca_fe core no debe importar psycopg: {violators}"


def test_version_semver():
    """El __version__ existe y tiene formato SemVer X.Y.Z."""
    import arca_fe
    assert hasattr(arca_fe, "__version__")
    parts = arca_fe.__version__.split(".")
    assert len(parts) == 3, f"__version__ no es SemVer: {arca_fe.__version__!r}"
    assert all(p.isdigit() for p in parts), f"__version__ no es numérico: {arca_fe.__version__!r}"


def test_all_exports_son_importables():
    """Todo símbolo en __all__ es importable desde el paquete."""
    import arca_fe

    for name in arca_fe.__all__:
        assert hasattr(arca_fe, name), f"'{name}' en __all__ pero no importable"


def test_pyproject_version_coincide_con_init():
    """`pyproject.toml` se sincroniza A MANO con `__init__.__version__` (no hay build tooling
    que lo haga automático) — este test evita que se desincronicen sin que nadie lo note."""
    import re as _re

    import arca_fe

    contenido = (_CORE_PKG / "pyproject.toml").read_text()
    m = _re.search(r'^version\s*=\s*"([^"]+)"', contenido, _re.MULTILINE)
    assert m is not None, "pyproject.toml no tiene una línea `version = \"X.Y.Z\"`"
    assert m.group(1) == arca_fe.__version__, (
        f"pyproject.toml dice version={m.group(1)!r} pero "
        f"arca_fe.__version__={arca_fe.__version__!r} — desincronizados"
    )
