"""
database.py — Conexión PostgreSQL con pool de conexiones, migraciones y helpers.
"""

import logging
import os
import pathlib
import psycopg2
import psycopg2.extras
import psycopg2.pool
from datetime import datetime

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

# ── Config BD desde variables de entorno ─────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL")

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
# minconn=2: siempre hay 2 conexiones listas. maxconn=10: techo para picos.

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        _pool = psycopg2.pool.ThreadedConnectionPool(2, 10, **get_connection_params())
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
            self._pool.putconn(self.raw_conn)   # devuelve al pool en lugar de cerrar
        else:
            self.raw_conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ── Init / migraciones ───────────────────────────────────────────────────────

def init_db():
    """Crear todas las tablas si no existen."""
    raw_conn = psycopg2.connect(**get_connection_params())
    raw_conn.set_isolation_level(0)  # Autocommit
    conn = PGConnection(raw_conn)

    # Crear tablas
    conn.execute("""
        CREATE TABLE IF NOT EXISTS equipos (
            id               SERIAL PRIMARY KEY,
            nombre           TEXT NOT NULL,
            marca            TEXT,
            modelo           TEXT,
            cantidad         INTEGER NOT NULL DEFAULT 1,
            precio_jornada   INTEGER,
            precio_usd       FLOAT,
            roi_pct          FLOAT,
            valor_reposicion FLOAT,
            foto_url         TEXT,
            fecha_compra     TEXT,
            serie            TEXT,
            bh_url           TEXT,
            dueno            TEXT DEFAULT 'Rambla',
            visible_catalogo INTEGER DEFAULT 1,
            estado           TEXT DEFAULT 'ok',
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Migration: flag para distinguir precios manuales (admin tipeó un valor
    # que no sale de la fórmula) vs automáticos (calculados desde
    # precio_usd × usd_rate × roi_pct/100). Cuando se hace recálculo masivo
    # al actualizar el USD rate, los manuales se respetan por default.
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS precio_jornada_manual BOOLEAN NOT NULL DEFAULT FALSE")

    # Migration: flag manual que el admin marca cuando termina de cargar la
    # ficha de un equipo. Permite filtrar "equipos pendientes" en el workflow
    # de carga incremental de inventario.
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS ficha_completa BOOLEAN NOT NULL DEFAULT FALSE")

    # Migration: soft delete. NULL = activo. Timestamp = eliminado.
    # Las listas filtran eliminado_at IS NULL por default. Preserva historial
    # de alquileres de equipos dados de baja (#206).
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS eliminado_at TIMESTAMP")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_equipos_eliminado_at ON equipos(eliminado_at) WHERE eliminado_at IS NOT NULL")

    # Tabla de marcas (brands)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS marcas (
            id SERIAL PRIMARY KEY,
            nombre TEXT NOT NULL UNIQUE,
            logo_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_marcas_nombre ON marcas(nombre)")

    # Migration: agregar columnas visible y orden para admin settings
    conn.execute("ALTER TABLE marcas ADD COLUMN IF NOT EXISTS visible BOOLEAN NOT NULL DEFAULT TRUE")
    conn.execute("ALTER TABLE marcas ADD COLUMN IF NOT EXISTS orden INTEGER NOT NULL DEFAULT 100")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_marcas_orden ON marcas(orden ASC)")
    # Migration: ranking automático de marcas (#131). Mismo concepto que equipos.
    conn.execute("ALTER TABLE marcas ADD COLUMN IF NOT EXISTS popularidad_score INT NOT NULL DEFAULT 0")
    conn.execute("ALTER TABLE marcas ADD COLUMN IF NOT EXISTS cant_pedidos INT NOT NULL DEFAULT 0")
    conn.execute("ALTER TABLE marcas ADD COLUMN IF NOT EXISTS ingreso_total_ars BIGINT NOT NULL DEFAULT 0")
    conn.execute("ALTER TABLE marcas ADD COLUMN IF NOT EXISTS ranking_actualizado TIMESTAMP")

    # Migration: agregar FK a marcas
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS brand_id INTEGER REFERENCES marcas(id)")

    # Migration: migrar datos de marca (TEXT) a brand_id (FK)
    try:
        # Obtener marcas únicas existentes
        existing_marcas = conn.execute("""
            SELECT DISTINCT marca FROM equipos WHERE marca IS NOT NULL AND marca != ''
            ORDER BY marca
        """).fetchall()

        for (marca,) in existing_marcas:
            marca = marca.strip()
            if not marca:
                continue
            # Insertar marca si no existe (UPSERT simulado con ON CONFLICT)
            conn.execute("""
                INSERT INTO marcas (nombre) VALUES (?)
                ON CONFLICT (nombre) DO NOTHING
            """, (marca,))

        # Backfill: actualizar brand_id para todos los equipos
        conn.execute("""
            UPDATE equipos SET brand_id = (
                SELECT id FROM marcas WHERE marcas.nombre = equipos.marca
            ) WHERE marca IS NOT NULL AND marca != ''
        """)
    except Exception as e:
        logger.warning("Migración de marcas parcial: %s", e)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id                SERIAL PRIMARY KEY,
            nombre            TEXT NOT NULL,
            apellido          TEXT NOT NULL,
            telefono          TEXT NOT NULL,
            email             TEXT NOT NULL UNIQUE,
            direccion         TEXT NOT NULL,
            cuit              TEXT NOT NULL,
            descuento         FLOAT DEFAULT 0,
            perfil_impuestos  TEXT DEFAULT 'consumidor_final',
            notas             TEXT,
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Migration: add maps URL column if not present
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS direccion_maps_url TEXT")
    # Migration: link clientes to Supabase Auth users (Phase 1 of unified backend)
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS supabase_uid UUID UNIQUE")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_clientes_supabase_uid ON clientes(supabase_uid)")
    # Functional index sobre LOWER(email): el UNIQUE no se usa porque las
    # queries hacen WHERE LOWER(email) = LOWER(?) (auth.py, cliente_portal.py).
    conn.execute("CREATE INDEX IF NOT EXISTS idx_clientes_email_lower ON clientes(LOWER(email))")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS alquileres (
            id               SERIAL PRIMARY KEY,
            cliente_id       INTEGER REFERENCES clientes(id) ON DELETE SET NULL,
            cliente_nombre   TEXT NOT NULL,
            cliente_email    TEXT,
            cliente_telefono TEXT,
            notas            TEXT,
            estado           TEXT NOT NULL DEFAULT 'presupuesto',
            fecha_desde      TEXT NOT NULL,
            fecha_hasta      TEXT NOT NULL,
            monto_total      INTEGER DEFAULT 0,
            monto_pagado     INTEGER DEFAULT 0,
            descuento_pct    FLOAT DEFAULT 0,
            fuente           TEXT DEFAULT 'sistema',
            numero_remito    TEXT,
            numero_pedido    INTEGER,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pedidos_estado ON alquileres(estado)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pedidos_fechas ON alquileres(fecha_desde, fecha_hasta)
    """)
    # Portal del cliente trae sus pedidos con WHERE cliente_id = ? en cada carga.
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pedidos_cliente ON alquileres(cliente_id)
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS alquiler_items (
            id             SERIAL PRIMARY KEY,
            pedido_id      INTEGER NOT NULL REFERENCES alquileres(id) ON DELETE CASCADE,
            equipo_id      INTEGER NOT NULL REFERENCES equipos(id),
            cantidad       INTEGER NOT NULL DEFAULT 1,
            precio_jornada INTEGER NOT NULL DEFAULT 0,
            subtotal       INTEGER NOT NULL DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pedido_items_pedido ON alquiler_items(pedido_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pedido_items_equipo ON alquiler_items(equipo_id)
    """)

    # NOTA: tabla `usuarios` (auth email+password legacy) removida en #76.
    # Auth ahora es 100% Google OAuth + Supabase. La migración Alembic
    # `322b...drop_tabla_usuarios_legacy_76` hace el DROP en prod.

    conn.execute("""
        CREATE TABLE IF NOT EXISTS equipo_fichas (
            equipo_id   INTEGER PRIMARY KEY REFERENCES equipos(id) ON DELETE CASCADE,
            descripcion TEXT,
            notas       TEXT,
            specs_json  TEXT,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Campos extra para construir el "nombre público" en el catálogo
    # (Cámara Sony FX3 Montura E Full Frame 4K).
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS montura   TEXT")
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS formato   TEXT")
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS resolucion TEXT")
    # Keywords/palabras clave libres por equipo (array JSON de strings).
    # Distintas de las etiquetas de búsqueda: estas son selling-points editoriales
    # ("bicolor", "silenciosa", "V-mount", "global shutter") visibles en la ficha.
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS keywords_json TEXT")
    # Template editable para el "nombre público" (con placeholders {marca}, {montura}, etc.).
    # Si está NULL/vacío, se usa el auto-build del frontend.
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS nombre_publico_template TEXT")

    # ── Ficha extendida (enriquecimiento con IA + scraping) ─────────────
    # Datos físicos / técnicos estructurados
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS peso TEXT")              # ej: "640g"
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS dimensiones TEXT")       # ej: "129.7 x 77.8 x 84.5 mm"
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS alimentacion TEXT")      # ej: "NP-FZ100", "V-mount", "AC 220V"
    # Listas estructuradas (TEXT con JSON, igual que specs_json/keywords_json)
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS incluye_json TEXT")          # ["Cuerpo", "Tapa", "Cargador", "Correa"]
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS conectividad_json TEXT")    # ["USB-C", "HDMI Type-A", "XLR x2"]
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS compatible_con_json TEXT")  # ["Sony E-mount", "Full-frame"]
    # Multimedia y referencias
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS video_url TEXT")             # YouTube demo
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS precio_bh_usd FLOAT")        # precio listado en B&H (referencia)
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS fuente_url TEXT")            # canonical (B&H si hubo)
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS fuente_titulo TEXT")
    # Trazabilidad del enriquecimiento — guardamos todo el raw para no perder data
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS raw_json TEXT")              # JSON completo de la última extracción
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS enriquecido_at TIMESTAMP")
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS enriquecido_fuente TEXT")    # 'firecrawl-bh' | 'firecrawl-oficial' | 'manual'

    # ── Etiquetas (bolsa libre / índice de búsqueda) ─────────────────────
    # Las etiquetas son strings libres: incluyen marca, modelo, palabras del
    # nombre, nombres de categorías asignadas y lo que el admin agregue.
    # NO son jerárquicas — la jerarquía vive en la tabla `categorias`.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS etiquetas (
            id     SERIAL PRIMARY KEY,
            nombre TEXT UNIQUE NOT NULL
        )
    """)
    # Columna prioridad legacy — se mantiene pero ya no se usa para ordenar
    # categorías. Queda por compat con datos viejos.
    conn.execute("""
        ALTER TABLE etiquetas
        ADD COLUMN IF NOT EXISTS prioridad INTEGER NOT NULL DEFAULT 100
    """)
    # parent_id legacy: se va a dropear más abajo, después de migrar a `categorias`.
    conn.execute("""
        ALTER TABLE etiquetas
        ADD COLUMN IF NOT EXISTS parent_id INTEGER
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS equipo_etiquetas (
            equipo_id   INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            etiqueta_id INTEGER NOT NULL REFERENCES etiquetas(id) ON DELETE CASCADE,
            orden       INTEGER DEFAULT 0,
            PRIMARY KEY (equipo_id, etiqueta_id)
        )
    """)
    # `origen` distingue etiquetas auto-generadas (a partir de categorías,
    # marca, modelo, nombre) de las puestas a mano por el admin. Permite
    # regenerar las auto sin tocar las manuales.
    conn.execute("""
        ALTER TABLE equipo_etiquetas
        ADD COLUMN IF NOT EXISTS origen TEXT NOT NULL DEFAULT 'manual'
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_eq_etiq ON equipo_etiquetas(equipo_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_eq_etiq_origen
            ON equipo_etiquetas(equipo_id, origen)
    """)
    # Mismo razonamiento que idx_eq_cat_categoria: el PK no sirve para
    # WHERE etiqueta_id = ? (queries reversas de "qué equipos tienen tag X").
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_eq_etiq_etiqueta ON equipo_etiquetas(etiqueta_id)
    """)

    # ── Categorías (taxonomía dedicada, árbol de 2 niveles) ──────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            id        SERIAL PRIMARY KEY,
            nombre    TEXT UNIQUE NOT NULL,
            prioridad INTEGER NOT NULL DEFAULT 100,
            parent_id INTEGER REFERENCES categorias(id) ON DELETE SET NULL
        )
    """)
    # Idempotente: agregar `visible` para installs viejos sin migration aplicada.
    conn.execute("""
        ALTER TABLE categorias ADD COLUMN IF NOT EXISTS visible BOOLEAN NOT NULL DEFAULT TRUE
    """)
    # Idempotente: plantilla de nombre público por categoría (PR #333).
    conn.execute("""
        ALTER TABLE categorias ADD COLUMN IF NOT EXISTS nombre_publico_template TEXT
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_cat_prioridad ON categorias(prioridad, nombre)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_cat_parent ON categorias(parent_id, prioridad, nombre)
    """)
    # Ranking automático de categorías (#131). Mismo concepto que equipos.
    conn.execute("ALTER TABLE categorias ADD COLUMN IF NOT EXISTS popularidad_score INT NOT NULL DEFAULT 0")
    conn.execute("ALTER TABLE categorias ADD COLUMN IF NOT EXISTS cant_pedidos INT NOT NULL DEFAULT 0")
    conn.execute("ALTER TABLE categorias ADD COLUMN IF NOT EXISTS ingreso_total_ars BIGINT NOT NULL DEFAULT 0")
    conn.execute("ALTER TABLE categorias ADD COLUMN IF NOT EXISTS ranking_actualizado TIMESTAMP")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS equipo_categorias (
            equipo_id    INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            categoria_id INTEGER NOT NULL REFERENCES categorias(id) ON DELETE CASCADE,
            orden        INTEGER DEFAULT 0,
            PRIMARY KEY (equipo_id, categoria_id)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_eq_cat ON equipo_categorias(equipo_id)
    """)
    # El PK (equipo_id, categoria_id) sirve para queries por equipo_id, pero no
    # para WHERE categoria_id = ? que se hace en equipos.py:1203,1219,234,248.
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_eq_cat_categoria ON equipo_categorias(categoria_id)
    """)

    # Seed del árbol de categorías (en la tabla `categorias`, no en etiquetas).
    # Sólo se ejecuta cuando la tabla está vacía — un install fresco arranca
    # con el árbol sugerido, pero una DB con categorías existentes queda
    # intacta. Antes corría en cada startup como "idempotente con ON CONFLICT",
    # pero pisaba parent_id y resucitaba categorías borradas por el admin.
    existing_cat_count = 0
    try:
        row = conn.execute("SELECT COUNT(*) AS n FROM categorias").fetchone()
        existing_cat_count = int(row["n"] if isinstance(row, dict) else row[0])
    except Exception:
        existing_cat_count = 0
    SEED_TREE = [] if existing_cat_count > 0 else [
        # (prioridad, nombre_padre, [hijos…])
        (10,  "Cámaras",              ["Video", "Foto", "Acción"]),
        (20,  "Lentes",               ["Zoom E-mount", "Zoom EF", "Fijos EF", "Especiales", "Vintage"]),
        (25,  "Adaptadores y Filtros",["Adaptadores de montura", "Filtros 82mm"]),
        (30,  "Iluminación",          ["LED daylight/bicolor", "LED RGB", "Tungsteno",
                                       "Fluorescente", "On-camera / Flash", "Práctica / efecto"]),
        (40,  "Modificadores",        ["Softbox", "Difusión / Frame", "Reflectores", "Banderas"]),
        (50,  "Soportes",             ["Trípodes video", "Trípodes foto", "C-Stands",
                                       "Estabilización", "Slider / Dolly / Riel", "Car Mount"]),
        (60,  "Grip",                 ["Brazos", "Clamps", "Wall plates / pins",
                                       "Pinzas", "Líneas de seguridad", "Sopapa", "Lastre"]),
        (70,  "Sonido",               ["Inalámbricos / Lavalier", "Shotgun / Boom",
                                       "On-camera (sonido)", "Estudio / Podcast", "Intercom"]),
        (80,  "Monitores y Video",    ["Monitores", "Grabadores",
                                       "Transmisión inalámbrica", "Follow Focus / Matebox"]),
        (90,  "Energía",              ["V-Mount", "NP / LP-E6", "Distribución eléctrica"]),
        (100, "Media y Datos",        ["Tarjetas SD", "Tarjetas CFexpress", "Lectores"]),
        (110, "Estudio y Producción", ["Set / Backdrops", "Paquetes"]),
    ]

    # Set de todos los nombres del árbol — se usa abajo para migrar etiquetas
    # legacy (las que actualmente viven en `etiquetas` como nodos del árbol)
    # hacia `categorias`.
    SEED_NAMES: set[str] = set()
    for pri, parent_name, children in SEED_TREE:
        SEED_NAMES.add(parent_name)
        SEED_NAMES.update(children)

    for pri, parent_name, children in SEED_TREE:
        conn.execute("""
            INSERT INTO categorias (nombre, prioridad, parent_id)
            VALUES (%s, %s, NULL)
            ON CONFLICT (nombre) DO UPDATE
                SET prioridad = CASE
                        WHEN categorias.prioridad = 100 THEN EXCLUDED.prioridad
                        ELSE categorias.prioridad
                    END,
                    parent_id = NULL
        """, (parent_name, pri))
        prow = conn.execute(
            "SELECT id FROM categorias WHERE nombre = %s", (parent_name,)
        ).fetchone()
        parent_cat_id = prow["id"]
        for idx, child_name in enumerate(children, start=1):
            child_pri = idx * 10
            conn.execute("""
                INSERT INTO categorias (nombre, prioridad, parent_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (nombre) DO UPDATE
                    SET parent_id = EXCLUDED.parent_id,
                        prioridad = CASE
                            WHEN categorias.prioridad = 100 THEN EXCLUDED.prioridad
                            ELSE categorias.prioridad
                        END
            """, (child_name, child_pri, parent_cat_id))

    # ── Migración: mover nodos del árbol que viven en `etiquetas` → `categorias` ──
    # Esta migración corre una sola vez por el ciclo de vida de cada nombre:
    # busca etiquetas cuyo nombre coincide con un nodo del árbol, mueve sus
    # asignaciones desde `equipo_etiquetas` → `equipo_categorias`, y borra
    # la etiqueta original. Idempotente: si ya está migrada, no encuentra nada.
    legacy_rows = conn.execute("""
        SELECT et.id AS etiq_id, et.nombre, c.id AS cat_id
        FROM etiquetas et
        JOIN categorias c ON c.nombre = et.nombre
    """).fetchall()
    for r in legacy_rows:
        # Copiar asignaciones: equipo_etiquetas → equipo_categorias.
        conn.execute("""
            INSERT INTO equipo_categorias (equipo_id, categoria_id, orden)
            SELECT equipo_id, %s, orden
            FROM equipo_etiquetas
            WHERE etiqueta_id = %s
            ON CONFLICT (equipo_id, categoria_id) DO NOTHING
        """, (r["cat_id"], r["etiq_id"]))
        # Borrar la etiqueta vieja (CASCADE elimina equipo_etiquetas).
        conn.execute("DELETE FROM etiquetas WHERE id = %s", (r["etiq_id"],))

    # Nota: NO dropeamos `etiquetas.parent_id` (queda como columna legacy
    # ignorada). Eso permite que los endpoints admin viejos sigan funcionando
    # mientras migramos la UI al nuevo CRUD de `categorias`.

    # ── Specs estructurados por categoría (rediseño docs/DISEÑO_SPECS.md - PR A) ──
    #
    # Hoy `equipo_fichas.specs_json` guarda specs como [{label, value}] sin
    # validación ni schema. Eso hace imposible filtrar el catálogo por specs
    # ("cámaras montura E con video 4K") o comparar dos productos lado a lado.
    #
    # Modelo nuevo: cada categoría define un TEMPLATE (categoria_spec_templates)
    # con las keys que sus equipos van a tener (sensor, montura, cri, etc.),
    # y los valores reales viven en EQUIPO_SPECS (key/value tipados).
    #
    # Migración: las tablas se crean acá. El form admin sigue editando el
    # specs_json viejo hasta que las PRs B/D del rediseño migren la UI.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS categoria_spec_templates (
            id                  SERIAL PRIMARY KEY,
            categoria_id        INTEGER NOT NULL REFERENCES categorias(id) ON DELETE CASCADE,
            spec_key            VARCHAR(64) NOT NULL,
            label               VARCHAR(120) NOT NULL,
            tipo                VARCHAR(16) NOT NULL,
            unidad              VARCHAR(32),
            enum_options        JSONB,
            prioridad           INTEGER DEFAULT 100,
            visible_en_card     BOOLEAN DEFAULT FALSE,
            visible_en_filtros  BOOLEAN DEFAULT FALSE,
            visible_en_nombre   BOOLEAN DEFAULT FALSE,
            obligatorio         BOOLEAN DEFAULT FALSE,
            ayuda               TEXT,
            destacado           BOOLEAN DEFAULT FALSE,
            UNIQUE (categoria_id, spec_key)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_spec_templates_cat "
        "ON categoria_spec_templates(categoria_id, prioridad)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS equipo_specs (
            equipo_id   INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            spec_key    VARCHAR(64) NOT NULL,
            value       TEXT NOT NULL,
            PRIMARY KEY (equipo_id, spec_key)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_equipo_specs_key "
        "ON equipo_specs(spec_key, value)"
    )

    # ── Mantenimiento log por equipo ─────────────────────────────────────
    # Una fila por evento de mantenimiento (revisión, reparación, limpieza,
    # etc.). proxima_revision opcional para recordatorios.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS equipo_mantenimiento (
            id                SERIAL PRIMARY KEY,
            equipo_id         INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            fecha             TEXT NOT NULL,
            tipo              VARCHAR(32) NOT NULL DEFAULT 'revision',
            descripcion       TEXT,
            costo             INTEGER,
            proxima_revision  TEXT,
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mantenimiento_equipo "
        "ON equipo_mantenimiento(equipo_id, fecha DESC)"
    )

    # ── Compatibilidades entre equipos (FX3 + Sigma EF → requiere MC-11) ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS equipo_compatibilidad (
            id            SERIAL PRIMARY KEY,
            equipo_a_id   INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            equipo_b_id   INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            tipo          VARCHAR(32) NOT NULL,
            nota          TEXT,
            adaptador_id  INTEGER REFERENCES equipos(id) ON DELETE SET NULL,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (equipo_a_id, equipo_b_id, tipo),
            CHECK (equipo_a_id != equipo_b_id),
            CHECK (tipo IN ('compatible', 'incompatible', 'requiere_adaptador'))
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_compat_a ON equipo_compatibilidad(equipo_a_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_compat_b ON equipo_compatibilidad(equipo_b_id)"
    )

    # ── Relevancia + ranking + nombre público calculado ────────────────
    # `relevancia_manual`: lo que el admin pone a mano (10=flagship, 100=default).
    # `popularidad_score`: calculado nightly desde historial de pedidos + ingreso.
    # `cant_pedidos` + `ingreso_total_ars`: snapshots para el cálculo y stats.
    # `nombre_publico` + `nombre_publico_largo`: cacheados desde el builder
    # (PR B implementa el builder y los rellena).
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS relevancia_manual INT NOT NULL DEFAULT 100")
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS popularidad_score INT NOT NULL DEFAULT 0")
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS cant_pedidos INT NOT NULL DEFAULT 0")
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS ingreso_total_ars BIGINT NOT NULL DEFAULT 0")
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS ranking_actualizado TIMESTAMP")
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS nombre_publico TEXT")
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS nombre_publico_largo TEXT")
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS nombre_publico_override TEXT")
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS nombre_publico_revisado BOOLEAN DEFAULT FALSE")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_equipos_ranking "
        "ON equipos(relevancia_manual ASC, popularidad_score DESC, nombre ASC)"
    )

    # ── Seed de los 12 templates iniciales (idempotente) ──
    # Importado dinámicamente para mantener este archivo manejable.
    try:
        from seeds.spec_templates import seed_spec_templates
        n = seed_spec_templates(conn)
        if n > 0:
            logger.info("%d templates de specs seedeados/actualizados", n)
    except Exception as ex:
        logger.warning("No se pudieron seedear los templates de specs: %s", ex)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS equipo_precio_historial (
            id             SERIAL PRIMARY KEY,
            equipo_id      INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            precio_jornada INTEGER,
            changed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_precio_hist_eq ON equipo_precio_historial(equipo_id)
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS kit_componentes (
            id             SERIAL PRIMARY KEY,
            equipo_id      INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            componente_id  INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            cantidad       INTEGER NOT NULL DEFAULT 1,
            UNIQUE(equipo_id, componente_id)
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_kit_eq ON kit_componentes(equipo_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_kit_comp ON kit_componentes(componente_id)
    """)
    # Columna orden para kit (migración idempotente)
    conn.execute("""
        ALTER TABLE kit_componentes ADD COLUMN IF NOT EXISTS orden INTEGER NOT NULL DEFAULT 0
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS alquiler_pagos (
            id         SERIAL PRIMARY KEY,
            pedido_id  INTEGER NOT NULL REFERENCES alquileres(id) ON DELETE CASCADE,
            monto      INTEGER NOT NULL,
            concepto   TEXT,
            fecha      TEXT DEFAULT CURRENT_DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pagos_pedido ON alquiler_pagos(pedido_id)
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS solicitudes_modificacion (
            id          SERIAL PRIMARY KEY,
            pedido_id   INTEGER NOT NULL REFERENCES alquileres(id) ON DELETE CASCADE,
            cliente_id  INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
            mensaje     TEXT NOT NULL,
            estado      TEXT NOT NULL DEFAULT 'pendiente',
            respuesta   TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_solicitudes_pedido ON solicitudes_modificacion(pedido_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_solicitudes_estado ON solicitudes_modificacion(estado)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_solicitudes_cliente ON solicitudes_modificacion(cliente_id)
    """)

    # Configuración global de la app (tipo de cambio, defaults, etc.).
    # Es un key-value simple: clave única + valor (string serializado).
    # Se accede vía /api/settings/:key (público read) y PUT /api/admin/settings/:key.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key         VARCHAR(64) PRIMARY KEY,
            value       TEXT NOT NULL,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by  VARCHAR(255)
        )
    """)
    # Seed inicial: tipo de cambio default si no existe.
    # 1000 ARS/USD es un placeholder razonable; el admin lo actualiza
    # cuando entra al panel.
    conn.execute("""
        INSERT INTO app_settings (key, value, updated_by)
        VALUES ('usd_rate', '1000', 'system-seed')
        ON CONFLICT (key) DO NOTHING
    """)

    conn.execute("CREATE SEQUENCE IF NOT EXISTS numero_pedido_seq")

    # Seed the sequence to the current max so nextval never collides with existing data.
    # GREATEST ensures we never decrease an already-advanced sequence on restart.
    conn.execute("""
        SELECT setval('numero_pedido_seq',
            GREATEST(
                (SELECT COALESCE(MAX(numero_pedido), 0) FROM alquileres WHERE numero_pedido IS NOT NULL),
                (SELECT COALESCE(MAX(CAST(numero_remito AS INTEGER)), 0) FROM alquileres
                 WHERE numero_remito IS NOT NULL AND numero_remito ~ '^[0-9]+$'),
                (SELECT last_value FROM numero_pedido_seq)
            ), true)
    """)

    # Regenerar etiquetas auto (origen='auto') para todos los equipos.
    # Idempotente: solo borra y reinserta las auto, no toca las manuales.
    # Se hace una vez por arranque para mantener la bolsa sincronizada
    # con marca/modelo/nombre/categorías.
    try:
        n = regenerate_auto_tags_all(conn)
        logger.info("%d equipos con etiquetas auto regeneradas", n)
    except Exception as ex:
        logger.warning("No se pudieron regenerar etiquetas auto: %s", ex)

    conn.commit()
    conn.close()
    logger.info("Base de datos PostgreSQL inicializada")


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
               e.nombre, e.marca, e.foto_url
        FROM kit_componentes kc
        JOIN equipos e ON e.id = kc.componente_id
        WHERE kc.equipo_id IN ({placeholders})
        ORDER BY kc.equipo_id, e.nombre
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
    """Agrega la ficha técnica (descripcion, montura, formato, resolucion, specs_json)."""
    if not equipos:
        return equipos
    ids = [e["id"] for e in equipos]
    placeholders = ",".join(["%s"] * len(ids))
    cur = conn.cursor()
    cur.execute(f"""
        SELECT equipo_id, descripcion, notas, specs_json, montura, formato, resolucion,
               keywords_json, nombre_publico_template,
               peso, dimensiones, alimentacion,
               incluye_json, conectividad_json, compatible_con_json,
               video_url, precio_bh_usd, fuente_url, fuente_titulo,
               enriquecido_at, enriquecido_fuente
        FROM equipo_fichas
        WHERE equipo_id IN ({placeholders})
    """, ids)
    rows = cur.fetchall()
    _ficha_keys = (
        "descripcion", "notas", "specs_json", "montura", "formato", "resolucion",
        "keywords_json", "nombre_publico_template",
        "peso", "dimensiones", "alimentacion",
        "incluye_json", "conectividad_json", "compatible_con_json",
        "video_url", "precio_bh_usd", "fuente_url", "fuente_titulo",
        "enriquecido_at", "enriquecido_fuente",
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
    specs marcadas como destacado=true en el template de su categoría."""
    if not equipos:
        return equipos
    ids = [e["id"] for e in equipos]
    placeholders = ",".join(["%s"] * len(ids))
    cur = conn.cursor()
    cur.execute(f"""
        SELECT es.equipo_id, t.label, es.value, t.prioridad
        FROM equipo_specs es
        JOIN equipo_categorias ec ON ec.equipo_id = es.equipo_id
        JOIN categoria_spec_templates t
            ON t.spec_key = es.spec_key
           AND t.categoria_id = ec.categoria_id
        WHERE t.destacado = TRUE
          AND es.equipo_id IN ({placeholders})
        ORDER BY es.equipo_id, t.prioridad, t.label
    """, ids)
    rows = cur.fetchall()
    cur.close()

    dest_map: dict[int, list[dict]] = {e["id"]: [] for e in equipos}
    seen: dict[int, set] = {e["id"]: set() for e in equipos}
    for r in rows:
        eid = r["equipo_id"]
        key = r["label"]
        if key not in seen[eid]:
            dest_map[eid].append({"label": r["label"], "value": r["value"]})
            seen[eid].add(key)

    for e in equipos:
        e["specs_destacados"] = dest_map[e["id"]]
    return equipos


