"""Regresión #921: ningún `CREATE INDEX IF NOT EXISTS` de `init_db` debe repetir
nombre con una definición distinta.

Con `IF NOT EXISTS`, dos índices del mismo nombre → el segundo **nunca se crea**
(índice fantasma silencioso). Pasó con `idx_spec_def_compat` (uno sobre `spec_key`,
otro sobre `es_compatibilidad`). Este test es hermético (lee el fuente, sin DB) y
falla si vuelve a colar un nombre duplicado.
"""
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SCHEMA = Path(__file__).resolve().parents[1] / "database" / "schema.py"
_RE_INDEX = re.compile(
    r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+IF\s+NOT\s+EXISTS\s+(\w+)", re.IGNORECASE
)


def test_no_hay_indices_con_nombre_duplicado():
    names = _RE_INDEX.findall(_SCHEMA.read_text())
    dups = sorted({n for n in names if names.count(n) > 1})
    assert not dups, (
        f"Índices con nombre duplicado en init_db (con IF NOT EXISTS el 2º nunca "
        f"se crea — índice fantasma, #921): {dups}"
    )
