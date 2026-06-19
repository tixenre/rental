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
    _BASE = pathlib.Path(__file__).parent
    for _name in (".env.local", ".env"):
        _f = _BASE / _name
        if _f.exists():
            load_dotenv(_f, override=False)
except ImportError:
    pass

# ── Paths ────────────────────────────────────────────────────────────────────

BASE = pathlib.Path(__file__).parent
# Frontend clásico (admin, login, etc.)
FRONT = BASE.parent / "frontend" / "public"
# Nuevo frontend (rental-refine, Vite SPA) — compilado en la raíz
FRONT_NEW = BASE.parent / "dist"

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


# ── Helpers de equipos ─────────────────────────────────────────────────────

def attach_tags(conn, equipos: list[dict]) -> list[dict]:
    """Agrega etiquetas a la lista de equipos (ordenadas por `orden`)."""
    if not equipos:
        return equipos

    ids = [e["id"] for e in equipos]
    placeholders = ",".join(["%s"] * len(ids))

    cur = conn.cursor()
    cur.execute(f"""
        SELECT ee.equipo_id, et.nombre, et.prioridad
        FROM equipo_etiquetas ee
        JOIN etiquetas et ON et.id = ee.etiqueta_id
        WHERE ee.equipo_id IN ({placeholders})
        ORDER BY ee.equipo_id, ee.orden
    """, ids)

    rows = cur.fetchall()
    tag_map: dict[int, list] = {e["id"]: [] for e in equipos}

    for r in rows:
        tag_map[r["equipo_id"]].append(r["nombre"])

    for e in equipos:
        e["etiquetas"] = tag_map[e["id"]]

    cur.close()
    return equipos


def attach_kit(conn, equipos: list[dict]) -> list[dict]:
    """Agrega componentes de kit a la lista de equipos."""
    if not equipos:
        return equipos

    ids = [e["id"] for e in equipos]
    placeholders = ",".join(["%s"] * len(ids))

    cur = conn.cursor()
    cur.execute(f"""
        SELECT kc.equipo_id, kc.componente_id, kc.cantidad,
               kc.descuento_pct, kc.esencial,
               e.nombre, {MARCA_SUBQUERY}, e.foto_url
        FROM kit_componentes kc
        JOIN equipos e ON e.id = kc.componente_id AND e.eliminado_at IS NULL
        WHERE kc.equipo_id IN ({placeholders})
        ORDER BY kc.equipo_id, kc.orden ASC, e.nombre ASC
    """, ids)

    rows = cur.fetchall()
    kit_map: dict[int, list] = {e["id"]: [] for e in equipos}

    for r in rows:
        kit_map[r["equipo_id"]].append({
            "componente_id": r["componente_id"],
            "nombre":        r["nombre"],
            "marca":         r["marca"],
            "foto_url":      r["foto_url"],
            "cantidad":      r["cantidad"],
            "descuento_pct": r["descuento_pct"],
            "esencial":      r["esencial"],
        })

    for e in equipos:
        e["kit"] = kit_map[e["id"]]

    cur.close()
    return equipos


def attach_categorias(conn, equipos: list[dict]) -> list[dict]:
    """Agrega `categorias` (lista de {id, nombre, parent_id}) a cada equipo."""
    if not equipos:
        return equipos
    ids = [e["id"] for e in equipos]
    placeholders = ",".join(["%s"] * len(ids))
    cur = conn.cursor()
    cur.execute(f"""
        SELECT ec.equipo_id, c.id, c.nombre, c.parent_id
        FROM equipo_categorias ec
        JOIN categorias c ON c.id = ec.categoria_id
        WHERE ec.equipo_id IN ({placeholders})
        ORDER BY ec.equipo_id, ec.orden
    """, ids)
    rows = cur.fetchall()
    cat_map: dict[int, list] = {e["id"]: [] for e in equipos}
    for r in rows:
        cat_map[r["equipo_id"]].append({
            "id": r["id"], "nombre": r["nombre"], "parent_id": r["parent_id"],
        })
    for e in equipos:
        e["categorias"] = cat_map[e["id"]]
    cur.close()
    return equipos


