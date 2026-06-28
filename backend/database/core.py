"""
database.py — Conexión PostgreSQL con pool de conexiones, migraciones y helpers.
"""

import logging
import pathlib
import re
from contextlib import contextmanager

import psycopg
import psycopg.errors
from psycopg_pool import ConnectionPool

from config import settings

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    _BASE = pathlib.Path(__file__).parent.parent  # backend/ (database/ es paquete, #501)
    for _name in (".env.local", ".env"):
        _f = _BASE / _name
        if _f.exists():
            load_dotenv(_f, override=False)
except ImportError:
    pass

# ── Paths ────────────────────────────────────────────────────────────────────

BASE = pathlib.Path(__file__).parent
# El frontend vive en `frontend/` en la RAÍZ del repo (simétrico a `backend/`).
# En Docker el Dockerfile hace `COPY --from=frontend /app/dist ./frontend/dist`
# y `COPY frontend/src/assets/fonts ./frontend/src/assets/fonts`. `database/` es
# un paquete (#501) → desde `database/core.py` hay que subir DOS niveles
# (database/ → backend/ → raíz). Antes era `backend/database.py` y alcanzaba un
# nivel; el split lo bajó uno → prod servía "Frontend not built" porque apuntaba
# a `backend/dist`. (Regresión del split, hotfix.)
FRONT = BASE.parent.parent / "frontend" / "public"
# SPA Vite (rental-refine) — compilado en `frontend/dist`.
FRONT_NEW = BASE.parent.parent / "frontend" / "dist"

# ── Fragmentos SQL canónicos ─────────────────────────────────────────────────
#
# Fase 0 de #501: la migración d5a8f2c4b6e9 dropeó `equipos.marca` (TEXT). El
# nombre de la marca se resuelve por subquery contra `marcas.nombre` vía
# `e.brand_id`. Esta subquery aparecía copiada literal en >15 lugares y algunos
# quedaron sin migrar → 500s (#499). El helper único acá garantiza que cualquier
# query nueva use la forma correcta y que "que no se repita el olvido".
#
# Uso (la convención es aliasar `equipos` como `e`):
#     conn.execute(f"SELECT e.id, e.nombre, {MARCA_SUBQUERY} FROM equipos e ...")
# Para predicados en WHERE/COALESCE:
#     conn.execute(f"... WHERE LOWER(COALESCE({MARCA_NOMBRE_EXPR}, '')) = LOWER(%s) ...", (valor,))
# Cuando el equipo va con OTRO alias (ej. `ec` para componentes de combo/kit, o
# la tabla `equipos` sin aliasar), pasar el alias al helper:
#     f"SELECT ec.nombre, {marca_subquery('ec')} FROM ... equipos ec ..."
#     f"SELECT id, {marca_subquery('equipos')} FROM equipos WHERE id = %s"


def marca_nombre_expr(alias: str = "e") -> str:
    """Subquery que resuelve `marcas.nombre` por `<alias>.brand_id` (sin `AS`)."""
    return f"(SELECT nombre FROM marcas WHERE id = {alias}.brand_id)"


def marca_subquery(alias: str = "e") -> str:
    """`marca_nombre_expr(alias)` con `AS marca` — para la lista de SELECT."""
    return f"{marca_nombre_expr(alias)} AS marca"


# Constantes para el caso por defecto (alias `e`), las más usadas.
MARCA_NOMBRE_EXPR = marca_nombre_expr()
MARCA_SUBQUERY = marca_subquery()


# ── Config BD desde variables de entorno ─────────────────────────────────────

DATABASE_URL = settings.DATABASE_URL

if not DATABASE_URL:
    # Fallback local (para desarrollo sin Railway)
    DATABASE_URL = "postgresql://postgres:postgres@localhost/rambla_rental"


