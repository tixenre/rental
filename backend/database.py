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

    conn.execute("""
        CREATE TABLE IF NOT EXISTS etiquetas (
            id     SERIAL PRIMARY KEY,
            nombre TEXT UNIQUE NOT NULL
        )
    """)

    # Prioridad para ordenar categorías (menor = más arriba)
    conn.execute("""
        ALTER TABLE etiquetas
        ADD COLUMN IF NOT EXISTS prioridad INTEGER NOT NULL DEFAULT 100
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_etiq_prioridad ON etiquetas(prioridad, nombre)
    """)

    # Seed: solo aplica a etiquetas todavía con prioridad por defecto.
    # Así nunca pisa cambios manuales hechos desde el back-office.
    seed_pri = [
        (10,  ["Cámaras", "Camaras", "Camara", "Cámara"]),
        (20,  ["Lentes", "Lente"]),
        (30,  ["Luces", "Luz", "Iluminación"]),
        (40,  ["Modificadores", "Modificador"]),
        (50,  ["Soportes", "Soporte", "Trípode", "Tripode", "Tripodes", "Trípodes"]),
        (60,  ["Grips", "Griperia", "Gripería", "Grip"]),
        (70,  ["Sonido", "Audio", "Micrófonos", "Microfonos"]),
        (80,  ["Monitores", "Monitor"]),
        (90,  ["Baterías", "Baterias", "Batería"]),
    ]
    for pri, names in seed_pri:
        conn.execute(
            f"UPDATE etiquetas SET prioridad = %s "
            f"WHERE prioridad = 100 AND nombre IN ({','.join(['%s'] * len(names))})",
            (pri, *names),
        )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS equipo_etiquetas (
            equipo_id   INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            etiqueta_id INTEGER NOT NULL REFERENCES etiquetas(id) ON DELETE CASCADE,
            orden       INTEGER DEFAULT 0,
            PRIMARY KEY (equipo_id, etiqueta_id)
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_eq_etiq ON equipo_etiquetas(equipo_id)
    """)

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