def attach_ficha(conn, equipos: list[dict]) -> list[dict]:
    """Agrega la ficha textual (descripcion, notas, keywords, enriquecimiento
    extra). Las specs estructuradas viven en `equipo_specs` y se atachan
    vía `attach_specs_estructuradas`.

    Post-Fase F: montura/formato/resolucion/peso/dimensiones/alimentacion
    fueron droppeadas — esos campos son specs en equipo_specs.
    Post-Fase E: specs_json y raw_json fueron droppeados.
    """
    if not equipos:
        return equipos
    ids = [e["id"] for e in equipos]
    placeholders = ",".join(["%s"] * len(ids))
    cur = conn.cursor()
    cur.execute(f"""
        SELECT equipo_id, descripcion, notas,
               keywords_json, nombre_publico_template,
               incluye_json, conectividad_json, compatible_con_json,
               video_url, precio_bh_usd, fuente_url, fuente_titulo,
               enriquecido_at, enriquecido_fuente,
               contenido_incluido_json
        FROM equipo_fichas
        WHERE equipo_id IN ({placeholders})
    """, ids)
    rows = cur.fetchall()
    _ficha_keys = (
        "descripcion", "notas",
        "keywords_json", "nombre_publico_template",
        "incluye_json", "conectividad_json", "compatible_con_json",
        "video_url", "precio_bh_usd", "fuente_url", "fuente_titulo",
        "enriquecido_at", "enriquecido_fuente",
        "contenido_incluido_json",
    )
    f_map: dict[int, dict] = {}
    for r in rows:
        f_map[r["equipo_id"]] = {k: r[k] for k in _ficha_keys}
    _empty = {k: None for k in _ficha_keys}
    for e in equipos:
        e["ficha"] = f_map.get(e["id"]) or dict(_empty)
    cur.close()
    return equipos


def attach_specs_destacados(conn, equipos: list[dict]) -> list[dict]:
    """Agrega `specs_destacados` a cada equipo: lista [{label, value}] de las
    specs con sd.favorito=true en spec_definitions."""
    if not equipos:
        return equipos
    from services.spec_render import render_spec_value
    ids = [e["id"] for e in equipos]
    placeholders = ",".join(["%s"] * len(ids))
    cur = conn.cursor()
    # Para destacadas de tipo bool, solo emitir cuando el valor es "Sí"/true.
    # Una spec "Macro: No" no aporta como quick fact en la card — destacar
    # solo cuando el lente ES macro, no cuando no lo es.
    cur.execute(f"""
        SELECT es.equipo_id, sd.label, sd.tipo, sd.unidad, es.value,
               COALESCE(sd.prioridad, 100) AS prioridad
        FROM equipo_specs es
        JOIN equipo_categorias ec ON ec.equipo_id = es.equipo_id
        JOIN spec_definitions sd ON sd.id = es.spec_def_id
        JOIN categoria_spec_templates t
            ON t.spec_def_id = es.spec_def_id
           AND t.categoria_id = ec.categoria_id
        WHERE COALESCE(sd.favorito, FALSE) = TRUE
          AND es.equipo_id IN ({placeholders})
          AND (
            sd.tipo != 'bool'
            OR LOWER(TRIM(es.value)) IN ('sí', 'si', 'yes', 'true', '1')
          )
        ORDER BY es.equipo_id, COALESCE(sd.prioridad, 100), sd.label
    """, ids)
    rows = cur.fetchall()
    cur.close()

    dest_map: dict[int, list[dict]] = {e["id"]: [] for e in equipos}
    seen: dict[int, set] = {e["id"]: set() for e in equipos}
    for r in rows:
        eid = r["equipo_id"]
        key = r["label"]
        if key not in seen[eid]:
            # Para bool, el value queda vacío — el frontend muestra solo el
            # label como badge (ej. "MACRO" en lugar de "MACRO Sí").
            # El resto pasa por el renderer canónico (mismo que el nombre
            # público) → "[24, 70]" mm → "24-70 mm", "[2.8]" f/ → "f/2.8".
            value = "" if r["tipo"] == "bool" else render_spec_value(
                r["value"], r["tipo"], r["unidad"]
            )
            dest_map[eid].append({"label": r["label"], "value": value})
            seen[eid].add(key)

    for e in equipos:
        e["specs_destacados"] = dest_map[e["id"]]
    return equipos