# ── Auto-tags: regenerar etiquetas derivadas (origen='auto') ────────────────
#
# Las etiquetas auto se sintetizan desde marca, modelo, palabras del nombre
# y nombres de cada categoría asignada (incluyendo padres del árbol).
# Sirven como índice de búsqueda libre. El admin puede agregar etiquetas
# manuales encima sin que se pisen.

import re as _re

_WORD_SPLIT = _re.compile(r"[^\wáéíóúñü]+", flags=_re.UNICODE)


def _auto_tags_for_equipo(conn, equipo: dict) -> list[str]:
    """Calcula la lista de strings que deberían ser etiquetas auto."""
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
    for r in cat_rows:
        add(r["nombre"])

    return bag


def regenerate_auto_tags(conn, equipo_id: int) -> int:
    """
    Regenera las etiquetas `origen='auto'` para un equipo.
    No toca las `origen='manual'`. Devuelve cuántas auto-tags quedaron asignadas.
    """
    eq = conn.execute(
        "SELECT id, nombre, marca, modelo FROM equipos WHERE id = %s", (equipo_id,)
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


def regenerate_auto_tags_all(conn) -> int:
    """Regenera auto-tags para todos los equipos. Devuelve cantidad procesada."""
    rows = conn.execute("SELECT id FROM equipos").fetchall()
    n = 0
    for r in rows:
        regenerate_auto_tags(conn, r["id"])
        n += 1
    return n
