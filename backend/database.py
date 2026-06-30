"""
database.py — Conexión PostgreSQL con pool de conexiones, migraciones y helpers.
"""

import logging
import pathlib
import psycopg2
import psycopg2.extras
import psycopg2.pool

from config import settings
from busqueda.motor import CAMPO_PLANTILLA

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


# ── Init / migraciones ───────────────────────────────────────────────────────

def init_db():
    """Crear todas las tablas si no existen."""
    raw_conn = psycopg2.connect(**get_connection_params())
    raw_conn.set_isolation_level(0)  # Autocommit
    conn = PGConnection(raw_conn)

    # ── Búsqueda fuzzy: extensiones + helper inmutable ────────────────────────
    # `pg_trgm` (similitud por trigramas → typos + ranking) y `unaccent` (folding
    # de acentos: "bateria" = "Batería"). El motor único vive en backend/busqueda;
    # acá garantizamos que la infra de BD que necesita exista. `unaccent()` es
    # STABLE (no indexable); `f_unaccent` la envuelve IMMUTABLE — la forma
    # canónica que usan tanto las queries (busqueda.campo_sql) como los índices
    # GIN trigram de abajo. Idempotente. Ver decisión 2026-06-06 (motor de búsqueda).
    conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    conn.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    conn.execute(
        "CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text AS "
        "$$ SELECT public.unaccent('public.unaccent', $1) $$ "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT"
    )

    # Crear tablas
    conn.execute("""
        CREATE TABLE IF NOT EXISTS equipos (
            id               SERIAL PRIMARY KEY,
            nombre           TEXT NOT NULL,
            modelo           TEXT,
            cantidad         INTEGER NOT NULL DEFAULT 1,
            precio_jornada   INTEGER,
            precio_usd       FLOAT,
            roi_pct          FLOAT,
            valor_reposicion FLOAT,
            foto_url         TEXT,
            fecha_compra     DATE,
            serie            TEXT,
            bh_url           TEXT,
            dueno            TEXT DEFAULT 'Rambla',
            visible_catalogo INTEGER DEFAULT 1,
            estado           TEXT DEFAULT 'operativo',
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

    # Migration: categoría de SPECS del equipo (1 de las 5 del registry:
    # Cámaras/Lentes/Iluminación/Adaptadores/Filtros). Define qué specs aplican
    # y el nombre público, desacoplado del árbol de categorías de catálogo
    # (equipo_categorias), que es una agrupación manual web-managed para el
    # front-office. NULL = sin specs asignadas.
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS categoria_specs TEXT")

    # Migration: URL pública del HTML de producto guardado (B&H Webpage Complete).
    # Permite re-extraer specs en el futuro sin volver a pedir el HTML al dueño.
    # Mismo patrón que foto_url — almacena URL pública R2, blob en equipos/{id}/source.html.
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS html_source_url TEXT")

    # Migration: recurso interno (no es un producto del catálogo). Lo usa el
    # centinela del Estudio (E2): un equipo de cantidad=1 que representa el
    # espacio físico para que las reservas por hora pasen por el mismo motor de
    # stock/overlap. Se excluye SIEMPRE de catálogo público, filtros, listado
    # admin, ranking y specs — no es un producto alquilable suelto. Es distinto
    # de visible_catalogo=0 (un producto real oculto sigue siendo producto).
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS es_recurso_interno BOOLEAN NOT NULL DEFAULT FALSE")

    # Migration (#637): el default histórico del schema era 'ok', un valor que no
    # existe en el enum de la app (operativo / en_mantenimiento / fuera_servicio).
    # Un equipo creado sin estado explícito quedaba en 'ok' y el dropdown del admin
    # no matcheaba ninguna opción. Se alinea el default y se normalizan las filas
    # viejas que hayan quedado en 'ok'. Idempotente: el UPDATE es no-op tras la 1ra corrida.
    conn.execute("ALTER TABLE equipos ALTER COLUMN estado SET DEFAULT 'operativo'")
    conn.execute("UPDATE equipos SET estado = 'operativo' WHERE estado = 'ok'")

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
    conn.execute("ALTER TABLE marcas ADD COLUMN IF NOT EXISTS destacada BOOLEAN NOT NULL DEFAULT FALSE")

    # FK a marcas. brand_id es la fuente única del nombre de marca
    # (vía marcas.nombre). El backfill desde la columna legacy `marca` y su
    # DROP viven en la migración d5a8f2c4b6e9 (corre una sola vez).
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS brand_id INTEGER REFERENCES marcas(id)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id                SERIAL PRIMARY KEY,
            nombre            TEXT NOT NULL,
            apellido          TEXT NOT NULL,
            telefono          TEXT NOT NULL,
            email             TEXT NOT NULL UNIQUE,
            direccion         TEXT NOT NULL,
            cuit              TEXT NOT NULL,
            descuento         NUMERIC(5,2) DEFAULT 0,
            perfil_impuestos  TEXT DEFAULT 'consumidor_final',
            razon_social      TEXT,
            domicilio_fiscal  TEXT,
            email_facturacion TEXT,
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
    # Índices GIN trigram para la búsqueda fuzzy (backend/busqueda). La expresión
    # es la canónica única (CAMPO_PLANTILLA) — la misma que arma busqueda.campo_sql
    # en las queries, para que el planner los pueda usar. El combinado
    # nombre+apellido permite que "santiago perez" rankee por prefijo.
    _nombre_apellido = CAMPO_PLANTILLA.format(expr="(nombre || ' ' || apellido)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_clientes_nombre_apellido_trgm ON clientes USING gin ({_nombre_apellido} gin_trgm_ops)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_clientes_email_trgm ON clientes USING gin ({CAMPO_PLANTILLA.format(expr='email')} gin_trgm_ops)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_clientes_cuit_trgm ON clientes USING gin ({CAMPO_PLANTILLA.format(expr='cuit')} gin_trgm_ops)")
    # Verificación de identidad Didit (DNI + selfie → RENAPER). Esquema en dos
    # capas (MEMORIA 2026-06-03): espejo idempotente de la migración v6w7x8y9z0a1.
    # — dni: número de documento validado (sin foto — Didit no la entrega).
    # — cuil: CUIL personal confirmado por RENAPER (puede diferir del `cuit` de
    #   facturación, que puede ser la razón social de una empresa).
    # — dni_validado_at: timestamp de la aprobación (NULL = no verificado todavía).
    # — didit_session_id: ID de la sesión de Didit para auditoría y trazabilidad.
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS dni TEXT")
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS cuil TEXT")
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS dni_validado_at TIMESTAMP")
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS didit_session_id TEXT")
    # Datos completos de RENAPER (extraídos por Didit del documento + base RENAPER).
    # Solo se persiste texto — no hay imagen ni biométrico (Ley 25.326).
    # Todos los campos son NULL hasta completar la verificación.
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS nombre_renaper TEXT")
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS apellido_renaper TEXT")
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS fecha_nacimiento_renaper TEXT")
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS direccion_renaper TEXT")
    # apodo: alias opcional para saludos informales en mails (siempre editable).
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS apodo TEXT")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS alquileres (
            id               SERIAL PRIMARY KEY,
            cliente_id       INTEGER REFERENCES clientes(id) ON DELETE SET NULL,
            cliente_nombre   TEXT NOT NULL,
            cliente_email    TEXT,
            cliente_telefono TEXT,
            notas            TEXT,
            estado           TEXT NOT NULL DEFAULT 'presupuesto',
            fecha_desde      TIMESTAMP,
            fecha_hasta      TIMESTAMP,
            monto_total      INTEGER DEFAULT 0,
            monto_pagado     INTEGER DEFAULT 0,
            descuento_pct    NUMERIC(5,2) DEFAULT 0,
            fuente           TEXT DEFAULT 'sistema',
            numero_pedido    INTEGER,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Estudio E2: tipo de alquiler ('diaria' = pedido normal por jornada;
    # 'estudio' = reserva del espacio por horas). El DEFAULT 'diaria' es clave:
    # las reservas existentes y las queries de overlap (que NO filtran por tipo)
    # quedan idénticas. `estudio_con_pack` se reserva para E3 (pack Grip/Luz).
    conn.execute("ALTER TABLE alquileres ADD COLUMN IF NOT EXISTS tipo TEXT NOT NULL DEFAULT 'diaria'")
    conn.execute("ALTER TABLE alquileres ADD COLUMN IF NOT EXISTS estudio_con_pack BOOLEAN NOT NULL DEFAULT FALSE")

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
            -- equipo_id NULL = línea personalizada (texto libre, #805): no es del
            -- catálogo, no reserva stock. Su nombre vive en `nombre_libre`.
            equipo_id      INTEGER REFERENCES equipos(id),
            cantidad       INTEGER NOT NULL DEFAULT 1,
            precio_jornada INTEGER NOT NULL DEFAULT 0,
            subtotal       INTEGER NOT NULL DEFAULT 0,
            -- Orden manual de las líneas dentro del pedido (drag-reorder, #806).
            -- Se asigna por posición al guardar; los displays ordenan por `orden, id`.
            orden          INTEGER NOT NULL DEFAULT 0,
            -- Línea personalizada (#805): nombre libre + modo de cobro por línea.
            -- `cobro_modo`: 'jornada' (× jornadas, default = equipos) | 'fijo' (monto único).
            nombre_libre   TEXT,
            cobro_modo     TEXT NOT NULL DEFAULT 'jornada'
        )
    """)
    # Idempotente para tablas ya creadas antes de estas features (esquema en dos capas).
    conn.execute("ALTER TABLE alquiler_items ADD COLUMN IF NOT EXISTS orden INTEGER NOT NULL DEFAULT 0")
    conn.execute("ALTER TABLE alquiler_items ADD COLUMN IF NOT EXISTS nombre_libre TEXT")
    conn.execute("ALTER TABLE alquiler_items ADD COLUMN IF NOT EXISTS cobro_modo TEXT NOT NULL DEFAULT 'jornada'")
    # Línea personalizada (#805): equipo_id deja de ser NOT NULL para permitir
    # líneas libres. Idempotente para tablas viejas con la constraint.
    conn.execute("ALTER TABLE alquiler_items ALTER COLUMN equipo_id DROP NOT NULL")

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
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # specs_json + raw_json fueron droppeados en Fase E (d7e9b3c5a8f2).
    # montura/formato/resolucion/peso/dimensiones/alimentacion fueron
    # droppeados en Fase F (a1b3c5e7f9d2). Las specs viven en equipo_specs.
    # Keywords/palabras clave libres por equipo (array JSON de strings).
    # Distintas de las etiquetas de búsqueda: estas son selling-points editoriales
    # ("bicolor", "silenciosa", "V-mount", "global shutter") visibles en la ficha.
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS keywords_json TEXT")
    # Template editable para el "nombre público" (con placeholders {marca}, {montura}, etc.).
    # Si está NULL/vacío, se usa el auto-build del frontend.
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS nombre_publico_template TEXT")

    # ── Ficha extendida (enriquecimiento con IA + scraping) ─────────────
    # Las specs físicas (peso/dimensiones/alimentacion/montura/formato/
    # resolucion) viven en equipo_specs desde Fase F. Acá quedan solo
    # las listas y multimedia que aún no son specs estructuradas.
    # Listas estructuradas (TEXT con JSON, igual que keywords_json)
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS incluye_json TEXT")          # ["Cuerpo", "Tapa", "Cargador", "Correa"]
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS conectividad_json TEXT")    # ["USB-C", "HDMI Type-A", "XLR x2"]
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS compatible_con_json TEXT")  # ["Sony E-mount", "Full-frame"]
    # Multimedia y referencias
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS video_url TEXT")             # YouTube demo
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS precio_bh_usd FLOAT")        # precio listado en B&H (referencia)
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS fuente_url TEXT")            # canonical (B&H si hubo)
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS fuente_titulo TEXT")
    # raw_json eliminada en Fase E (migration d7e9b3c5a8f2).
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS enriquecido_at TIMESTAMP")
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS enriquecido_fuente TEXT")    # 'firecrawl-bh' | 'firecrawl-oficial' | 'manual'
    # B1 #635: contenido incluido (dim. 3) — [{nombre, cantidad, foto_url?}] editado a mano
    conn.execute("ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS contenido_incluido_json TEXT")

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
    # `grupo_visual` agrupa varias categorías raíz en un bloque visual del
    # catálogo (ej. Lentes / Adaptadores / Filtros → "Óptica") sin nidos en
    # el modelo de datos. Single source of truth: registry.py.
    conn.execute("""
        ALTER TABLE categorias ADD COLUMN IF NOT EXISTS grupo_visual VARCHAR(64)
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
        (20,  "Lentes",               ["Zoom", "Fijo", "Vintage", "Especiales"]),
        (25,  "Adaptadores",          []),  # sub-cats por montura (E/RF/EF/M42) on-the-fly
        (27,  "Filtros",              []),  # sub-cats por diámetro (82mm/77mm) on-the-fly
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
    # Modelo de specs (registry-driven, composite key por categoría):
    #
    # 1) `spec_definitions` — UNIQUE(categoria_raiz_id, spec_key). Cada cat
    #    raíz es dueña de sus filas; los keys "shared" (lens_mount, formato,
    #    diametro_filtro, peso_g) están duplicados por cat. El motor de
    #    compat matchea por string-equality del spec_key + value.
    #    Single source of truth: `backend/specs/registry.py`.
    #
    # 2) `categoria_spec_templates` — asigna spec_def a una sub-categoría
    #    con flags overriding (prioridad, destacado, en_card/filtros/nombre).
    #
    # 3) `equipo_specs` — valores concretos por equipo, FK a spec_def.

    conn.execute("""
        CREATE TABLE IF NOT EXISTS spec_definitions (
            id                  SERIAL PRIMARY KEY,
            categoria_raiz_id   INTEGER REFERENCES categorias(id) ON DELETE CASCADE,
            spec_key            VARCHAR(64) NOT NULL,
            label               VARCHAR(120) NOT NULL,
            tipo                VARCHAR(16) NOT NULL,
            unidad              VARCHAR(32),
            enum_options        JSONB,
            ayuda               TEXT,
            es_compatibilidad   BOOLEAN NOT NULL DEFAULT FALSE,
            compatibilidad_modo VARCHAR(16) NOT NULL DEFAULT 'exacta',
            rol_compatibilidad  VARCHAR(16),
            validado            BOOLEAN NOT NULL DEFAULT FALSE,
            tabla_columnas      JSONB,
            output_config       JSONB,
            favorito            BOOLEAN NOT NULL DEFAULT FALSE,
            en_nombre           BOOLEAN NOT NULL DEFAULT FALSE,
            en_filtros          BOOLEAN NOT NULL DEFAULT FALSE,
            prioridad           INTEGER NOT NULL DEFAULT 100,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (categoria_raiz_id, spec_key)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_spec_def_categoria "
        "ON spec_definitions(categoria_raiz_id, spec_key)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_spec_def_compat "
        "ON spec_definitions(spec_key) WHERE es_compatibilidad"
    )
    # Specs free-floating (admin endpoint sin categoría) — partial unique.
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_spec_def_global_unique "
        "ON spec_definitions(spec_key) WHERE categoria_raiz_id IS NULL"
    )

    # Catálogo global de unidades (lm, K, V, A, W…). Referenciado por specs
    # tabla con columnas `valor_unidad` para listas cerradas de opciones.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS unidades (
            id          SERIAL PRIMARY KEY,
            simbolo     VARCHAR(16) UNIQUE NOT NULL,
            nombre      VARCHAR(64) NOT NULL,
            dimension   VARCHAR(32),
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_unidades_dimension ON unidades(dimension)"
    )
    # FK al catálogo unidades. El `unidad` VARCHAR de spec_definitions se
    # mantiene como cache denormalizado para evitar JOINs en el hot path
    # (render, listing). El sync `unidad ↔ unidad_id` lo cuida el endpoint
    # PATCH/POST en routes/specs.py.
    conn.execute(
        "ALTER TABLE spec_definitions "
        "ADD COLUMN IF NOT EXISTS unidad_id INTEGER "
        "REFERENCES unidades(id) ON DELETE SET NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_spec_def_unidad_id "
        "ON spec_definitions(unidad_id) WHERE unidad_id IS NOT NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_spec_def_compat "
        "ON spec_definitions(es_compatibilidad) WHERE es_compatibilidad"
    )
    # aliases: lista de strings usados para match de columnas B&H/CSV.
    # Agregado por migración b3d5e7f9a1c2; lo replicamos en init_db para
    # garantizar la columna pase lo que pase con la cadena de Alembic.
    conn.execute(
        "ALTER TABLE spec_definitions "
        "ADD COLUMN IF NOT EXISTS aliases JSONB NOT NULL DEFAULT '[]'::jsonb"
    )

    # Familias jerárquicas para specs multi_enum (HDMI 1.4 < 2.0 < 2.1, SDI
    # 3G < 6G < 12G, sensor formats, etc.). Editable desde UI admin —
    # antes vivían hardcodeadas en routes/specs.py.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS spec_familia_jerarquia (
            id          SERIAL PRIMARY KEY,
            familia     VARCHAR(64) NOT NULL,
            valor       VARCHAR(64) NOT NULL,
            posicion    INTEGER NOT NULL,
            spec_def_id INTEGER REFERENCES spec_definitions(id) ON DELETE CASCADE,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (familia, valor)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_fam_jer_familia_pos "
        "ON spec_familia_jerarquia (familia, posicion)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS categoria_spec_templates (
            id                  SERIAL PRIMARY KEY,
            categoria_id        INTEGER NOT NULL REFERENCES categorias(id) ON DELETE CASCADE,
            spec_def_id         INTEGER NOT NULL REFERENCES spec_definitions(id) ON DELETE CASCADE,
            prioridad           INTEGER DEFAULT 100,
            destacado           BOOLEAN DEFAULT FALSE,
            obligatorio         BOOLEAN DEFAULT FALSE,
            visible_en_card     BOOLEAN DEFAULT FALSE,
            visible_en_filtros  BOOLEAN DEFAULT FALSE,
            visible_en_nombre   BOOLEAN DEFAULT FALSE,
            ayuda               TEXT,
            UNIQUE (categoria_id, spec_def_id)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cst_categoria "
        "ON categoria_spec_templates(categoria_id, prioridad)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cst_def "
        "ON categoria_spec_templates(spec_def_id)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS equipo_specs (
            equipo_id   INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            spec_def_id INTEGER NOT NULL REFERENCES spec_definitions(id) ON DELETE CASCADE,
            value       TEXT NOT NULL,
            PRIMARY KEY (equipo_id, spec_def_id)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_equipo_specs_def_value "
        "ON equipo_specs(spec_def_id, value)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_equipo_specs_equipo "
        "ON equipo_specs(equipo_id)"
    )

    # ── Mantenimiento log por equipo ─────────────────────────────────────
    # Una fila por evento de mantenimiento (revisión, reparación, limpieza,
    # etc.). proxima_revision opcional para recordatorios.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS equipo_mantenimiento (
            id                SERIAL PRIMARY KEY,
            equipo_id         INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            fecha             TIMESTAMP NOT NULL,
            tipo              VARCHAR(32) NOT NULL DEFAULT 'revision',
            descripcion       TEXT,
            costo             INTEGER,
            proxima_revision  TIMESTAMP,
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mantenimiento_equipo "
        "ON equipo_mantenimiento(equipo_id, fecha DESC)"
    )
    # Mantenimiento que bloquea disponibilidad: una entrada con bloquea_stock=true
    # y fecha/fecha_hasta saca `cantidad` unidades del equipo durante ese rango.
    # Si fecha_hasta es NULL o bloquea_stock=false, es solo log histórico.
    conn.execute("ALTER TABLE equipo_mantenimiento ADD COLUMN IF NOT EXISTS fecha_hasta TIMESTAMP")
    conn.execute("ALTER TABLE equipo_mantenimiento ADD COLUMN IF NOT EXISTS cantidad INTEGER NOT NULL DEFAULT 1")
    conn.execute("ALTER TABLE equipo_mantenimiento ADD COLUMN IF NOT EXISTS bloquea_stock BOOLEAN NOT NULL DEFAULT FALSE")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mantenimiento_bloqueo "
        "ON equipo_mantenimiento(equipo_id, fecha, fecha_hasta) WHERE bloquea_stock = TRUE"
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
    # Metadata para distinguir compat generadas por el skill IA vs manuales
    # del dueño. Las auto se borran/reemplazan en cada regen; manuales nunca.
    conn.execute("ALTER TABLE equipo_compatibilidad ADD COLUMN IF NOT EXISTS auto_generado BOOLEAN NOT NULL DEFAULT FALSE")
    conn.execute("ALTER TABLE equipo_compatibilidad ADD COLUMN IF NOT EXISTS razon_ia TEXT")
    conn.execute("ALTER TABLE equipo_compatibilidad ADD COLUMN IF NOT EXISTS confianza REAL")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_compat_auto "
        "ON equipo_compatibilidad(auto_generado) WHERE auto_generado = TRUE"
    )
    # Timestamp de última pasada del skill por equipo (para encolar pendientes).
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS compat_analizado_at TIMESTAMP")

    # Propuestas IA generadas por el skill gear-compatibility. NUNCA se aplican
    # automáticamente — el dueño las aprueba/descarta desde la UI.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS spec_propuestas_pendientes (
            id            SERIAL PRIMARY KEY,
            tipo          VARCHAR(20) NOT NULL,
            payload       JSONB       NOT NULL,
            origen        VARCHAR(64),
            confianza     REAL,
            created_at    TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
            aplicado_at   TIMESTAMP,
            descartado_at TIMESTAMP,
            CHECK (tipo IN ('enum_option', 'spec_nueva', 'merge_specs', 'assign_spec'))
        )
    """)
    # Migration idempotente: si la tabla existe con el CHECK viejo, lo
    # reemplazamos por uno que incluye 'assign_spec'.
    conn.execute("ALTER TABLE spec_propuestas_pendientes DROP CONSTRAINT IF EXISTS spec_propuestas_pendientes_tipo_check")
    conn.execute(
        "ALTER TABLE spec_propuestas_pendientes ADD CONSTRAINT spec_propuestas_pendientes_tipo_check "
        "CHECK (tipo IN ('enum_option', 'spec_nueva', 'merge_specs', 'assign_spec'))"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_propuestas_pendientes "
        "ON spec_propuestas_pendientes(created_at DESC) "
        "WHERE aplicado_at IS NULL AND descartado_at IS NULL"
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
    # Índices GIN trigram para la búsqueda fuzzy (backend/busqueda). La expresión
    # es la canónica única (CAMPO_PLANTILLA), la misma que arma busqueda.campo_sql.
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_equipos_nombre_trgm ON equipos USING gin ({CAMPO_PLANTILLA.format(expr='nombre')} gin_trgm_ops)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_equipos_modelo_trgm ON equipos USING gin ({CAMPO_PLANTILLA.format(expr='modelo')} gin_trgm_ops)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_equipos_serie_trgm ON equipos USING gin ({CAMPO_PLANTILLA.format(expr='serie')} gin_trgm_ops)")

    # NOTA: el seed de spec_templates se movió a `seed_spec_templates_after_migrations`
    # invocado desde main.py después de alembic upgrade. El motivo: la migración
    # `unificar_specs_definitions` dropea categoria_spec_templates y equipo_specs
    # y los recrea con un schema nuevo (con spec_def_id). Si el seed corriera
    # antes de alembic en una BD con schema viejo, fallaría con "column
    # spec_def_id does not exist".

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
    # A1 #635: columnas para combos (descuento por línea + esencial/best-effort).
    # Schema en init_db (idempotente); el backfill del tipo vive en la migración a1c3b5f7e9d2.
    conn.execute("ALTER TABLE kit_componentes ADD COLUMN IF NOT EXISTS descuento_pct FLOAT NOT NULL DEFAULT 0.0")
    conn.execute("ALTER TABLE kit_componentes ADD COLUMN IF NOT EXISTS esencial BOOLEAN NOT NULL DEFAULT TRUE")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS alquiler_pagos (
            id           SERIAL PRIMARY KEY,
            pedido_id    INTEGER NOT NULL REFERENCES alquileres(id) ON DELETE CASCADE,
            monto        INTEGER NOT NULL,
            concepto     TEXT,
            destinatario TEXT,
            metodo       TEXT,
            fecha        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pagos_pedido ON alquiler_pagos(pedido_id)
    """)

    # destinatario (a quién se cobró: Tincho/Pablo) + metodo (transferencia/
    # efectivo) — esquema en dos capas (MEMORIA 2026-06-03): también en la
    # migración u5v6w7x8y9z0. Nullable a propósito: los pagos previos a junio
    # 2026 son import del sistema anterior y quedan sin especificar ("—").
    conn.execute("ALTER TABLE alquiler_pagos ADD COLUMN IF NOT EXISTS destinatario TEXT")
    conn.execute("ALTER TABLE alquiler_pagos ADD COLUMN IF NOT EXISTS metodo TEXT")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS solicitudes_modificacion (
            id                SERIAL PRIMARY KEY,
            pedido_id         INTEGER NOT NULL REFERENCES alquileres(id) ON DELETE CASCADE,
            cliente_id        INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
            mensaje           TEXT,
            estado            TEXT NOT NULL DEFAULT 'pendiente',
            respuesta         TEXT,
            cambios_json      JSONB,
            cambios_aplicados JSONB,
            tipo              TEXT NOT NULL DEFAULT 'aprobacion',
            resolved_at       TIMESTAMPTZ,
            resolved_by       TEXT,
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    # Garantía atómica de "una sola solicitud pendiente por pedido": previene
    # races multi-tab donde dos requests pasan el check optimista y ambos
    # insertan.
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uniq_solicitud_pendiente_por_pedido
        ON solicitudes_modificacion (pedido_id)
        WHERE estado = 'pendiente'
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
    # Horas mínimas de antelación para que el cliente pueda solicitar
    # una modificación al pedido desde el portal.
    conn.execute("""
        INSERT INTO app_settings (key, value, updated_by)
        VALUES ('modificacion_ventana_horas', '24', 'system-seed')
        ON CONFLICT (key) DO NOTHING
    """)
    conn.execute("""
        INSERT INTO app_settings (key, value, updated_by)
        VALUES ('hero_taglines', '[["rental, estudio,","rambla."],["en rambla,","en mardel."],["en rambla,","tu proyecto."],["en rambla,","tu rodaje."]]', 'system-seed')
        ON CONFLICT (key) DO NOTHING
    """)
    # Token del feed iCal de reservas (routes/calendar.py). Vacío = feed
    # deshabilitado; el admin lo genera desde /admin/settings (no se expone
    # por el GET /settings/{key} público).
    conn.execute("""
        INSERT INTO app_settings (key, value, updated_by)
        VALUES ('ical_feed_token', '', 'system-seed')
        ON CONFLICT (key) DO NOTHING
    """)

    # Sugerencias automáticas ignoradas (#352). Cuando el admin descarta una
    # sugerencia, la persistimos por (tipo, ref) para no volver a mostrarla.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sugerencias_ignoradas (
            tipo       TEXT NOT NULL,
            ref        TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (tipo, ref)
        )
    """)

    # Cierres de liquidación (#721). Cerrar un mes congela una FOTO inmutable del
    # reporte de ese mes (los números Y el modelo de comisiones con que se calculó)
    # → cambiar el modelo o editar un pedido viejo ya no reescribe un mes liquidado.
    # `mes` es 'YYYY-MM'. Reabrir = borrar la fila (vuelve a calcularse en vivo).
    # Motor: backend/reportes/cierres.py. Va TAMBIÉN en una migración (esquema en
    # dos capas, decisión 2026-06-03).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS liquidacion_cierres (
            mes           VARCHAR(7) PRIMARY KEY,
            snapshot_json TEXT NOT NULL,
            modelo_json   TEXT NOT NULL,
            cerrado_por   VARCHAR(255),
            cerrado_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Contabilidad (#809): cuentas + gasto_categorias + movimientos ───────
    # Módulo contable (backend/contabilidad/, espejo de reportes/): el libro
    # único de movimientos entre cuentas/cajas con saldos. El ingreso por
    # alquiler NO vive acá — DERIVA de alquiler_pagos (única fuente del cobro,
    # #722); el saldo de la caja de un socio se calcula sumando sus pagos. Acá
    # solo van los movimientos manuales (gasto/transferencia/retiro/aporte) y las
    # cuentas con su saldo inicial. Esquema en dos capas (decisión 2026-06-03):
    # también en la migración x8y9z0a1b2c3.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cuentas (
            id             SERIAL PRIMARY KEY,
            nombre         TEXT NOT NULL,
            tipo           TEXT NOT NULL DEFAULT 'caja',
            socio          TEXT,
            moneda         VARCHAR(3) NOT NULL DEFAULT 'ARS',
            saldo_inicial  INTEGER NOT NULL DEFAULT 0,
            fecha_apertura DATE NOT NULL DEFAULT '2026-06-01',
            activa         BOOLEAN NOT NULL DEFAULT TRUE,
            orden          INTEGER NOT NULL DEFAULT 0,
            created_by     TEXT,
            created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by     TEXT,
            updated_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # moneda por cuenta (ARS/USD) — a veces se guardan dólares. ADD COLUMN para
    # BDs que ya tenían la tabla (migración d4e5f6a7b8c9).
    conn.execute("ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS moneda VARCHAR(3) NOT NULL DEFAULT 'ARS'")
    # El nombre es único SOLO entre cuentas activas: una cuenta dada de baja
    # (activa=FALSE) deja de bloquear su nombre, así se puede reusar (migración
    # f6a7b8c9d0e1). Se baja el único global viejo y se crea el parcial.
    conn.execute("ALTER TABLE cuentas DROP CONSTRAINT IF EXISTS cuentas_nombre_key")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS cuentas_nombre_activa_uq "
        "ON cuentas(nombre) WHERE activa"
    )
    # Un socio = exactamente una caja (puente 1:1 con alquiler_pagos.destinatario).
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_cuentas_socio "
        "ON cuentas(socio) WHERE socio IS NOT NULL"
    )
    conn.execute("""
        INSERT INTO cuentas (nombre, tipo, socio, moneda, orden) VALUES
            ('Caja Tincho', 'socio', 'Tincho', 'ARS', 1),
            ('Caja Pablo',  'socio', 'Pablo',  'ARS', 2),
            ('Efectivo',    'caja',  NULL,      'ARS', 3),
            ('Banco',       'banco', NULL,      'ARS', 4),
            ('Fondo Rambla','fondo', 'Rambla',  'ARS', 5),
            ('Dólares',     'caja',  NULL,      'USD', 6)
        ON CONFLICT (nombre) WHERE activa DO NOTHING
    """)
    # Rambla también cobra (default): la caja Fondo Rambla representa al cobrador
    # 'Rambla'. Backfill para BDs que ya tenían la caja con socio NULL (migración
    # c3d4e5f6a7b8). Idempotente.
    conn.execute(
        "UPDATE cuentas SET socio = 'Rambla' WHERE nombre = 'Fondo Rambla' AND socio IS NULL"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gasto_categorias (
            id     SERIAL PRIMARY KEY,
            nombre TEXT NOT NULL UNIQUE,
            activa BOOLEAN NOT NULL DEFAULT TRUE,
            orden  INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        INSERT INTO gasto_categorias (nombre, orden) VALUES
            ('Alquiler local', 1), ('Sueldos', 2), ('Equipos', 3),
            ('Mantenimiento', 4), ('Impuestos', 5), ('Servicios', 6),
            ('Otros', 99)
        ON CONFLICT (nombre) DO NOTHING
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS movimientos (
            id                SERIAL PRIMARY KEY,
            tipo              TEXT NOT NULL,
            monto             INTEGER NOT NULL CHECK (monto > 0),
            cuenta_origen_id  INTEGER REFERENCES cuentas(id),
            cuenta_destino_id INTEGER REFERENCES cuentas(id),
            categoria_id      INTEGER REFERENCES gasto_categorias(id),
            metodo            TEXT,
            fecha             DATE NOT NULL DEFAULT CURRENT_DATE,
            nota              TEXT,
            comprobante_url   TEXT,
            comprobante_key   TEXT,
            rendicion_mes     VARCHAR(7),
            es_rendicion      BOOLEAN NOT NULL DEFAULT FALSE,
            created_by        TEXT,
            created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by        TEXT,
            updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            anulado           BOOLEAN NOT NULL DEFAULT FALSE,
            anulado_por       TEXT,
            anulado_at        TIMESTAMP,
            anulado_motivo    TEXT,
            CONSTRAINT mov_tiene_cuenta CHECK (cuenta_origen_id IS NOT NULL OR cuenta_destino_id IS NOT NULL),
            CONSTRAINT mov_cuentas_distintas CHECK (cuenta_origen_id IS DISTINCT FROM cuenta_destino_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mov_fecha ON movimientos(fecha)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mov_origen ON movimientos(cuenta_origen_id) WHERE NOT anulado"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mov_destino ON movimientos(cuenta_destino_id) WHERE NOT anulado"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mov_rendicion ON movimientos(rendicion_mes) WHERE es_rendicion"
    )
    # beneficiario: a quién / para qué es el movimiento (ej. "Jimena") — etiqueta
    # parseable y reutilizable (migración e5f6a7b8c9d0).
    conn.execute("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS beneficiario TEXT")
    # Cierres contables (#809, Fase 6): congelan un mes (foto + traba la edición de
    # movimientos de ese mes). Espejo de la migración b2c3d4e5f6a7.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contabilidad_cierres (
            mes           VARCHAR(7) PRIMARY KEY,
            snapshot_json TEXT NOT NULL,
            cerrado_por   VARCHAR(255),
            cerrado_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Reconciliación con migraciones ──────────────────────────────────────
    # Estas tablas/columnas históricamente vivían SOLO en migraciones Alembic.
    # Las replicamos acá (idempotente) para que init_db produzca un esquema
    # COMPLETO aunque `alembic upgrade` falle (paso defensivo: ya ocurrió una
    # falla silenciosa con equipos.slug). Mantener en sync con migrations/.

    # descuentos por jornada (migración a3e7f1d2b8c4)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS descuentos_jornada (
            id         SERIAL PRIMARY KEY,
            jornadas   INTEGER NOT NULL UNIQUE,
            pct        NUMERIC(5,2) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("ALTER TABLE alquileres ADD COLUMN IF NOT EXISTS descuento_jornadas_pct FLOAT DEFAULT 0")

    # email infra (migración a4e8c2b9d710)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS email_templates (
            key        TEXT PRIMARY KEY,
            subject    TEXT NOT NULL,
            body_html  TEXT NOT NULL,
            body_text  TEXT NOT NULL,
            enabled    BOOLEAN NOT NULL DEFAULT TRUE,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        )
    """)
    # On/off por plantilla (Fase B mails): apagar un mail automático sin tocar
    # código. `send_email` lo respeta. ADD COLUMN idempotente para BDs que ya
    # tenían la tabla (CREATE IF NOT EXISTS no agrega columnas nuevas). Espeja la
    # migración r2s3t4u5v6w7.
    conn.execute(
        "ALTER TABLE email_templates ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE"
    )
    # Seed idempotente de las plantillas del sistema (esquema en dos capas, MEMORIA
    # 2026-06-03): el contenido vivía SOLO en migraciones, así que con las
    # migraciones trabadas la tabla quedaba vacía y la sección /admin/email-templates
    # no tenía nada que abrir ni previsualizar. La fuente única forward del copy
    # es services/email/default_templates.py. ON CONFLICT DO NOTHING respeta lo
    # que ya exista (filas migradas o editadas por un admin).
    from services.email.default_templates import DEFAULT_TEMPLATES
    for _key, _tpl in DEFAULT_TEMPLATES.items():
        conn.execute(
            """
            INSERT INTO email_templates (key, subject, body_html, body_text, updated_by)
            VALUES (?, ?, ?, ?, 'system:migration')
            ON CONFLICT (key) DO NOTHING
            """,
            (_key, _tpl["subject"], _tpl["body_html"], _tpl["body_text"]),
        )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS emails_log (
            id           BIGSERIAL PRIMARY KEY,
            to_addr      TEXT NOT NULL,
            subject      TEXT NOT NULL,
            template_key TEXT NOT NULL,
            alquiler_id  INTEGER REFERENCES alquileres(id) ON DELETE SET NULL,
            status       TEXT NOT NULL,
            provider     TEXT NOT NULL,
            provider_id  TEXT,
            error        TEXT,
            sent_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_emails_log_alquiler ON emails_log(alquiler_id)")
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_emails_log_recordatorio
        ON emails_log(alquiler_id, template_key)
        WHERE template_key = 'recordatorio_retiro' AND status = 'sent'
    """)

    # equipos.slug (migraciones e4a7c1f8d6b2 + f5b8d2e4a9c1): columna + UNIQUE
    # constraint completo (no partial index — ese era transicional).
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS slug VARCHAR(80)")
    # A1 #635: tipo de producto (simple/kit/combo). DEFAULT 'simple'; el backfill
    # (kits con componentes → 'kit') y el CHECK viven en la migración a1c3b5f7e9d2.
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS tipo TEXT NOT NULL DEFAULT 'simple'")
    conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'equipos_slug_key' AND conrelid = 'equipos'::regclass
            ) AND NOT EXISTS (
                SELECT 1 FROM equipos WHERE slug IS NOT NULL
                GROUP BY slug HAVING COUNT(*) > 1
            ) THEN
                ALTER TABLE equipos ADD CONSTRAINT equipos_slug_key UNIQUE (slug);
            END IF;
        END $$;
    """)

    # JSONB agregadas por migraciones (b6f8d3e5a2c1, d7c9e1f3a8b2)
    conn.execute("ALTER TABLE solicitudes_modificacion ADD COLUMN IF NOT EXISTS cambios_json JSONB")
    conn.execute("ALTER TABLE spec_definitions ADD COLUMN IF NOT EXISTS tabla_columnas JSONB")

    # Canonización de spec_keys (#535): renombres idempotentes en spec_definitions.
    # ORDEN CRÍTICO: esto corre en init_db (siempre, antes del seeder y sin depender
    # de Alembic) para que el seeder NO purgue la key vieja con CASCADE — eso borraría
    # los equipo_specs de esos specs. El rename preserva la MISMA fila (mismo id), así
    # que equipo_specs y categoria_spec_templates quedan intactos (FK por id, no por key).
    # Guard NOT EXISTS: evita violar UNIQUE(categoria_raiz_id, spec_key) si la canónica
    # ya existiera (un merge real se resolvería en migración, no acá).
    conn.execute("""
        UPDATE spec_definitions sd
           SET spec_key = 'consumo_w', label = 'Consumo eléctrico', updated_at = NOW()
         WHERE sd.spec_key = 'power_consumption_w'
           AND sd.categoria_raiz_id = (SELECT id FROM categorias WHERE nombre = 'Cámaras')
           AND NOT EXISTS (
               SELECT 1 FROM spec_definitions x
                WHERE x.categoria_raiz_id = sd.categoria_raiz_id AND x.spec_key = 'consumo_w'
           )
    """)
    conn.execute("""
        UPDATE spec_definitions sd
           SET spec_key = 'distancia_minima_cm', updated_at = NOW()
         WHERE sd.spec_key = 'distancia_minima_m'
           AND sd.categoria_raiz_id = (SELECT id FROM categorias WHERE nombre = 'Lentes')
           AND NOT EXISTS (
               SELECT 1 FROM spec_definitions x
                WHERE x.categoria_raiz_id = sd.categoria_raiz_id AND x.spec_key = 'distancia_minima_cm'
           )
    """)

    # Fechas TEXT → tipo nativo (migración e2c6f4a8b1d7). Las fechas se
    # guardaban como strings ISO; ahora son TIMESTAMP/DATE. Idempotente: solo
    # convierte si la columna sigue siendo 'text'. Defensivo: limpia valores
    # no-ISO a NULL antes del cast y re-aplica NOT NULL solo si quedó limpio.
    for tabla, col, tipo, not_null in (
        ("alquileres", "fecha_desde", "timestamp", False),
        ("alquileres", "fecha_hasta", "timestamp", False),
        ("equipo_mantenimiento", "fecha", "timestamp", True),
        ("equipo_mantenimiento", "fecha_hasta", "timestamp", False),
        ("equipo_mantenimiento", "proxima_revision", "timestamp", False),
        ("alquiler_pagos", "fecha", "timestamp", False),
        ("equipos", "fecha_compra", "date", False),
    ):
        renotnull = (
            f"IF NOT EXISTS (SELECT 1 FROM {tabla} WHERE {col} IS NULL) THEN "
            f"ALTER TABLE {tabla} ALTER COLUMN {col} SET NOT NULL; END IF;"
            if not_null else ""
        )
        conn.execute(f"""
            DO $$
            BEGIN
                IF (SELECT data_type FROM information_schema.columns
                    WHERE table_name = '{tabla}' AND column_name = '{col}') = 'text' THEN
                    ALTER TABLE {tabla} ALTER COLUMN {col} DROP NOT NULL;
                    UPDATE {tabla} SET {col} = NULL
                        WHERE {col} !~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}';
                    ALTER TABLE {tabla} ALTER COLUMN {col} TYPE {tipo}
                        USING NULLIF(TRIM({col}), '')::{tipo};
                    {renotnull}
                END IF;
            END $$;
        """)

    # ── Estudio (singleton E1) ──────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS estudio (
            id             SERIAL PRIMARY KEY,
            equipo_id      INTEGER,
            nombre         TEXT NOT NULL DEFAULT 'El Estudio',
            tagline        TEXT NOT NULL DEFAULT '',
            descripcion    TEXT NOT NULL DEFAULT '',
            precio_hora    INTEGER NOT NULL DEFAULT 0,
            min_horas      INTEGER NOT NULL DEFAULT 2,
            open_hour      INTEGER NOT NULL DEFAULT 8,
            close_hour     INTEGER NOT NULL DEFAULT 22,
            buffer_horas   INTEGER NOT NULL DEFAULT 0,
            pack_activo    BOOLEAN NOT NULL DEFAULT TRUE,
            pack_nombre    TEXT NOT NULL DEFAULT '',
            pack_descripcion TEXT NOT NULL DEFAULT '',
            pack_precio    INTEGER NOT NULL DEFAULT 0,
            features_json  TEXT,
            faq_json       TEXT,
            updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS estudio_fotos (
            id           SERIAL PRIMARY KEY,
            estudio_id   INTEGER NOT NULL REFERENCES estudio(id) ON DELETE CASCADE,
            url          TEXT NOT NULL,
            path         TEXT,
            orden        INTEGER NOT NULL DEFAULT 0,
            es_principal BOOLEAN NOT NULL DEFAULT FALSE,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_estudio_fotos_estudio_orden
        ON estudio_fotos(estudio_id, orden)
    """)
    # E2.1: anticipación mínima de reserva del estudio (en horas). Solo aplica
    # al espacio (no a equipos). 0 = sin tope.
    conn.execute("ALTER TABLE estudio ADD COLUMN IF NOT EXISTS anticipacion_min_horas INTEGER NOT NULL DEFAULT 0")
    # Ficha pública: ubicación + prueba social (editables desde el back-office).
    conn.execute("ALTER TABLE estudio ADD COLUMN IF NOT EXISTS direccion TEXT NOT NULL DEFAULT ''")
    conn.execute("ALTER TABLE estudio ADD COLUMN IF NOT EXISTS como_llegar TEXT NOT NULL DEFAULT ''")
    conn.execute("ALTER TABLE estudio ADD COLUMN IF NOT EXISTS testimonios_json TEXT")
    # Mapa: el dueño pega un link/iframe; el backend lo parsea y guarda ambos.
    conn.execute("ALTER TABLE estudio ADD COLUMN IF NOT EXISTS mapa_url TEXT NOT NULL DEFAULT ''")
    conn.execute("ALTER TABLE estudio ADD COLUMN IF NOT EXISTS mapa_embed_url TEXT NOT NULL DEFAULT ''")
    # E4: slots fijos recurrentes mensuales (ej. "miércoles 8-20 Filmar $X jun-dic").
    # Bloquean su franja para el público mientras el rango de meses esté activo y
    # generan un pedido por mes (tipo='estudio_fijo') para estadísticas + pagos.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS estudio_slots_fijos (
            id            SERIAL PRIMARY KEY,
            cliente       TEXT NOT NULL,
            dia_semana    INTEGER NOT NULL,        -- 0=Lunes .. 6=Domingo (date.weekday())
            hora_desde    INTEGER NOT NULL,        -- hora entera 0-24
            hora_hasta    INTEGER NOT NULL,
            valor_mensual INTEGER NOT NULL DEFAULT 0,
            mes_desde     TEXT NOT NULL,           -- 'YYYY-MM'
            mes_hasta     TEXT NOT NULL,           -- 'YYYY-MM'
            activo        BOOLEAN NOT NULL DEFAULT TRUE,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Vincula cada pedido mensual generado con su slot, para regenerar futuros sin
    # tocar pasados/pagados. NULL en todo pedido normal → cero impacto.
    conn.execute("ALTER TABLE alquileres ADD COLUMN IF NOT EXISTS estudio_slot_id INTEGER REFERENCES estudio_slots_fijos(id) ON DELETE SET NULL")
    # v2-C: pack curado. El admin elige a mano qué equipos integran el pack
    # (reemplaza "todo lo de las categorías Grip/Iluminación/Modificadores"). La
    # disponibilidad de la franja sigue saliendo del motor sagrado.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS estudio_pack_equipos (
            id          SERIAL PRIMARY KEY,
            estudio_id  INTEGER NOT NULL REFERENCES estudio(id) ON DELETE CASCADE,
            equipo_id   INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            orden       INTEGER NOT NULL DEFAULT 0,
            UNIQUE (estudio_id, equipo_id)
        )
    """)

    # Registro de búsquedas del catálogo público (analítica interna). Acompaña a
    # la migración i1c2d3e4f5a6 — acá garantizamos su creación en cada boot
    # (init_db corre siempre y es idempotente), sin depender de la cadena de
    # alembic. query_text = término crudo; query_norm = normalizado para agrupar.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS search_queries (
            id           SERIAL PRIMARY KEY,
            query_text   VARCHAR(120) NOT NULL,
            query_norm   VARCHAR(120) NOT NULL,
            result_count INTEGER NOT NULL DEFAULT 0,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_search_queries_norm ON search_queries(query_norm)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_search_queries_created ON search_queries(created_at)"
    )
    # Click-through: qué resultado abre el usuario tras una búsqueda. Es la señal
    # que faltaba para, a futuro, aprender qué encontró la gente (ranking por
    # comportamiento, sinónimos). Cada fila liga una search_queries con el equipo
    # que se abrió. Acompaña a la migración s3t4u5v6w7x8 (esquema en dos capas).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS search_clicks (
            id           SERIAL PRIMARY KEY,
            query_id     INTEGER NOT NULL REFERENCES search_queries(id) ON DELETE CASCADE,
            equipo_id    INTEGER REFERENCES equipos(id) ON DELETE SET NULL,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_search_clicks_query ON search_clicks(query_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_search_clicks_equipo ON search_clicks(equipo_id)"
    )
    # Seed idempotente: inserta la fila singleton si no existe, con los valores
    # del copy original de src/data/studio.ts. Precios en 0 (el dueño los setea).
    import json as _json
    # Lista canónica de 16 features. Las con value="" se ocultan del público
    # (filtro en src/routes/estudio.tsx) y solo aparecen en /admin/estudio
    # como casilleros para que el dueño los complete a medida.
    _features_seed = _json.dumps([
        {"label": "Superficie", "value": ""},
        {"label": "Altura", "value": ""},
        {"label": "Ciclorama", "value": "6×6 m"},
        {"label": "Climatización", "value": "Sí"},
        {"label": "Living", "value": "Sí"},
        {"label": "Área de trabajo", "value": "Sí"},
        {"label": "Entrada para autos", "value": "Sí"},
        {"label": "Cocina", "value": "Sí"},
        {"label": "WiFi", "value": ""},
        {"label": "Camarín / vestuario", "value": ""},
        {"label": "Potencia eléctrica", "value": ""},
        {"label": "Insonorización", "value": ""},
        {"label": "Pet friendly", "value": ""},
        {"label": "Acceso 24h", "value": ""},
        {"label": "Estacionamiento", "value": ""},
        {"label": "Rigging / tomas de techo", "value": ""},
    ])
    _faq_seed = _json.dumps([
        {"q": "¿Cuál es el mínimo de reserva?",
         "a": "El mínimo es de 2 horas. Para producciones más cortas, escribínos por WhatsApp y vemos."},
        {"q": "¿Cómo se abona?",
         "a": "Aceptamos transferencia bancaria, MercadoPago y efectivo. Se reserva con un 50% del total al confirmar la fecha."},
        {"q": "¿Puedo llevar equipo extra?",
         "a": "Sí, podés traer cualquier equipo propio. Si necesás algo puntual también podés alquilarlo en Rambla y armar todo en un único pedido."},
        {"q": "¿Tienen estacionamiento?",
         "a": "Estacionamiento sobre la calle (zona azul gratuita los fines de semana). Para descarga rápida de equipos hay acceso directo."},
        {"q": "¿Incluye asistente / iluminador?",
         "a": "Por defecto el estudio se reserva sin staff. Si necesás un asistente o iluminador, lo coordinamos aparte — escribínos antes."},
        {"q": "¿Puedo cancelar o reagendar?",
         "a": "Hasta 48 hs antes del shoot podés reagendar sin costo. Cancelaciones con menos aviso pierden la seña."},
    ])
    conn.execute("""
        INSERT INTO estudio (
            id, nombre, tagline, descripcion,
            precio_hora, min_horas, open_hour, close_hour, buffer_horas,
            pack_activo, pack_nombre, pack_descripcion, pack_precio,
            features_json, faq_json
        )
        SELECT
            1,
            'El Estudio',
            'Foto y video en Mar del Plata',
            'Un espacio para producciones audiovisuales con todos los equipos de Rambla Rental a mano. '
            'Ideal para rodajes grandes — flexible para los chicos.',
            0, 2, 8, 22, 0,
            TRUE,
            'Pack Todo Incluido',
            'Todas las luces y griperías del estudio sin pensar en sumar ítem por ítem. '
            'Llegás con la cámara y filmás.',
            0,
            %s,
            %s
        WHERE NOT EXISTS (SELECT 1 FROM estudio WHERE id = 1)
    """, (_features_seed, _faq_seed))

    # Centinela del Estudio (E2): el espacio físico modelado como un equipo de
    # cantidad=1, para que las reservas por hora reusen el motor de stock/overlap
    # SAGRADO sin lógica nueva. Es un recurso interno: invisible al catálogo,
    # filtros, listado admin, ranking y specs (es_recurso_interno=TRUE). Idempotente:
    # solo se crea si el estudio todavía no tiene un equipo asociado.
    est_row = conn.execute("SELECT equipo_id FROM estudio WHERE id = 1").fetchone()
    if est_row is not None and est_row["equipo_id"] is None:
        cur_cent = conn.execute("""
            INSERT INTO equipos (nombre, cantidad, visible_catalogo, dueno, es_recurso_interno)
            VALUES ('Estudio (espacio)', 1, 0, 'Rambla', TRUE)
            RETURNING id
        """)
        centinela_id = cur_cent.fetchone()["id"]
        conn.execute("UPDATE estudio SET equipo_id = ? WHERE id = 1", (centinela_id,))

    # ── Media pipeline no-destructivo (F1 — i1j2k3l4m5n6) ──────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS media_assets (
            id           BIGSERIAL PRIMARY KEY,
            kind         TEXT NOT NULL,
            original_key TEXT,
            original_ct  TEXT,
            width        INTEGER,
            height       INTEGER,
            bytes        INTEGER,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS media_variants (
            id           BIGSERIAL PRIMARY KEY,
            asset_id     BIGINT NOT NULL REFERENCES media_assets(id) ON DELETE CASCADE,
            name         TEXT NOT NULL,
            key          TEXT,
            url          TEXT,
            content_type TEXT NOT NULL DEFAULT 'image/webp',
            width        INTEGER,
            height       INTEGER,
            bytes        INTEGER,
            params       JSONB DEFAULT '{}',
            created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(asset_id, name)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_media_variants_asset
        ON media_variants(asset_id)
    """)
    conn.execute("ALTER TABLE estudio_fotos ADD COLUMN IF NOT EXISTS media_id BIGINT REFERENCES media_assets(id) ON DELETE SET NULL")

    # ── Galería multi-foto de equipos (F2 — k1l2m3n4o5p6) ───────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS equipo_fotos (
            id           SERIAL PRIMARY KEY,
            equipo_id    INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            media_id     BIGINT REFERENCES media_assets(id) ON DELETE SET NULL,
            url          TEXT NOT NULL,
            path         TEXT,
            orden        INTEGER NOT NULL DEFAULT 0,
            es_principal BOOLEAN NOT NULL DEFAULT FALSE,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_equipo_fotos_equipo_orden
        ON equipo_fotos(equipo_id, orden)
    """)
    conn.execute("ALTER TABLE marcas ADD COLUMN IF NOT EXISTS media_id BIGINT REFERENCES media_assets(id) ON DELETE SET NULL")

    conn.execute("CREATE SEQUENCE IF NOT EXISTS numero_pedido_seq")

    # Seed the sequence to the current max so nextval never collides with existing data.
    # GREATEST ensures we never decrease an already-advanced sequence on restart.
    conn.execute("""
        SELECT setval('numero_pedido_seq',
            GREATEST(
                (SELECT COALESCE(MAX(numero_pedido), 0) FROM alquileres WHERE numero_pedido IS NOT NULL),
                (SELECT last_value FROM numero_pedido_seq)
            ), true)
    """)

    # ── Facturación electrónica ARCA (#1139) ─────────────────────────────────
    # Motor portable en `backend/arca_fe/`; adapter en `backend/services/facturacion/`.
    # Esquema en dos capas (MEMORIA 2026-06-03): también en migración a2b3c4d5e6f7.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS facturas (
            id                      SERIAL PRIMARY KEY,
            pedido_id               INTEGER NOT NULL REFERENCES alquileres(id) ON DELETE CASCADE,
            emisor                  TEXT NOT NULL,
            ambiente                TEXT NOT NULL,
            cbte_tipo               INTEGER NOT NULL,
            pto_vta                 INTEGER NOT NULL,
            cbte_nro                INTEGER,
            cae                     TEXT,
            cae_vto                 DATE,
            doc_tipo                INTEGER NOT NULL,
            doc_nro                 TEXT NOT NULL,
            condicion_iva_receptor  INTEGER NOT NULL,
            concepto                INTEGER NOT NULL,
            imp_neto                INTEGER NOT NULL,
            imp_iva                 INTEGER NOT NULL DEFAULT 0,
            imp_total               INTEGER NOT NULL,
            moneda                  TEXT NOT NULL DEFAULT 'PES',
            cliente_cuit            TEXT,
            razon_social            TEXT,
            qr_payload              TEXT,
            pdf_key                 TEXT,
            estado                  TEXT NOT NULL DEFAULT 'pendiente',
            nota_credito_de         INTEGER REFERENCES facturas(id),
            raw_request             JSONB,
            raw_response            JSONB,
            errores                 JSONB,
            fecha_emision           TIMESTAMPTZ,
            created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by              TEXT
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_factura_vigente_por_pedido
        ON facturas (pedido_id) WHERE estado IN ('pendiente','emitida')
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_facturas_pedido ON facturas (pedido_id)
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS afip_ta (
            ambiente   TEXT NOT NULL,
            emisor     TEXT NOT NULL,
            token      TEXT NOT NULL,
            sign       TEXT NOT NULL,
            expira_at  TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (ambiente, emisor)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS emisores_arca (
            id              SERIAL PRIMARY KEY,
            nombre          TEXT NOT NULL UNIQUE,
            cuit            TEXT NOT NULL,
            pto_vta         INTEGER NOT NULL,
            condicion_iva   TEXT NOT NULL,
            cert_enc        BYTEA,
            key_enc         BYTEA,
            activo          BOOLEAN NOT NULL DEFAULT true,
            notas           TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
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