def attach_specs_estructuradas(conn, equipos: list[dict]) -> list[dict]:
    """Agrega `specs` (dict) a cada equipo con TODAS las specs estructuradas
    desde equipo_specs JOIN spec_definitions JOIN categoria_spec_templates.

    Shape: {spec_key: {label, value, tipo, unidad, prioridad, en_card,
    destacado}}. El catálogo público lee esto en vez de las columnas
    legacy (montura/formato/specs_json) de equipo_fichas.

    Solo incluye specs cuyo `spec_def` esté asignado al template de
    alguna categoría del equipo (descartando orfanos cross-cat).
    Flags y prioridad vienen de spec_definitions (sd), no de categoria_spec_templates.
    """
    if not equipos:
        return equipos
    from services.spec_render import render_spec_value, _is_empty_value
    ids = [e["id"] for e in equipos]
    placeholders = ",".join(["%s"] * len(ids))
    cur = conn.cursor()
    cur.execute(f"""
        SELECT DISTINCT ON (es.equipo_id, sd.id)
            es.equipo_id, sd.spec_key, sd.label, sd.tipo, sd.unidad,
            es.value,
            COALESCE(sd.prioridad, 100) AS prioridad,
            COALESCE(sd.favorito, FALSE) AS en_card,
            COALESCE(sd.en_filtros, FALSE) AS en_filtros,
            COALESCE(sd.favorito, FALSE) AS destacado
        FROM equipo_specs es
        JOIN equipo_categorias ec ON ec.equipo_id = es.equipo_id
        JOIN spec_definitions sd ON sd.id = es.spec_def_id
        JOIN categoria_spec_templates t
            ON t.spec_def_id = es.spec_def_id
           AND t.categoria_id = ec.categoria_id
        WHERE es.equipo_id IN ({placeholders})
        ORDER BY es.equipo_id, sd.id, COALESCE(sd.prioridad, 100)
    """, ids)
    rows = cur.fetchall()
    cur.close()

    _BOOL_FALSE = frozenset({"false", "no", "0", "n", "falso", "off", "disabled"})

    specs_map: dict[int, dict[str, dict]] = {e["id"]: {} for e in equipos}
    for r in rows:
        eid = r["equipo_id"]
        key = r["spec_key"]
        if key in specs_map[eid]:
            continue  # dedup: mantenemos el de mayor prioridad (DISTINCT ON)
        raw_val: str | None = r["value"]
        # Omitir specs efectivamente vacías o bool-false: no aportan en la ficha.
        if _is_empty_value(raw_val):
            continue
        if r["tipo"] == "bool" and str(raw_val).lower().strip() in _BOOL_FALSE:
            continue
        value_display = render_spec_value(raw_val, r["tipo"], r["unidad"])
        if not value_display:
            continue
        specs_map[eid][key] = {
            "label": r["label"],
            # `value` queda CRUDO (lo usan los filtros públicos por specsRaw).
            # `value_display` es el render canónico (mismo que el nombre
            # público) para mostrar en la ficha — "[24,70]" mm → "24-70 mm".
            "value": raw_val,
            "value_display": value_display,
            "tipo": r["tipo"],
            "unidad": r["unidad"],
            "prioridad": r["prioridad"],
            "en_card": bool(r["en_card"]),
            "en_filtros": bool(r["en_filtros"]),
            "destacado": bool(r["destacado"]),
        }
    for e in equipos:
        e["specs"] = specs_map[e["id"]]
    return equipos


# ── Auto-tags: regenerar etiquetas derivadas (origen='auto') ────────────────
#
# Las etiquetas auto se sintetizan desde marca, modelo, palabras del nombre
# y nombres de cada categoría asignada (incluyendo padres del árbol).
# Sirven como índice de búsqueda libre. El admin puede agregar etiquetas
# manuales encima sin que se pisen.

import re as _re

_WORD_SPLIT = _re.compile(r"[^\wáéíóúñü]+", flags=_re.UNICODE)


def _auto_tags_from_parts(equipo: dict, categoria_nombres) -> list[str]:
    """Arma la lista de strings que deberían ser etiquetas auto a partir de los
    campos del equipo (marca/modelo/nombre) + los nombres de sus categorías (con
    ancestros, ya resueltos por el caller).

    Es la pieza ÚNICA de la regla de tagging: tanto el camino por-equipo
    (`_auto_tags_for_equipo`) como el batch (`regenerate_auto_tags_batch`) la
    usan, así no pueden divergir qué tags ve un equipo según el camino que lo
    procesó."""
    bag: list[str] = []

    def add(val):
        if not val:
            return
        s = str(val).strip().lower()
        if not s:
            return
        if s not in bag:
            bag.append(s)

    add(equipo.get("marca"))
    add(equipo.get("modelo"))
    # Palabras del nombre (descarta tokens muy cortos / numéricos sueltos).
    for word in _WORD_SPLIT.split(str(equipo.get("nombre") or "")):
        w = word.strip().lower()
        if len(w) >= 3 and not w.isdigit():
            add(w)

    # Nombres de categorías asignadas + sus padres (árbol completo hacia arriba).
    for nombre in categoria_nombres:
        add(nombre)

    return bag


