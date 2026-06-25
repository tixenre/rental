"""database/schema.py — bootstrap idempotente del esquema (#501 Fase 5).

`init_db()` crea/asegura todas las tablas, índices y extensiones (capa 1 del
esquema en dos capas; Alembic es la capa 2 — decisión 2026-06-03). Move-verbatim
desde `database.py`; usa la conexión cruda + los wrappers del spine (`core`).
"""
import logging
import time

import psycopg2

from busqueda.motor import CAMPO_PLANTILLA
from database.core import get_connection_params, PGConnection
from database.auto_tags import regenerate_auto_tags_all

logger = logging.getLogger(__name__)


def _ddl_retry(conn, sql: str, retries: int = 3) -> None:
    """Ejecuta `sql` reintentando si Postgres devuelve 'tuple concurrently updated'.

    Esa condición ocurre cuando autovacuum toca pg_catalog.pg_proc justo mientras
    CREATE OR REPLACE FUNCTION escribe ahí. Es transitorio y reintentar resuelve.
    """
    for attempt in range(retries):
        try:
            conn.execute(sql)
            return
        except psycopg2.Error as exc:
            if "tuple concurrently updated" in str(exc) and attempt < retries - 1:
                time.sleep(0.2 * (2 ** attempt))
            else:
                raise


def init_db():
    """Crear todas las tablas si no existen."""
    raw_conn = psycopg2.connect(**get_connection_params())
    raw_conn.set_isolation_level(0)  # Autocommit
    conn = PGConnection(raw_conn)
    try:
        _init_db_schema(conn)
    finally:
        conn.close()
    logger.info("Base de datos PostgreSQL inicializada")


