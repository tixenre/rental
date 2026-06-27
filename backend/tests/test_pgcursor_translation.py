"""Test adversarial del wrapper de DB (`database.core`): traducción `?`→`%s` + guardas.

Fija la conducta del chokepoint único por donde pasan TODAS las queries:
  - traducción `?`→`%s`, y coexistencia con `%s` ya nativo (string mixto, caso real
    de `routes/inventario.py`);
  - guarda `_assert_pct_safe`: un `%` literal en el SQL (ej. `LIKE '%x%'` inline) falla
    fuerte en vez de corromper la query en silencio;
  - guarda `_assert_params_present`: placeholders sin `params` falla fuerte (agnóstica
    de paramstyle: cubre `?` Y `%s`);
  - `executemany` ahora valida (antes no chequeaba nada — bug de asimetría);
  - `insert_returning` agrega el `RETURNING` y devuelve el id (reemplazo de `lastrowid`).

No necesita Postgres: usa un cursor/conexión fake. Es el "simular" del workflow —
inyecta patrones malos para VER las guardas fallar, no sólo el happy path.
"""
import pytest

from database.core import (
    PGConnection,
    _assert_params_present,
    _assert_pct_safe,
)

pytestmark = pytest.mark.unit


# ── Doble de cursor/conexión (sin Postgres) ──────────────────────────────────

class _FakeCursor:
    def __init__(self):
        self.executed = []        # [(sql, params), ...] — lo que llegó a psycopg
        self.description = [("id",)]
        self._rows = [(42,)]

    def execute(self, sql, params=()):
        self.executed.append((sql, params))

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


class _FakeConn:
    def __init__(self):
        self.cur = _FakeCursor()

    def cursor(self, *a, **k):
        return self.cur

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def _conn():
    return PGConnection(_FakeConn())


def _last_sql(conn):
    return conn.raw_conn.cur.executed[-1][0]


# ── _assert_pct_safe: el `%` sólo es válido como placeholder o `%%` ──────────

@pytest.mark.parametrize("sql", [
    "SELECT 1",                                  # sin %
    "SELECT * FROM t WHERE id = %s",             # placeholder posicional
    "SELECT * FROM t WHERE id = %(uid)s",        # placeholder nombrado
    "SELECT '50%%' AS pct",                      # % escapado
    "SELECT id, %s FROM t WHERE a IN (%s,%s)",   # varios %s (builder real)
])
def test_pct_safe_acepta_validos(sql):
    _assert_pct_safe(sql)   # no debe levantar


@pytest.mark.parametrize("sql", [
    "SELECT * FROM t WHERE nombre LIKE '%foo%'",  # comodín literal (va en params)
    "SELECT 5 % 2",                               # módulo desnudo (psycopg pide %%)
    "SELECT '50%' AS pct",                        # % suelto
])
def test_pct_safe_rechaza_literal(sql):
    with pytest.raises(ValueError):
        _assert_pct_safe(sql)


# ── _assert_params_present: placeholders sin params = bug del caller ─────────

@pytest.mark.parametrize("sql", [
    "SELECT * FROM t WHERE id = ?",
    "SELECT * FROM t WHERE id = %s",
    "SELECT * FROM t WHERE id = %(uid)s",
])
def test_params_present_rechaza_sin_params(sql):
    with pytest.raises(ValueError):
        _assert_params_present(sql, ())


def test_params_present_ok():
    _assert_params_present("WHERE id = ?", (1,))   # con params: ok
    _assert_params_present("SELECT 1", ())          # sin placeholders: ok


# ── Traducción y coexistencia `?` + `%s` ─────────────────────────────────────

def test_traduce_qmark_a_pyformat():
    conn = _conn()
    conn.execute("SELECT * FROM t WHERE id = ? AND x = ?", (1, 2))
    assert _last_sql(conn) == "SELECT * FROM t WHERE id = %s AND x = %s"


def test_string_mixto_qmark_y_pyformat_no_se_rechaza():
    # Caso real (inventario.py): `?` y `%s` conviviendo. Debe pasar → todo %s.
    conn = _conn()
    conn.execute("UPDATE t SET a = ? WHERE id IN (%s, %s)", ("v", 1, 2))
    assert _last_sql(conn) == "UPDATE t SET a = %s WHERE id IN (%s, %s)"


def test_pyformat_nativo_pasa_intacto():
    conn = _conn()
    conn.execute("SELECT * FROM t WHERE id = %s", (1,))
    assert _last_sql(conn) == "SELECT * FROM t WHERE id = %s"


def test_execute_rechaza_literal_pct():
    conn = _conn()
    with pytest.raises(ValueError):
        conn.execute("SELECT * FROM t WHERE n LIKE '%foo%' AND id = ?", (1,))


def test_execute_rechaza_placeholder_sin_params():
    conn = _conn()
    with pytest.raises(ValueError):
        conn.execute("SELECT * FROM t WHERE id = ?")


def test_execute_rechaza_no_string():
    conn = _conn()
    with pytest.raises(TypeError):
        conn.execute(123)


# ── executemany (antes no validaba nada) ─────────────────────────────────────

def test_executemany_traduce():
    conn = _conn()
    conn.executemany("INSERT INTO t (a) VALUES (?)", [("x",), ("y",)])
    assert _last_sql(conn) == "INSERT INTO t (a) VALUES (%s)"


def test_executemany_rechaza_literal_pct():
    conn = _conn()
    with pytest.raises(ValueError):
        conn.executemany("INSERT INTO t (a) VALUES ('%x')", [()])


# ── insert_returning: reemplazo idiomático de lastrowid ──────────────────────

def test_insert_returning_agrega_clause_y_devuelve_id():
    conn = _conn()
    rid = conn.insert_returning("INSERT INTO t (a) VALUES (?)", ("x",))
    assert _last_sql(conn) == "INSERT INTO t (a) VALUES (%s) RETURNING id"
    assert rid == 42


def test_insert_returning_valida_column():
    conn = _conn()
    with pytest.raises(ValueError):
        conn.insert_returning("INSERT INTO t (a) VALUES (?)", ("x",),
                              column="id; DROP TABLE t")


# ── Limitación documentada: `?` dentro de un string literal ──────────────────

def test_limitacion_qmark_en_string_literal():
    # BLIND SPOT conocido (0 casos activos): el `replace` es ciego a un `?` dentro
    # de un string literal → lo traduce igual. Se fija para hacerlo VISIBLE, no
    # para bendecirlo. Desaparece en Fase 6 cuando se borra la traducción.
    conn = _conn()
    conn.execute("SELECT * FROM t WHERE nota = 'a?b' AND id = ?", ("a?b", 1))
    assert _last_sql(conn) == "SELECT * FROM t WHERE nota = 'a%sb' AND id = %s"