def _auto_tags_for_equipo(conn, equipo: dict) -> list[str]:
    """Calcula la lista de strings que deberían ser etiquetas auto para un equipo."""
    # Nombres de categorías asignadas + sus padres (árbol completo hacia arriba).
    cat_rows = conn.execute("""
        WITH RECURSIVE up AS (
            SELECT c.id, c.nombre, c.parent_id
            FROM equipo_categorias ec
            JOIN categorias c ON c.id = ec.categoria_id
            WHERE ec.equipo_id = %s
            UNION
            SELECT p.id, p.nombre, p.parent_id
            FROM categorias p
            JOIN up ON up.parent_id = p.id
        )
        SELECT DISTINCT nombre FROM up
    """, (equipo["id"],)).fetchall()
    return _auto_tags_from_parts(equipo, [r["nombre"] for r in cat_rows])


def regenerate_auto_tags(conn, equipo_id: int) -> int:
    """
    Regenera las etiquetas `origen='auto'` para un equipo.
    No toca las `origen='manual'`. Devuelve cuántas auto-tags quedaron asignadas.
    """
    eq = conn.execute(
        f"SELECT id, nombre, {marca_subquery('equipos')}, modelo FROM equipos WHERE id = %s", (equipo_id,)
    ).fetchone()
    if not eq:
        return 0
    equipo = {"id": eq["id"], "nombre": eq["nombre"], "marca": eq["marca"], "modelo": eq["modelo"]}

    # 1) Borrar las auto actuales del equipo.
    conn.execute(
        "DELETE FROM equipo_etiquetas WHERE equipo_id = %s AND origen = 'auto'",
        (equipo_id,),
    )

    # 2) Calcular nuevas y asegurar que cada nombre exista en `etiquetas`.
    tags = _auto_tags_for_equipo(conn, equipo)
    count = 0
    for orden, name in enumerate(tags):
        # Upsert de la etiqueta (la tabla tiene UNIQUE(nombre)).
        conn.execute(
            "INSERT INTO etiquetas (nombre) VALUES (%s) ON CONFLICT (nombre) DO NOTHING",
            (name,),
        )
        row = conn.execute("SELECT id FROM etiquetas WHERE nombre = %s", (name,)).fetchone()
        if not row:
            continue
        # Insertar como auto. Si el admin ya tenía esta etiqueta como manual,
        # respetamos su origen (DO NOTHING).
        conn.execute("""
            INSERT INTO equipo_etiquetas (equipo_id, etiqueta_id, orden, origen)
            VALUES (%s, %s, %s, 'auto')
            ON CONFLICT (equipo_id, etiqueta_id) DO NOTHING
        """, (equipo_id, row["id"], orden))
        count += 1

    # Limpiar etiquetas que ya no las usa ningún equipo (ni manual ni auto).
    # `etiquetas` no tiene columna `origen` — el origen vive en `equipo_etiquetas`.
    conn.execute("""
        DELETE FROM etiquetas
        WHERE id NOT IN (SELECT DISTINCT etiqueta_id FROM equipo_etiquetas)
    """)

    return count


# Tamaño de tanda del batch: acota cuántos equipos se cargan a memoria y cuántos
# parámetros viajan en cada query. Las queries usan arrays (`= ANY(...)`), que
# Postgres maneja bien aun con listas grandes; el chunk es defensa de memoria.
_AUTO_TAGS_CHUNK = 1000


def regenerate_auto_tags_batch(conn, equipo_ids) -> int:
    """Variante batch de `regenerate_auto_tags`: regenera las etiquetas
    `origen='auto'` de N equipos en un puñado de queries (en vez de O(N) pasadas
    — una por equipo). El resultado es IDÉNTICO a llamar `regenerate_auto_tags`
    equipo por equipo: mismo set de auto-tags por equipo, se respetan las
    `manual` (ON CONFLICT DO NOTHING) y se limpian las etiquetas huérfanas.

    Usar en los caminos masivos (bulk_action, duplicación, rename de categoría)
    donde antes se iteraba `regenerate_auto_tags` adentro de un loop → N+1.

    Devuelve cuántos equipos se procesaron."""
    ids = list(dict.fromkeys(int(i) for i in equipo_ids))  # dedup preservando orden
    if not ids:
        return 0

    procesados = 0
    for i in range(0, len(ids), _AUTO_TAGS_CHUNK):
        procesados += _regenerate_auto_tags_chunk(conn, ids[i:i + _AUTO_TAGS_CHUNK])

    # Limpiar etiquetas que ya no usa ningún equipo (ni manual ni auto). Igual que
    # en el camino por-equipo, pero UNA sola vez al final en vez de por equipo.
    conn.execute("""
        DELETE FROM etiquetas
        WHERE id NOT IN (SELECT DISTINCT etiqueta_id FROM equipo_etiquetas)
    """)
    return procesados


