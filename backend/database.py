"""
database.py — Conexión PostgreSQL con pool de conexiones, migraciones y helpers.
"""

import os
import pathlib
import psycopg2
import psycopg2.extras
import psycopg2.pool
from datetime import datetime

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
        print(f"Error parsing DATABASE_URL: {e}")
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

class PGCursor:
    """Wrapper que permite acceder a resultados por índice O por nombre."""
    def __init__(self, raw_cursor):
        self.raw_cursor = raw_cursor

    def execute(self, sql, params=()):
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
        cur = self.raw_conn.cursor()
        # Convertir placeholders de ? (sqlite3) a %s (psycopg2)
        sql = sql.replace('?', '%s')
        cur.execute(sql, params)
        return PGCursor(cur)

    def executemany(self, sql, params_list):
        """Ejecuta una query con múltiples filas de parámetros."""
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

    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id            SERIAL PRIMARY KEY,
            email         TEXT UNIQUE NOT NULL,
            nombre        TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            creado_en     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

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

    # ── Categorías (taxonomía dedicada, árbol de 2 niveles) ──────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            id        SERIAL PRIMARY KEY,
            nombre    TEXT UNIQUE NOT NULL,
            prioridad INTEGER NOT NULL DEFAULT 100,
            parent_id INTEGER REFERENCES categorias(id) ON DELETE SET NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_cat_prioridad ON categorias(prioridad, nombre)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_cat_parent ON categorias(parent_id, prioridad, nombre)
    """)

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

    # Seed del árbol de categorías (en la tabla `categorias`, no en etiquetas).
    # Idempotente: ON CONFLICT (nombre). Solo pisa prioridad cuando está en
    # default (100), así no rompe ajustes manuales del back-office.
    SEED_TREE = [
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
        print(f"   ↳ {n} equipos con etiquetas auto regeneradas")
    except Exception as ex:
        print(f"⚠️  No se pudieron regenerar etiquetas auto: {ex}")

    conn.commit()
    conn.close()
    print("✅ Base de datos PostgreSQL inicializada")


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
    return count


def regenerate_auto_tags_all(conn) -> int:
    """Regenera auto-tags para todos los equipos. Devuelve cantidad procesada."""
    rows = conn.execute("SELECT id FROM equipos").fetchall()
    n = 0
    for r in rows:
        regenerate_auto_tags(conn, r["id"])
        n += 1
    return n
