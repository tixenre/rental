"""Guard: cero placeholders `?` en SQL — psycopg3 usa `%s` nativo.

El driver es psycopg3 (migración #1084): el wrapper de conexión (`database/core.py`)
NO traduce `?`→`%s`. Cualquier `?` en una query pasada a `conn.execute` rompe en
runtime ("0 placeholders but N params") — y los tests con FakeConn NO lo cazan,
así que este guard estático es la red.

Detecta el patrón de placeholder SQL (`= ?`, `LIKE ?`, `IN (?`, `(?, ?)`, etc.)
dentro de string literals (vía AST → comentarios y otros `?` no-SQL quedan fuera).
Si reaparece un `?` SQL (típico: un PR que ramificó antes de la migración y revirtió
un `%s`), este test falla y obliga a volver a `%s`.

Excluye: `database/core.py` (el wrapper, que documenta el patrón), `tests/`, y
`migrations/` (Alembic corre SQL aparte). También `.venv/`/`venv/` — sin esto, un
`.venv` local dentro de `backend/` hace que el walk parsee paquetes de terceros
instalados y dispare falsos positivos (nunca pasa en CI, que instala las deps
globales sin un venv anidado ahí).
"""
import ast
import os
import re

import pytest

pytestmark = pytest.mark.unit

# Posiciones inequívocas de placeholder `?` en SQL.
_SQL_QMARK = re.compile(
    r"= \?|!= \?|<> \?|<= \?|>= \?|< \?|> \?|IN \(\?|VALUES \(\?|\(\?,|"
    r"\?, ?\?|, \?|LIKE \?|\(\?\)|word_similarity\(\?"
)

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SKIP = ("/tests/", "/migrations/", "database/core.py", "/.venv/", "/venv/")


def _literal_texts(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.JoinedStr):
        return [
            v.value for v in node.values
            if isinstance(v, ast.Constant) and isinstance(v.value, str)
        ]
    return []


def _archivos_py():
    for dp, _, files in os.walk(_BACKEND):
        if any(s in dp for s in _SKIP):
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            p = os.path.join(dp, f)
            if any(s in p for s in _SKIP):
                continue
            yield p


def test_cero_placeholders_qmark_en_sql():
    """Ningún string SQL del backend usa `?` (debe ser `%s` — psycopg3)."""
    ofensores = []
    for path in _archivos_py():
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            for txt in _literal_texts(node):
                if _SQL_QMARK.search(txt):
                    rel = os.path.relpath(path, _BACKEND)
                    ofensores.append(f"{rel}:{node.lineno}: {txt.strip()[:70]}")
    assert not ofensores, (
        "Placeholders `?` en SQL (psycopg3 usa `%s` — el wrapper no traduce). "
        "Convertí a `%s`:\n" + "\n".join(ofensores)
    )