def _init_db_schema(conn):
    """Aplica todo el DDL idempotente sobre `conn`. La conexión y su cierre los
    maneja `init_db` con try/finally — separar el cuerpo evita re-indentar ~1500
    líneas y garantiza que `conn.close()` corra aunque un DDL falle (sin leak)."""
    # ── Búsqueda fuzzy: extensiones + helper inmutable ────────────────────────
    # `pg_trgm` (similitud por trigramas → typos + ranking) y `unaccent` (folding
    # de acentos: "bateria" = "Batería"). El motor único vive en backend/busqueda;
    # acá garantizamos que la infra de BD que necesita exista. `unaccent()` es
    # STABLE (no indexable); `f_unaccent` la envuelve IMMUTABLE — la forma
    # canónica que usan tanto las queries (busqueda.campo_sql) como los índices
    # GIN trigram de abajo. Idempotente. Ver decisión 2026-06-06 (motor de búsqueda).
    conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    conn.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    # CREATE OR REPLACE FUNCTION toca pg_proc y puede colisionar con autovacuum
    # corriendo sobre el catálogo en CI. Reintentamos hasta 3 veces con backoff
    # exponencial corto — en prod este DDL nunca corre en caliente.
    _ddl_retry(
        conn,
        "CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text AS "
        "$$ SELECT public.unaccent('public.unaccent', $1) $$ "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT",
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
            foto_url_sm      TEXT,   -- variante 600px de la foto principal para srcset (NULL = sin variante → el front usa foto_url)
            foto_url_thumb   TEXT,   -- variante 160px para thumbnails de ~48px (NULL = sin variante → el front usa foto_url_sm)
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

    # Migration: variantes AVIF + LQIP denormalizadas de la foto principal (perf
    # del catálogo). Acompañan a foto_url/foto_url_sm/foto_url_thumb: el front sirve
    # <picture> con AVIF (~20-30% menos bytes que webp) + blur-up LQIP sin inflar el
    # payload del listado (127 equipos × ~250 bytes). Todas nullable: legacy = NULL
    # → fallback seguro a la variante webp. Por ahora quedan vacías: las puebla un
    # PR posterior (ingesta/sync de la foto principal); mientras tanto la web usa webp.
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS foto_url_avif TEXT")
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS foto_url_sm_avif TEXT")
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS foto_url_thumb_avif TEXT")
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS foto_lqip TEXT")

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
    conn.execute("ALTER TABLE marcas ADD COLUMN IF NOT EXISTS logo_url_sm TEXT")

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
    # nombre_completo_renaper: nombre legal autoritativo tal cual lo devuelve
    # RENAPER (full_name), sin reconstruirlo de nombre+apellido — importa para
    # los contratos, donde el string legal exacto cuenta.
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS nombre_completo_renaper TEXT")
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS fecha_nacimiento_renaper TEXT")
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS direccion_renaper TEXT")
    # Datos adicionales del documento (todos solo texto — Ley 25.326).
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS genero_renaper TEXT")
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS nacionalidad_renaper TEXT")
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS lugar_nacimiento_renaper TEXT")
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS vencimiento_documento_renaper TEXT")
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS emision_documento_renaper TEXT")
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS tipo_documento_renaper TEXT")
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS estado_civil_renaper TEXT")
    # apodo: alias opcional para saludos informales en mails (siempre editable).
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS apodo TEXT")
    # Estado del flujo de verificación Didit (PR2). El gate de pedidos sigue usando
    # `dni_validado_at IS NOT NULL` como criterio — este campo añade visibilidad de
    # estados intermedios para el portal (rechazado, en_revision).
    # Espejo de la migración i9j0k1l2m3n4 (esquema en dos capas, MEMORIA 2026-06-03).
    conn.execute(
        "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS "
        "dni_verificacion_estado TEXT NOT NULL DEFAULT 'no_verificado'"
    )
    conn.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS dni_verificacion_motivo TEXT")

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
    # Nombre distinto del de arriba (`idx_spec_def_compat`, sobre spec_key): antes
    # ambos se llamaban igual → con IF NOT EXISTS este nunca se creaba (#921).
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_spec_def_es_compat "
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
        ON CONFLICT DO NOTHING
    """)
    # `ON CONFLICT DO NOTHING` SIN target (no `(nombre) WHERE activa`): la tabla
    # tiene DOS unique (nombre-activo + idx_cuentas_socio sobre socio). Si una
    # cuenta de socio se renombró/desactivó, su nombre sale del índice parcial
    # pero su socio sigue en idx_cuentas_socio → el ON CONFLICT (nombre) no lo
    # atrapaba y el seed reventaba con UniqueViolation en cada boot (#932). Sin
    # target, salta ante CUALQUIER choque → idempotente de verdad.
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
    conn.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS destacado BOOLEAN DEFAULT FALSE")
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
    # Backfill de slugs faltantes (fuente única; idempotente). Acá, en el
    # bootstrap, en vez del viejo self-heal que vivía dentro del export (#922).
    from dataio.slug import backfill_equipos_slug
    backfill_equipos_slug(conn)

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
            content_hash TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        ALTER TABLE media_assets
        ADD COLUMN IF NOT EXISTS content_hash TEXT
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_media_assets_kind_hash
        ON media_assets(kind, content_hash)
        WHERE content_hash IS NOT NULL
    """)
    conn.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS lqip TEXT")
    conn.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'ready'")
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
    conn.execute("ALTER TABLE estudio_fotos ADD COLUMN IF NOT EXISTS url_sm TEXT")
    conn.execute("ALTER TABLE estudio_fotos ADD COLUMN IF NOT EXISTS url_avif TEXT")
    conn.execute("ALTER TABLE estudio_fotos ADD COLUMN IF NOT EXISTS url_sm_avif TEXT")

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

    # ── Talleres (workshops públicos con formulario de inscripción) ──────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS talleres (
            id                   SERIAL PRIMARY KEY,
            slug                 VARCHAR(120) NOT NULL UNIQUE,
            nombre               TEXT NOT NULL,
            subtitulo            TEXT NOT NULL DEFAULT '',
            instructor_nombre    TEXT NOT NULL,
            instructor_bio       TEXT NOT NULL DEFAULT '',
            instructor_proyectos TEXT NOT NULL DEFAULT '',
            descripcion          TEXT NOT NULL DEFAULT '',
            publico_objetivo     TEXT NOT NULL DEFAULT '',
            programa_teorica     JSONB NOT NULL DEFAULT '[]',
            programa_practica    JSONB NOT NULL DEFAULT '[]',
            fecha_inicio         DATE NOT NULL,
            fecha_fin            DATE NOT NULL,
            horario              TEXT NOT NULL DEFAULT '',
            cupos_total          INTEGER NOT NULL DEFAULT 12,
            cupos_confirmados    INTEGER NOT NULL DEFAULT 0,
            precio_total         INTEGER NOT NULL DEFAULT 0,
            precio_sena          INTEGER NOT NULL DEFAULT 0,
            pago_alias           TEXT NOT NULL DEFAULT '',
            pago_cbu             TEXT NOT NULL DEFAULT '',
            pago_banco           TEXT NOT NULL DEFAULT '',
            direccion            TEXT NOT NULL DEFAULT '',
            notif_email          TEXT NOT NULL DEFAULT '',
            activo               BOOLEAN NOT NULL DEFAULT TRUE,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS taller_inscripciones (
            id              SERIAL PRIMARY KEY,
            taller_id       INTEGER NOT NULL REFERENCES talleres(id) ON DELETE CASCADE,
            nombre          TEXT NOT NULL,
            email           TEXT NOT NULL,
            telefono        TEXT NOT NULL,
            experiencia     TEXT,
            comprobante_url TEXT,
            en_lista_espera BOOLEAN NOT NULL DEFAULT FALSE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_taller_inscripciones_taller "
        "ON taller_inscripciones(taller_id)"
    )
    # Seed idempotente del workshop de Jime Troncoso (julio 2026)
    conn.execute("ALTER TABLE talleres ADD COLUMN IF NOT EXISTS instructor_foto_url TEXT NOT NULL DEFAULT ''")
    conn.execute("ALTER TABLE talleres ADD COLUMN IF NOT EXISTS numero_edicion INTEGER NOT NULL DEFAULT 1")
    conn.execute("ALTER TABLE talleres ADD COLUMN IF NOT EXISTS proxima_edicion_slug TEXT NOT NULL DEFAULT ''")
    conn.execute("ALTER TABLE taller_inscripciones ADD COLUMN IF NOT EXISTS comprobante_key TEXT")
    conn.execute("ALTER TABLE talleres ADD COLUMN IF NOT EXISTS instructor_media_id BIGINT REFERENCES media_assets(id) ON DELETE SET NULL")
    import json as _json_t
    _programa_teorica = _json_t.dumps([
        "Qué es la dirección de arte y cuál es su función dentro de un proyecto",
        "Cómo se compone y se coordina un equipo",
        "Análisis de proyectos reales: videoclip, publicidad, ambientación en evento y foto producto",
        "Armado de presupuesto (sí, vamos a hablar de números)",
        "Cómo mostrar tus proyectos y crecer dentro de la industria",
    ])
    _programa_practica = _json_t.dumps([
        "Llegamos a la mejor parte (o la que a mí más me divierte): crear el set.",
        "En esta instancia se suman el director de fotografía (Pablo Isa) y el gaffer (Tincho Santini), "
        "que se encargarán del equipo técnico, junto con Rambla Rental, para que la práctica sea aún "
        "más real y podamos ver el resultado final.",
    ])
    _instructor_proyectos = (
        "Universal LATAM, CheNetflix, Shorta, Spotify, Gancia, Skyy, Dr Lemon, Luigi Bosca, "
        "Las Pastillas del Abuelo, Kevin Johansen, Los Pericos & El Plan de la Mariposa, "
        "Agapornis, Guolis, Lucciano's, La Fonte D'Oro, Billabong, Atomik, Kappa x Huracán, "
        "Bruto, Turboblender, Shell, Hops"
    )
    conn.execute(
        """
        INSERT INTO talleres (
            slug, nombre, subtitulo,
            instructor_nombre, instructor_bio, instructor_proyectos,
            descripcion, publico_objetivo,
            programa_teorica, programa_practica,
            fecha_inicio, fecha_fin, horario,
            cupos_total, precio_total, precio_sena,
            pago_alias, pago_cbu, pago_banco,
            direccion, notif_email, activo
        )
        VALUES (
            'direccion-de-arte-jime-troncoso',
            'Workshop Dirección de Arte', 'x Jime Troncoso',
            'Jime Troncoso',
            '26 años, marplatense viviendo en CABA. Desde 2020 colabora con marcas, agencias y equipos '
            'creativos en proyectos artísticos, audiovisuales y fotográficos, pensados para entornos '
            'digitales y físicos.',
            %s,
            'Si llegaste hasta acá: gracias, estoy muy emocionada por hacer realidad este proyecto. '
            'El workshop incluye 2 clases en Rambla Estudio y son 12 cupos, porque quiero que sea '
            'un espacio donde podamos tener un intercambio de aprendizajes y conocimientos.',
            'Directores/as, asistentes y ayudantes de arte · Creadores de contenido, fotógrafos/as, filmmakers · '
            'Estudiantes de comunicación audiovisual, cine o fotografía · '
            'Personas que les interese trabajar sobre lo artístico y estético a la hora de crear proyectos',
            %s::jsonb, %s::jsonb,
            '2026-07-11', '2026-07-18', '9 a 13 hs',
            12, 200000, 100000,
            'rambla.estudio', '0170239440000032889112', 'BBVA',
            'Chaco 1392 — Rambla Estudio',
            'jimetroncoso44@gmail.com',
            TRUE
        )
        ON CONFLICT (slug) DO NOTHING
        """,
        (_instructor_proyectos, _programa_teorica, _programa_practica),
    )
    # Actualizaciones idempotentes para filas ya existentes (ON CONFLICT DO NOTHING no las toca).
    conn.execute(
        "UPDATE talleres SET notif_email = %s WHERE slug = %s AND notif_email = ''",
        ("jimetroncoso44@gmail.com", "direccion-de-arte-jime-troncoso"),
    )
    conn.execute(
        "UPDATE talleres SET instructor_proyectos = %s WHERE slug = %s",
        (_instructor_proyectos, "direccion-de-arte-jime-troncoso"),
    )
    conn.execute(
        "UPDATE talleres SET programa_teorica = %s::jsonb, programa_practica = %s::jsonb WHERE slug = %s",
        (_programa_teorica, _programa_practica, "direccion-de-arte-jime-troncoso"),
    )
    conn.execute(
        "UPDATE talleres SET instructor_bio = %s WHERE slug = %s",
        (
            "26 años, marplatense viviendo en CABA. Desde 2020 colabora con marcas, agencias y equipos "
            "creativos en proyectos artísticos, audiovisuales y fotográficos, pensados para entornos "
            "digitales y físicos.",
            "direccion-de-arte-jime-troncoso",
        ),
    )
    conn.execute(
        "UPDATE talleres SET publico_objetivo = %s WHERE slug = %s",
        (
            "Directores/as, asistentes y ayudantes de arte · Creadores de contenido, fotógrafos/as, filmmakers · "
            "Estudiantes de comunicación audiovisual, cine o fotografía · "
            "Personas que les interese trabajar sobre lo artístico y estético a la hora de crear proyectos",
            "direccion-de-arte-jime-troncoso",
        ),
    )
    # Seed 2da edición (agosto 2026) — mismos contenidos, fechas distintas.
    _descripcion_taller = (
        "Si llegaste hasta acá: gracias, estoy muy emocionada por hacer realidad este proyecto. "
        "El workshop incluye 2 clases en Rambla Estudio y son 12 cupos, porque quiero que sea "
        "un espacio donde podamos tener un intercambio de aprendizajes y conocimientos."
    )
    _publico_objetivo_taller = (
        "Directores/as, asistentes y ayudantes de arte · Creadores de contenido, fotógrafos/as, filmmakers · "
        "Estudiantes de comunicación audiovisual, cine o fotografía · "
        "Personas que les interese trabajar sobre lo artístico y estético a la hora de crear proyectos"
    )
    _instructor_bio_taller = (
        "26 años, marplatense viviendo en CABA. Desde 2020 colabora con marcas, agencias y equipos "
        "creativos en proyectos artísticos, audiovisuales y fotográficos, pensados para entornos "
        "digitales y físicos."
    )
    conn.execute(
        """
        INSERT INTO talleres (
            slug, nombre, subtitulo,
            instructor_nombre, instructor_bio, instructor_proyectos,
            descripcion, publico_objetivo,
            programa_teorica, programa_practica,
            fecha_inicio, fecha_fin, horario,
            cupos_total, precio_total, precio_sena,
            pago_alias, pago_cbu, pago_banco,
            direccion, notif_email, activo,
            numero_edicion
        )
        VALUES (
            'direccion-de-arte-jime-troncoso-2',
            'Workshop Dirección de Arte', 'x Jime Troncoso',
            'Jime Troncoso',
            %s, %s, %s, %s,
            %s::jsonb, %s::jsonb,
            '2026-08-15', '2026-08-22', '9 a 13 hs',
            12, 200000, 100000,
            'rambla.estudio', '0170239440000032889112', 'BBVA',
            'Chaco 1392 — Rambla Estudio',
            'jimetroncoso44@gmail.com',
            TRUE, 2
        )
        ON CONFLICT (slug) DO NOTHING
        """,
        (
            _instructor_bio_taller, _instructor_proyectos,
            _descripcion_taller, _publico_objetivo_taller,
            _programa_teorica, _programa_practica,
        ),
    )
    # Linkear ediciones y asegurar numero_edicion correcto.
    conn.execute(
        "UPDATE talleres SET numero_edicion = 1, proxima_edicion_slug = 'direccion-de-arte-jime-troncoso-2' WHERE slug = 'direccion-de-arte-jime-troncoso'",
    )
    conn.execute(
        "UPDATE talleres SET numero_edicion = 2, proxima_edicion_slug = '' WHERE slug = 'direccion-de-arte-jime-troncoso-2'",
    )

    # ── Carritos activos (#280 Fase 1): persistencia server-side ──────────────
    # Cada heartbeat del frontend hace upsert por session_id (UUID v4 generado
    # en el cliente). cliente_id se asocia automáticamente si hay sesión activa.
    # items_json incluye nombre del equipo para el dashboard sin joins adicionales.
    # confirmado=TRUE cuando el cliente confirma el pedido (cierre del funnel).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS carritos_activos (
            id              SERIAL PRIMARY KEY,
            session_id      TEXT NOT NULL UNIQUE,
            cliente_id      INTEGER REFERENCES clientes(id) ON DELETE SET NULL,
            items_json      JSONB NOT NULL DEFAULT '[]',
            fecha_desde     DATE,
            fecha_hasta     DATE,
            hora_desde      TEXT,
            hora_hasta      TEXT,
            total_items     INTEGER NOT NULL DEFAULT 0,
            monto_estimado  INTEGER NOT NULL DEFAULT 0,
            confirmado      BOOLEAN NOT NULL DEFAULT FALSE,
            abandonado_en   TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_carritos_updated "
        "ON carritos_activos(updated_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_carritos_cliente "
        "ON carritos_activos(cliente_id) WHERE cliente_id IS NOT NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_carritos_activos_no_conf "
        "ON carritos_activos(updated_at DESC) WHERE NOT confirmado"
    )

    # ── Registro de errores del servidor ──────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS server_errors (
            id          SERIAL PRIMARY KEY,
            route       TEXT NOT NULL,
            error_type  TEXT NOT NULL,
            message     TEXT NOT NULL DEFAULT '',
            traceback   TEXT NOT NULL DEFAULT '',
            request_id  TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_server_errors_created "
        "ON server_errors(created_at DESC)"
    )

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