def _regenerate_auto_tags_chunk(conn, ids) -> int:
    """Procesa una tanda de equipos (sin la limpieza de huérfanas, que hace el
    caller una vez al final). Devuelve cuántos equipos se procesaron."""
    # 1) Cargar marca/modelo/nombre de todos los equipos de la tanda en UNA query.
    #    Alias `e` + helper MARCA_SUBQUERY (convención 2026-05-26).
    eq_rows = conn.execute(
        f"SELECT e.id, e.nombre, {MARCA_SUBQUERY}, e.modelo "
        "FROM equipos e WHERE e.id = ANY(%s)",
        (ids,),
    ).fetchall()
    if not eq_rows:
        return 0
    found_ids = [r["id"] for r in eq_rows]

    # 2) Borrar las auto actuales de todos los equipos de la tanda en UNA query.
    conn.execute(
        "DELETE FROM equipo_etiquetas WHERE equipo_id = ANY(%s) AND origen = 'auto'",
        (found_ids,),
    )

    # 3) Árbol de categorías (con ancestros) de TODOS los equipos en UNA query
    #    recursiva, arrastrando equipo_id para atribuir cada nombre a su equipo.
    cat_rows = conn.execute("""
        WITH RECURSIVE up AS (
            SELECT ec.equipo_id, c.id, c.nombre, c.parent_id
            FROM equipo_categorias ec
            JOIN categorias c ON c.id = ec.categoria_id
            WHERE ec.equipo_id = ANY(%s)
            UNION
            SELECT up.equipo_id, p.id, p.nombre, p.parent_id
            FROM categorias p
            JOIN up ON up.parent_id = p.id
        )
        SELECT DISTINCT equipo_id, nombre FROM up
    """, (found_ids,)).fetchall()
    cats_por_equipo: dict = {}
    for r in cat_rows:
        cats_por_equipo.setdefault(r["equipo_id"], []).append(r["nombre"])

    # 4) Calcular el bag de tags por equipo (misma pieza que el camino por-equipo)
    #    y juntar el universo de nombres de etiquetas de toda la tanda.
    bags: dict = {}
    todos_los_nombres: set = set()
    for r in eq_rows:
        equipo = {"id": r["id"], "nombre": r["nombre"], "marca": r["marca"], "modelo": r["modelo"]}
        bag = _auto_tags_from_parts(equipo, cats_por_equipo.get(r["id"], []))
        bags[r["id"]] = bag
        todos_los_nombres.update(bag)

    # 5) Asegurar que cada nombre exista en `etiquetas` (UNA query) y mapear
    #    nombre → id (UNA query).
    name_to_id: dict = {}
    if todos_los_nombres:
        nombres = list(todos_los_nombres)
        conn.execute(
            "INSERT INTO etiquetas (nombre) SELECT unnest(%s::text[]) "
            "ON CONFLICT (nombre) DO NOTHING",
            (nombres,),
        )
        id_rows = conn.execute(
            "SELECT id, nombre FROM etiquetas WHERE nombre = ANY(%s)",
            (nombres,),
        ).fetchall()
        name_to_id = {row["nombre"]: row["id"] for row in id_rows}

    # 6) Insertar todas las asignaciones auto de la tanda en UNA query (unnest de
    #    arrays paralelos). ON CONFLICT respeta una etiqueta ya marcada manual.
    eq_ids, et_ids, ordenes = [], [], []
    for eid in found_ids:
        for orden, name in enumerate(bags.get(eid, [])):
            etiqueta_id = name_to_id.get(name)
            if etiqueta_id is None:
                continue
            eq_ids.append(eid)
            et_ids.append(etiqueta_id)
            ordenes.append(orden)
    if eq_ids:
        conn.execute("""
            INSERT INTO equipo_etiquetas (equipo_id, etiqueta_id, orden, origen)
            SELECT eq, et, ord, 'auto'
            FROM unnest(%s::int[], %s::int[], %s::int[]) AS t(eq, et, ord)
            ON CONFLICT (equipo_id, etiqueta_id) DO NOTHING
        """, (eq_ids, et_ids, ordenes))

    return len(found_ids)


def regenerate_auto_tags_all(conn) -> int:
    """Regenera auto-tags para todos los equipos. Devuelve cantidad procesada."""
    rows = conn.execute("SELECT id FROM equipos").fetchall()
    return regenerate_auto_tags_batch(conn, [r["id"] for r in rows])
