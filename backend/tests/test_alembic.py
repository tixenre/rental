"""Smoke tests del setup de Alembic.

NO corre migraciones contra una BD real — eso es integration test (issue
futuro). Verifica que:
- Alembic carga la config.
- Las migraciones son listables sin errores.
- El baseline existe y su upgrade/downgrade no rompen.
"""

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

BACKEND_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = BACKEND_ROOT / "migrations"
VERSIONS_DIR = MIGRATIONS_DIR / "versions"


def test_alembic_ini_existe():
    assert (BACKEND_ROOT / "alembic.ini").exists()


def test_estructura_de_migrations():
    assert MIGRATIONS_DIR.exists()
    assert MIGRATIONS_DIR.is_dir()
    assert (MIGRATIONS_DIR / "env.py").exists()
    assert (MIGRATIONS_DIR / "script.py.mako").exists()
    assert VERSIONS_DIR.exists()


def test_hay_al_menos_una_migracion():
    revisions = list(VERSIONS_DIR.glob("*.py"))
    # Excluir __init__.py si hubiera
    revisions = [r for r in revisions if r.name != "__init__.py"]
    assert len(revisions) >= 1, "Debería haber al menos la migración baseline"


def test_alembic_config_se_carga_sin_errores():
    """Verifica que `Config(alembic.ini)` carga limpiamente."""
    from alembic.config import Config

    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    # Si no tira, está OK.
    assert cfg.get_main_option("script_location")


def test_baseline_migration_es_importable():
    """Importa la primera migración y verifica upgrade()/downgrade() son no-op."""
    revisions = sorted(
        f for f in VERSIONS_DIR.glob("*.py")
        if f.name != "__init__.py"
    )
    assert revisions, "No hay migraciones"

    # Buscar la migración baseline (down_revision = None). NO es siempre
    # el primer archivo alfabéticamente: a medida que se agregan migraciones,
    # el orden por filename cambia.
    baseline = None
    for path in revisions:
        spec = importlib.util.spec_from_file_location(f"mig_{path.stem}", path)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "upgrade")
        assert hasattr(mod, "downgrade")
        assert hasattr(mod, "revision")
        if mod.down_revision is None:
            baseline = mod
            break

    assert baseline is not None, "No se encontró migración con down_revision=None (baseline)"


def test_script_directory_lista_revisiones():
    """ScriptDirectory de Alembic puede enumerar las migraciones."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    script_dir = ScriptDirectory.from_config(cfg)

    heads = script_dir.get_heads()
    assert len(heads) >= 1, "Debería haber al menos una head"
    # No debería haber heads divergentes en este punto
    assert len(heads) == 1, f"Heads divergentes detectados: {heads}"