def get_connection_params():
    """Parse DATABASE_URL a parámetros de conexión (host/port/user/password/database)."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(DATABASE_URL)
        return {
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 5432,
            'user': parsed.username or 'postgres',
            'password': parsed.password or 'postgres',
            'database': parsed.path.lstrip('/') or 'rambla_rental',
        }
    except Exception as e:
        logger.error("Error parsing DATABASE_URL: %s", e, exc_info=True)
        raise


# ── Pool de conexiones ────────────────────────────────────────────────────────
# psycopg_pool.ConnectionPool es thread-safe (FastAPI corre handlers sync en threads).
#
# CLAVE: `max_size` tiene que cubrir la concurrencia real de requests. FastAPI
# corre cada handler sync en el threadpool de Starlette (default 40 threads),
# y cada uno toma una conexión del pool. Si más de `max_size` handlers corren
# a la vez, psycopg_pool espera hasta `timeout` segundos (default 30s) antes
# de lanzar `PoolTimeout` → 500. Por eso el arranque (main.py) ACOTA el
# threadpool a `pool_max()` menos un margen para workers de fondo (scheduler,
# init, webhooks async): así los requests de más hacen cola en vez de explotar.
# Ambos valores se tunean por env (DB_POOL_MIN / DB_POOL_MAX) sin tocar código.
#
# `DB_POOL_TIMEOUT` (segundos): tope que `getconn()` espera por una conexión
# libre. Default 30s en prod a propósito (ver arriba: los requests de más hacen
# cola en vez de explotar). En el job `python-tests` de CI NO hay Postgres y los
# tests de contrato golpean handlers reales a propósito (verifican ruteo/guards,
# aceptan un 500) → sin este knob cada request colgaba los 30s del timeout antes
# de devolver el 500, y eran ~150 requests = ~38 min. conftest.py lo baja a 1s
# cuando no hay DATABASE_URL (job sin DB real): el 500 sale igual, pero al toque.
import os as _os

_POOL_MIN = int(_os.getenv("DB_POOL_MIN", "2"))
_POOL_MAX = int(_os.getenv("DB_POOL_MAX", "25"))
_POOL_TIMEOUT = float(_os.getenv("DB_POOL_TIMEOUT", "30"))

_pool: ConnectionPool | None = None


def pool_max() -> int:
    """Techo de conexiones del pool (para que main.py acote el threadpool)."""
    return _POOL_MAX


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        # ClientCursor: sustitución client-side (= psycopg2) → None→NULL literal,
        # sin IndeterminateDatatype. Clave para la migración desde psycopg2.
        _pool = ConnectionPool(
            DATABASE_URL,
            min_size=_POOL_MIN,
            max_size=_POOL_MAX,
            timeout=_POOL_TIMEOUT,
            kwargs={"cursor_factory": psycopg.ClientCursor},
            open=True,
        )
    return _pool


# ── Guardas de seguridad SQL ─────────────────────────────────────────────────
# Todo el código usa `%s` nativo de psycopg (migración de `?` completada).
# Las guardas `_assert_params_present` + `_assert_pct_safe` enforcan:
#   · Todo VALOR va como bound param (no f-strings ni concatenación).
#   · El único `%` permitido es placeholder (`%s`/`%(name)s`) o `%%`.
#   · Un `%` literal (ej. `LIKE '%x%'` inline) es un bug → comodín en params.

# Un `%` es válido sólo si abre un placeholder (`%s`, `%(name)s`) o es `%%`.
_VALID_PCT = re.compile(r"%(?:s|%|\([A-Za-z_]\w*\)s)")
# Placeholders nativos psycopg (`%s` / `%(name)s`).
_HAS_PLACEHOLDER = re.compile(r"%s|%\([A-Za-z_]\w*\)s")


def _assert_pct_safe(sql: str) -> None:
    """Rechaza un `%` que no sea un placeholder válido (`%s`/`%(name)s`/`%%`).

    El wrapper siempre pasa una tupla de params → psycopg corre pyformat → un `%`
    desnudo ya falla hoy con un error críptico. Esta guarda lo caza antes, con un
    mensaje claro: el comodín de `LIKE` va en el param, nunca literal en el SQL.
    Paramstyle-agnóstica → sobrevive a la migración `?`→`%s`.
    """
    i = sql.find("%")
    while i != -1:
        m = _VALID_PCT.match(sql, i)
        if m is None:
            raise ValueError(
                f"`%` que no es placeholder válido en el SQL (usá %s / %%; "
                f"el comodín de LIKE va en params). SQL: {sql[:120]!r}"
            )
        i = sql.find("%", m.end())


def _assert_params_present(sql: str, params) -> None:
    """Si el SQL tiene placeholders (`%s`/`%(name)s`) pero `params` está vacío,
    casi seguro el caller olvidó la tupla. Avisa claro en vez del error críptico
    de psycopg."""
    if not params and _HAS_PLACEHOLDER.search(sql):
        raise ValueError(
            f"SQL tiene placeholders pero `params` está vacío "
            f"(¿olvidaste la tupla?). SQL: {sql[:120]!r}"
        )


class PGCursor:
    """Wrapper que permite acceder a resultados por índice O por nombre."""
    def __init__(self, raw_cursor):
        self.raw_cursor = raw_cursor

    def execute(self, sql: str, params=()):
        if not isinstance(sql, str):
            raise TypeError(f"execute() recibió SQL no-string: {type(sql).__name__}")
        _assert_params_present(sql, params)
        _assert_pct_safe(sql)
        return self.raw_cursor.execute(sql, params)

    @property
    def lastrowid(self):
        """Equivalente a sqlite3 lastrowid — usa SELECT lastval() de PostgreSQL."""
        try:
            cur = self.raw_cursor.connection.cursor()
            cur.execute("SELECT lastval()")
            result = cur.fetchone()
            cur.close()
            return result[0] if result else None
        except Exception:
            return None

    def fetchone(self):
        """Retorna Row que se puede acceder por [0] o ['name']."""
        row = self.raw_cursor.fetchone()
        if row is None:
            return None
        return PGRow(row, self.raw_cursor.description)

    def scalar(self):
        """Retorna el primer valor de la primera fila (o None si no hay filas)."""
        row = self.raw_cursor.fetchone()
        return row[0] if row is not None else None

    def fetchall(self):
        """Retorna lista de Rows."""
        rows = self.raw_cursor.fetchall()
        if not rows:
            return []
        return [PGRow(row, self.raw_cursor.description) for row in rows]

    def close(self):
        self.raw_cursor.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class PGRow:
    """Row que se puede acceder por [0] (tuple-style) o ['name'] (dict-style)."""
    def __init__(self, data, description):
        self.data = data
        self.description = description
        self.col_names = {desc[0]: i for i, desc in enumerate(description)} if description else {}

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.data[key]
        return self.data[self.col_names[key]]

    def __iter__(self):
        return iter(self.data)

    def keys(self):
        return self.col_names.keys()


# ── Wrapper para compatibilidad con sqlite3 ─────────────────────────────────

class PGConnection:
    """Envoltura del pool de psycopg3: aísla la infra (pool, rollback, guardas) del resto."""

    def __init__(self, raw_conn, pool=None):
        self.raw_conn = raw_conn
        self.row_factory = None
        self._pool = pool   # Si viene del pool, close() devuelve en lugar de cerrar

    def execute(self, sql: str, params=()) -> "PGCursor":
        """Ejecuta una query y retorna un cursor tipo sqlite3."""
        if not isinstance(sql, str):
            raise TypeError(f"execute() recibió SQL no-string: {type(sql).__name__}")
        _assert_params_present(sql, params)
        _assert_pct_safe(sql)
        cur = self.raw_conn.cursor()
        cur.execute(sql, params)
        return PGCursor(cur)

    def executemany(self, sql: str, params_list) -> "PGCursor":
        """Ejecuta una query con múltiples filas de parámetros."""
        if not isinstance(sql, str):
            raise TypeError(f"executemany() recibió SQL no-string: {type(sql).__name__}")
        _assert_pct_safe(sql)   # (paridad con execute; antes executemany no validaba nada)
        cur = self.raw_conn.cursor()
        for params in params_list:
            cur.execute(sql, params)
        return PGCursor(cur)

    def cursor(self, cursor_factory=None):
        """Retorna un cursor (envuelto para compatibilidad). `cursor_factory` ignorado (sin callers)."""
        return PGCursor(self.raw_conn.cursor())

    def commit(self):
        self.raw_conn.commit()

    def rollback(self):
        self.raw_conn.rollback()

    @contextmanager
    def transaction(self):
        """Context manager de transacción: commit al salir OK, rollback ante
        excepción. NO cierra la conexión (a diferencia de `with conn:` en
        psycopg3). Reemplaza el patrón manual try / commit / except / rollback."""
        try:
            yield self
            self.raw_conn.commit()
        except Exception:
            self.raw_conn.rollback()
            raise

    def insert_returning(self, sql: str, params=(), *, column: str = "id"):
        """Ejecuta un `INSERT … RETURNING <column>` y devuelve el valor —
        reemplazo idiomático de `lastrowid`. `sql` NO debe traer el RETURNING (se
        agrega). `column` es un identificador del esquema (no acepta input de
        usuario); se valida para descartar interpolación insegura."""
        if not column.isidentifier():
            raise ValueError(f"column inválida para RETURNING: {column!r}")
        row = self.execute(f"{sql} RETURNING {column}", params).fetchone()
        return row[0] if row is not None else None

    def close(self):
        if self._pool:
            # Limpiar la transacción pendiente ANTES de devolver la conexión al
            # pool. Sin esto, una query que falló deja la conexión en estado
            # "transacción abortada"; al reusarla, el próximo request (no
            # relacionado) falla con "current transaction is aborted, commands
            # ignored until end of transaction block" → 500 en cascada. El
            # rollback es inocuo tras un commit (no-op) y en reads cierra la
            # transacción implícita.
            try:
                self.raw_conn.rollback()
            except Exception:
                pass
            self._pool.putconn(self.raw_conn)   # devuelve al pool en lugar de cerrar
        else:
            self.raw_conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ── Helpers de conexión ──────────────────────────────────────────────────────

def get_db():
    """Toma una conexión del pool y la retorna con interfaz compatible sqlite3."""
    pool = _get_pool()
    raw_conn = pool.getconn()
    return PGConnection(raw_conn, pool=pool)


def row_to_dict(row) -> dict:
    """Convierte una fila a dict."""
    if isinstance(row, dict):
        return row
    return dict(row)


def to_datetime(v):
    """Coacciona a `datetime`. Acepta str ISO, `date`, `datetime` o None.

    Las columnas de fecha pasaron de TEXT a TIMESTAMP/DATE, así que psycopg
    devuelve objetos `datetime`/`date` en vez de strings. Los request bodies
    siguen llegando como strings ISO. Este helper neutraliza ambos casos."""
    from datetime import date as _date, datetime as _dt
    if v is None or v == "":
        return None
    if isinstance(v, _dt):
        return v
    if isinstance(v, _date):
        return _dt(v.year, v.month, v.day)
    return _dt.fromisoformat(str(v))


def now_ar():
    """Ahora en hora de Buenos Aires (UTC-3, sin horario de verano), como
    `datetime` naive. Las fechas de los pedidos se guardan/comparan como
    wall-clock de AR, así que el "ahora" para chequear pasado/ventanas debe
    estar en la misma zona — independiente de la TZ del server (que en la nube
    suele ser UTC)."""
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    return _dt.now(_tz(_td(hours=-3))).replace(tzinfo=None)


def to_iso(v) -> str | None:
    """Coacciona a string ISO. None/'' → None. Acepta str, `date`, `datetime`."""
    if v is None or v == "":
        return None
    iso = getattr(v, "isoformat", None)
    return iso() if callable(iso) else str(v)
