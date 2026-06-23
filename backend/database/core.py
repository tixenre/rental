"""
database.py — Conexión PostgreSQL con pool de conexiones, migraciones y helpers.
"""

import logging
import pathlib
import psycopg2
import psycopg2.extras
import psycopg2.pool

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
#     conn.execute(f"... WHERE LOWER(COALESCE({MARCA_NOMBRE_EXPR}, '')) = LOWER(?) ...")
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
    """Parse DATABASE_URL a parámetros de psycopg2."""
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
# ThreadedConnectionPool es thread-safe (FastAPI corre handlers sync en threads).
#
# CLAVE: `maxconn` tiene que cubrir la concurrencia real de requests. FastAPI
# corre cada handler sync en el threadpool de Starlette (default 40 threads),
# y cada uno toma una conexión del pool. Si más de `maxconn` handlers corren a
# la vez, psycopg2 NO espera: lanza `PoolError: connection pool exhausted` al
# instante → 500 en cascada. Por eso el arranque (main.py) ACOTA el threadpool
# a `pool_max()` menos un margen para workers de fondo (scheduler, init,
# webhooks async): así los requests de más hacen cola en vez de explotar.
# Ambos valores se tunean por env (DB_POOL_MIN / DB_POOL_MAX) sin tocar código.
import os as _os

_POOL_MIN = int(_os.getenv("DB_POOL_MIN", "2"))
_POOL_MAX = int(_os.getenv("DB_POOL_MAX", "25"))

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def pool_max() -> int:
    """Techo de conexiones del pool (para que main.py acote el threadpool)."""
    return _POOL_MAX


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        _pool = psycopg2.pool.ThreadedConnectionPool(_POOL_MIN, _POOL_MAX, **get_connection_params())
    return _pool


# ── Cursor wrapper para compatibilidad con sqlite3 ───────────────────────────
# El proyecto migró de SQLite a PostgreSQL. Para no reescribir cientos de
# queries, este wrapper traduce los placeholders `?` (sqlite3) a `%s` (psycopg2)
# y emula `lastrowid` con `SELECT lastval()`. Convención del codebase: usar `?`
# en TODAS las queries para que la traducción sea consistente.
# Si en el futuro se quiere migrar a `%s` nativo, hay que hacerlo archivo por
# archivo con tests, no con un sed global (hay `?` en regex y URLs que no se
# deben tocar — ver `routes/equipos.py:1817`, `:2073`, `routes/auth.py`).

class PGCursor:
    """Wrapper que permite acceder a resultados por índice O por nombre."""
    def __init__(self, raw_cursor):
        self.raw_cursor = raw_cursor

    def execute(self, sql, params=()):
        # Validación defensiva: si el SQL tiene `?` pero `params` está vacío,
        # eso es muy probablemente un bug del caller (olvidó pasar el tuple).
        # Antes el `replace` igual procedía y psycopg2 fallaba con un error
        # críptico ("syntax error at or near %s"). Ahora avisamos claro.
        if not isinstance(sql, str):
            raise TypeError(f"execute() recibió SQL no-string: {type(sql).__name__}")
        if '?' in sql and not params:
            raise ValueError(
                f"SQL tiene placeholders `?` pero `params` está vacío. "
                f"SQL: {sql[:100]!r}"
            )
        sql = sql.replace('?', '%s')
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
    """Envoltura de psycopg2 que simula interfaz sqlite3 para migración fácil."""

    def __init__(self, raw_conn, pool=None):
        self.raw_conn = raw_conn
        self.row_factory = None
        self._pool = pool   # Si viene del pool, close() devuelve en lugar de cerrar

    def execute(self, sql, params=()):
        """Ejecuta una query y retorna un cursor tipo sqlite3."""
        if not isinstance(sql, str):
            raise TypeError(f"execute() recibió SQL no-string: {type(sql).__name__}")
        if '?' in sql and not params:
            raise ValueError(
                f"SQL tiene placeholders `?` pero `params` está vacío. "
                f"SQL: {sql[:100]!r}"
            )
        cur = self.raw_conn.cursor()
        # Convertir placeholders de ? (sqlite3) a %s (psycopg2)
        sql = sql.replace('?', '%s')
        cur.execute(sql, params)
        return PGCursor(cur)

    def executemany(self, sql, params_list):
        """Ejecuta una query con múltiples filas de parámetros."""
        if not isinstance(sql, str):
            raise TypeError(f"executemany() recibió SQL no-string: {type(sql).__name__}")
        cur = self.raw_conn.cursor()
        sql = sql.replace('?', '%s')
        for params in params_list:
            cur.execute(sql, params)
        return PGCursor(cur)

    def cursor(self, cursor_factory=None):
        """Retorna un cursor (envuelto para compatibilidad)."""
        if cursor_factory is not None:
            return PGCursor(self.raw_conn.cursor(cursor_factory=cursor_factory))
        return PGCursor(self.raw_conn.cursor())

    def commit(self):
        self.raw_conn.commit()

    def rollback(self):
        self.raw_conn.rollback()

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
