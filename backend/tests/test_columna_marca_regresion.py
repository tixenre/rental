"""Regresión #499: ninguna query SQL del backend debe referenciar la columna
`equipos.marca` directamente (fue dropeada por la migración d5a8f2c4b6e9).

El nombre de la marca se resuelve por subquery contra `marcas.nombre` vía
`e.brand_id`. El helper canónico es `database.MARCA_SUBQUERY`. Este test
asegura que la próxima query nueva no caiga en el patrón viejo.

También cubre #504: ninguna query debe referenciar la tabla inexistente
`fichas_tecnicas` ni la columna dropeada `raw_json`.
"""

import pathlib
import re

import pytest

from database import MARCA_NOMBRE_EXPR, MARCA_SUBQUERY


pytestmark = pytest.mark.unit

BACKEND_ROOT = pathlib.Path(__file__).parent.parent
ROUTES_DIR = BACKEND_ROOT / "routes"


# ── Helpers canónicos ────────────────────────────────────────────────────


def test_marca_subquery_tiene_alias():
    """El helper debe incluir `AS marca` para que las queries lo concatenen tal cual."""
    assert "AS marca" in MARCA_SUBQUERY
    assert MARCA_NOMBRE_EXPR in MARCA_SUBQUERY


def test_marca_nombre_expr_es_subquery_pura():
    """Sin alias, lista para WHERE/COALESCE."""
    assert "AS" not in MARCA_NOMBRE_EXPR
    assert "SELECT nombre FROM marcas" in MARCA_NOMBRE_EXPR
    assert "e.brand_id" in MARCA_NOMBRE_EXPR


# ── Regresión #499: no queda código accediendo a equipos.marca ───────────


# Patrones SQL inválidos a buscar en los routes (palabra `marca` aludida
# como COLUMNA de equipos, no como tabla, alias del subquery, ni variable
# Python). Buscamos en strings de SQL (delimitados por triple o single
# quote). El test es heurístico — algunos falsos positivos en comentarios
# o en variables Python son posibles, pero deberían quedar en cero tras
# la limpieza de este PR. Si en el futuro se agrega un comentario que
# matchea, el test guía a usar el helper.

_INVALID_SQL_PATTERNS = [
    # `, marca,` o `SELECT marca,` o `e.marca,` en contexto SQL — la columna ya no existe.
    re.compile(r"\bSELECT\s+[^()]*?\b(?:e\.)?marca\b\s*[,\s][^()]*?FROM\s+equipos\b", re.IGNORECASE | re.DOTALL),
    # `UPDATE equipos SET marca = ?` → escritura rota.
    re.compile(r"\bUPDATE\s+equipos\b[^()]*?\bmarca\s*=", re.IGNORECASE | re.DOTALL),
    # `INSERT INTO equipos (..., marca, ...)` — defensivo.
    re.compile(r"\bINSERT\s+INTO\s+equipos\b[^()]*?\bmarca\b", re.IGNORECASE | re.DOTALL),
]


def _strip_string_literals_with_subquery(content: str) -> str:
    """Saca los fragmentos que contienen la subquery canónica para evitar
    falsos positivos: el alias `AS marca` del helper es válido."""
    # Cualquier referencia a "marcas WHERE id" → es la subquery legítima.
    # Removemos esas líneas para que el regex `, marca` no las matchee.
    out_lines = []
    for line in content.split("\n"):
        if "marcas WHERE id" in line or "FROM marcas" in line or "AS marca" in line:
            continue
        out_lines.append(line)
    return "\n".join(out_lines)


@pytest.mark.parametrize("path", sorted(ROUTES_DIR.rglob("*.py")))
def test_route_no_referencia_columna_marca_eliminada(path):
    """Ningún `.py` de routes/ debe tener queries SQL que accedan a
    `equipos.marca` como columna directa."""
    content = path.read_text(encoding="utf-8")
    sin_subquery = _strip_string_literals_with_subquery(content)
    for pat in _INVALID_SQL_PATTERNS:
        match = pat.search(sin_subquery)
        assert match is None, (
            f"{path.name}: query SQL hace referencia a `equipos.marca`, "
            f"columna dropeada por d5a8f2c4b6e9.\n"
            f"Patrón: {pat.pattern}\n"
            f"Match:  {match.group()[:200]}\n"
            f"Usar `MARCA_SUBQUERY` de database.py."
        )


# ── Regresión #504: no queda código apuntando a fichas_tecnicas/raw_json ─


def test_no_referencia_tabla_fichas_tecnicas():
    """La tabla `fichas_tecnicas` nunca existió — la real es `equipo_fichas`."""
    for path in ROUTES_DIR.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        # Aceptamos menciones en comentarios (`# fichas_tecnicas`), pero
        # no en strings SQL.
        sin_comentarios = re.sub(r"#.*$", "", content, flags=re.MULTILINE)
        assert "fichas_tecnicas" not in sin_comentarios, (
            f"{path.name}: referencia a tabla inexistente `fichas_tecnicas`. "
            f"La real es `equipo_fichas`."
        )


_RAW_JSON_RUNTIME_PATTERNS = [
    # Acceso a la columna desde un row de DB (causa KeyError o lectura inválida).
    re.compile(r"\[[\"']raw_json[\"']\]"),
    # SELECT/INSERT/UPDATE explícito de la columna.
    re.compile(r"\bSELECT\s[^()]*?\braw_json\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"\bINSERT[^()]*?\braw_json\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"\bUPDATE[^()]*?\braw_json\s*=", re.IGNORECASE | re.DOTALL),
]


def test_no_referencia_columna_raw_json():
    """`raw_json` fue dropeada en Fase E por la migración d7e9b3c5a8f2.
    Las menciones en docstrings (histórico, ej. "Fase E droppeó raw_json")
    son OK; lo que rompe es acceso runtime."""
    for path in ROUTES_DIR.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        for pat in _RAW_JSON_RUNTIME_PATTERNS:
            match = pat.search(content)
            assert match is None, (
                f"{path.name}: referencia runtime a columna dropeada `raw_json`.\n"
                f"Match: {match.group()[:120]}"
            )
