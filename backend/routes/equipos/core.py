"""
routes/equipos.py — CRUD de equipos, kits, etiquetas, categorías y fichas.
"""

import calendar as _cal
import datetime
import logging
import re
from datetime import date as _date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Query, HTTPException, Request, Response
from pydantic import BaseModel, Field

from database import (
    get_db, row_to_dict, attach_tags, attach_kit, attach_categorias,
    attach_ficha, attach_specs_destacados, attach_specs_estructuradas,
    regenerate_auto_tags, regenerate_auto_tags_batch,
    MARCA_SUBQUERY, MARCA_NOMBRE_EXPR,
)
from busqueda import construir
from reservas import (
    calcular_disponibilidad,
    reservado_total,
    ESTADOS_RESERVADO,  # noqa: F401 — re-export canónico (guard: test_reservas_sql_safety)
)
from reservas.disponibilidad import _derivar_compuestos
from reservas.semantics import componentes_de, parientes_de
from auth.session import get_session
from auth.guards import require_admin
from services.contenido import contenido_de
from services.nombre_service import actualizar_nombres_de
# `delete_equipo` limpia el blob HTML scrapeado en R2 al borrar un equipo; los
# endpoints de fotos viven en `routes.equipos.fotos` (importan estos mismos
# helpers de `services.media.storage` por su cuenta). Lo testea
# `test_delete_equipo_r2_cleanup` parcheando estos nombres sobre `core`.
from services.media.storage import _r2_config, delete_object as _delete_from_r2

router = APIRouter()


# Campos buscables del equipo (motor único backend/busqueda). Incluye la marca
# (subquery por brand_id) y los textos de la ficha (descripción + keywords) para
# que la barra siga siendo un "find anything" — buscás "log3" o "iso 25600" y
# aparece aunque la palabra viva en un spec, no en el nombre.
_FICHA_EXPR = (
    "(SELECT string_agg(coalesce(ef.descripcion, '') || ' ' || coalesce(ef.keywords_json, ''), ' ') "
    "FROM equipo_fichas ef WHERE ef.equipo_id = e.id)"
)
CAMPOS_EQUIPO = ["e.nombre", MARCA_NOMBRE_EXPR, "e.modelo", "e.serie", _FICHA_EXPR]


# ── Modelos ──────────────────────────────────────────────────────────────────

def _validar_categoria_specs(v: Optional[str]) -> Optional[str]:
    """Valida que la categoría de specs sea una del registry (o None)."""
    if v is None or v == "":
        return None
    from specs import REGISTRY
    if v not in REGISTRY.categorias:
        validas = ", ".join(REGISTRY.categorias)
        raise ValueError(f"categoria_specs inválida: '{v}'. Opciones: {validas}")
    return v


_TIPOS_EQUIPO = frozenset({"simple", "kit", "combo"})


def _validar_tipo(v: Optional[str]) -> Optional[str]:
    if v is not None and v not in _TIPOS_EQUIPO:
        raise ValueError(f"tipo inválido: '{v}'. Opciones: simple, kit, combo")
    return v


class EquipoCreate(BaseModel):
    from pydantic import field_validator
    nombre:           str
    marca:            Optional[str]   = None
    modelo:           Optional[str]   = None
    cantidad:         int             = Field(default=1, ge=0, le=9999)
    precio_jornada:   Optional[int]   = Field(default=None, ge=0)
    precio_usd:       Optional[float] = Field(default=None, ge=0)
    roi_pct:          Optional[float] = Field(default=None, ge=0, le=100)
    valor_reposicion: Optional[float] = Field(default=None, ge=0)
    foto_url:         Optional[str]   = None
    fecha_compra:     Optional[str]   = None
    serie:            Optional[str]   = None
    bh_url:           Optional[str]   = None
    dueno:            Optional[str]   = "Rambla"
    visible_catalogo: Optional[int]   = 1
    estado:           Optional[str]   = "operativo"   # operativo / en_mantenimiento / fuera_servicio
    ficha_completa:   Optional[bool]  = False
    # Categoría de specs (1 de las 5 del registry): define qué specs aplican.
    categoria_specs: Optional[str] = None
    # Tipo de producto: 'simple' = equipo suelto, 'kit' = con accesorios compartidos,
    # 'combo' = agrupación derivada. Gobierna precio, stock y disponibilidad.
    tipo:            Optional[str]   = "simple"

    @field_validator("precio_jornada")
    @classmethod
    def validate_precio(cls, v):
        if v is not None and v < 0:
            raise ValueError("precio_jornada no puede ser negativo")
        return v

    @field_validator("cantidad")
    @classmethod
    def validate_cantidad(cls, v):
        if v is not None and v < 0:
            raise ValueError("cantidad no puede ser negativa")
        return v

    @field_validator("categoria_specs")
    @classmethod
    def validate_categoria_specs(cls, v):
        return _validar_categoria_specs(v)

    @field_validator("tipo")
    @classmethod
    def validate_tipo(cls, v):
        return _validar_tipo(v)


class EquipoUpdate(BaseModel):
    from pydantic import field_validator
    nombre:           Optional[str]   = None
    marca:            Optional[str]   = None
    modelo:           Optional[str]   = None
    cantidad:         Optional[int]   = Field(default=None, ge=0, le=9999)
    precio_jornada:   Optional[int]   = Field(default=None, ge=0)
    # Flag explícito que el frontend manda para indicar si el precio
    # viene de la fórmula (auto, false) o lo tipeó el admin a mano (true).
    # Si no se manda y se cambia precio_jornada, el endpoint infiere
    # según contexto (ver update_equipo).
    precio_jornada_manual: Optional[bool] = None
    precio_usd:       Optional[float] = Field(default=None, ge=0)
    roi_pct:          Optional[float] = Field(default=None, ge=0, le=100)
    valor_reposicion: Optional[float] = Field(default=None, ge=0)
    foto_url:         Optional[str]   = None
    fecha_compra:     Optional[str]   = None
    serie:            Optional[str]   = None
    bh_url:           Optional[str]   = None
    dueno:            Optional[str]   = None
    visible_catalogo: Optional[int]   = None
    estado:           Optional[str]   = None
    ficha_completa:   Optional[bool]  = None
    # Categoría de specs (1 de las 5 del registry): define qué specs aplican.
    categoria_specs: Optional[str] = None
    # Tipo de producto: 'simple' / 'kit' / 'combo'.
    tipo:            Optional[str]   = None

    @field_validator("precio_jornada")
    @classmethod
    def validate_precio(cls, v):
        if v is not None and v < 0:
            raise ValueError("precio_jornada no puede ser negativo")
        return v

    @field_validator("cantidad")
    @classmethod
    def validate_cantidad(cls, v):
        if v is not None and v < 0:
            raise ValueError("cantidad no puede ser negativa")
        return v

    @field_validator("categoria_specs")
    @classmethod
    def validate_categoria_specs(cls, v):
        return _validar_categoria_specs(v)

    @field_validator("tipo")
    @classmethod
    def validate_tipo(cls, v):
        return _validar_tipo(v)


# ── Disponibilidad en tiempo real ────────────────────────────────────────────

@router.get("/equipos/afuera")
def equipos_afuera():
    """
    Devuelve los equipos actualmente retirados (pedidos en estado 'retirado'
    con fecha_hasta >= hoy), con cantidad afuera y fecha de devolución.
    Respuesta: { "equipo_id": { cantidad_afuera, stock_total, devuelve, pedidos } }
    """
    today = datetime.date.today().isoformat()
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                pi.equipo_id,
                e.cantidad                                              AS stock_total,
                SUM(pi.cantidad)                                        AS cantidad_afuera,
                MIN(p.fecha_hasta)                                      AS devuelve_pronto,
                MAX(p.fecha_hasta)                                      AS devuelve_ultimo,
                STRING_AGG(
                    COALESCE(c.nombre || ' ' || c.apellido, p.cliente_nombre),
                    ', '
                )                                                       AS clientes
            FROM alquiler_items pi
            JOIN alquileres  p ON p.id  = pi.pedido_id
            JOIN equipos  e ON e.id  = pi.equipo_id
            LEFT JOIN clientes c ON c.id = p.cliente_id
            WHERE p.estado    = 'retirado'
              AND p.fecha_hasta >= %s
            GROUP BY pi.equipo_id, e.cantidad
        """, (today,)).fetchall()
        return {str(r["equipo_id"]): row_to_dict(r) for r in rows}


@router.get("/equipos/kpis")
def equipos_kpis(request: Request):
    """KPIs del inventario para el header de /admin/equipos:
    - total: equipos FÍSICOS del catálogo (no eliminados). Excluye los combos: un
      combo es un bundle (sin stock propio, precio derivado), no un equipo distinto.
    - en_uso_hoy: unidades en pedidos retirados que solapan hoy.
    - mantenimiento: equipos con mantenimiento que bloquea stock activo hoy.
    """
    require_admin(request)
    with get_db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM equipos "
            "WHERE eliminado_at IS NULL AND es_recurso_interno = FALSE AND tipo != 'combo'"
        ).fetchone()[0]
        en_uso_hoy = conn.execute("""
            SELECT COALESCE(SUM(pi.cantidad), 0)
            FROM alquiler_items pi
            JOIN alquileres p ON p.id = pi.pedido_id
            WHERE p.estado = 'retirado'
              AND p.fecha_desde::date <= CURRENT_DATE
              AND p.fecha_hasta::date >= CURRENT_DATE
        """).fetchone()[0]
        mantenimiento = conn.execute("""
            SELECT COUNT(DISTINCT equipo_id)
            FROM equipo_mantenimiento
            WHERE bloquea_stock = TRUE
              AND fecha::date <= CURRENT_DATE
              AND COALESCE(fecha_hasta, fecha)::date >= CURRENT_DATE
        """).fetchone()[0]
        return {
            "total": int(total or 0),
            "en_uso_hoy": int(en_uso_hoy or 0),
            "mantenimiento": int(mantenimiento or 0),
        }


# ── Rutas de equipos ─────────────────────────────────────────────────────────


def _stock_sin_reservas(conn) -> dict[int, int]:
    """Stock teórico de kits/combos derivado solo del stock de componentes, sin
    descontar ninguna reserva. Detecta kits imposibles de armar (components <
    cantidad requerida) independientemente de las fechas seleccionadas."""
    raw = {
        r["id"]: r["cantidad"]
        for r in conn.execute(
            "SELECT id, cantidad FROM equipos WHERE eliminado_at IS NULL"
        ).fetchall()
    }
    return _derivar_compuestos(raw, componentes_de(conn))


def _attach_disponibilidad(conn, equipos: list, desde: str, hasta: str) -> list:
    """Inyecta el campo `disponible` por equipo, usando la fuente única de
    lectura del motor (`reservas.calcular_disponibilidad`).

    Antes esta función tenía su propia query (directas + vía kit) que NO restaba
    mantenimiento ni aplicaba buffer → mostraba disponibilidad inflada respecto
    del gate real (bug #619). Ahora delega en el motor, así el catálogo refleja
    exactamente lo mismo que el chequeo de confirmación."""
    disp = calcular_disponibilidad(conn, desde, hasta)
    for eq in equipos:
        eid = eq["id"]
        # `calcular_disponibilidad` indexa por str(equipo_id); fallback al stock
        # propio si el equipo no aparece (ej. equipo nuevo sin filas asociadas).
        eq["disponible"] = disp.get(str(eid), eq.get("cantidad", 0))
    return equipos


@router.get("/equipos")
def list_equipos(
    request:       Request,
    response:      Response,
    q:                Optional[str]  = Query(None),
    etiqueta:         Optional[str]  = Query(None),
    categoria:        Optional[str]  = Query(None),
    marca:            Optional[str]  = Query(None, description="Filtra por nombre exacto de marca"),
    solo_visibles:    Optional[bool] = Query(None),
    solo_incompletos: Optional[bool] = Query(None),
    falta: Optional[str] = Query(None, description="Filtra equipos sin un campo: foto|categoria|nombre_publico|descripcion|serie|valor_reposicion (#350)"),
    incluir_eliminados: Optional[bool] = Query(None, description="Si true (solo admin), incluye soft-deleted"),
    solo_eliminados:  Optional[bool] = Query(None, description="Si true (solo admin), SOLO soft-deleted (vista papelera)"),
    sort:          Optional[str]  = Query(None, description="ranking | nombre | precio_asc | precio_desc | id"),
    spec:          Optional[list[str]] = Query(None, description="Filtros por specs: spec=key:valor"),
    page:          int = Query(1, ge=1),
    per_page:      int = Query(200, ge=1, le=500),
    desde:         Optional[str]  = Query(None, description="Fecha inicio (YYYY-MM-DD) para calcular disponibilidad"),
    hasta:         Optional[str]  = Query(None, description="Fecha fin (YYYY-MM-DD) para calcular disponibilidad"),
):
    """Lista equipos con sort y filtros.

    sort por defecto: "ranking" → ORDER BY relevancia_manual ASC,
    popularidad_score DESC, nombre ASC. Otros valores: nombre,
    precio_asc, precio_desc, id.

    spec: filtros por specs estructurados. Formato `key:valor`. Múltiples
    valores se AND-ean. Ej. `?spec=montura:E&spec=video_max:4K` filtra
    equipos con montura=E Y video_max=4K.
    """
    offset = (page - 1) * per_page
    base_sql = "FROM equipos e WHERE 1=1"
    params: list = []

    # El centinela del Estudio (es_recurso_interno) no es un producto del
    # catálogo: se excluye SIEMPRE (público y admin), filtros incluidos.
    base_sql += " AND e.es_recurso_interno = FALSE"

    is_admin = bool(get_session(request))
    if solo_visibles or not is_admin:
        base_sql += " AND e.visible_catalogo = 1 AND e.estado != 'fuera_servicio'"

    # Filtro admin: equipos cuya ficha el admin aún no marcó como completa.
    if solo_incompletos and is_admin:
        base_sql += " AND e.ficha_completa = FALSE"

    # Filtro por campo faltante (#350) — alimenta los CTAs del dashboard de calidad.
    # Mismos criterios que /api/admin/inventario/calidad para consistencia.
    if falta and is_admin:
        FALTA_SQL = {
            "foto":              " AND NULLIF(TRIM(COALESCE(e.foto_url, '')), '') IS NULL",
            "nombre_publico":    " AND NULLIF(TRIM(COALESCE(e.nombre_publico, '')), '') IS NULL",
            "serie":             " AND NULLIF(TRIM(COALESCE(e.serie, '')), '') IS NULL",
            "valor_reposicion":  " AND (e.valor_reposicion IS NULL OR e.valor_reposicion = 0)",
            "descripcion": (
                " AND NOT EXISTS ("
                " SELECT 1 FROM equipo_fichas f"
                " WHERE f.equipo_id = e.id"
                " AND NULLIF(TRIM(COALESCE(f.descripcion, '')), '') IS NOT NULL)"
            ),
            "categoria": (
                " AND NOT EXISTS ("
                " SELECT 1 FROM equipo_categorias ec WHERE ec.equipo_id = e.id)"
            ),
        }
        if falta in FALTA_SQL:
            base_sql += FALTA_SQL[falta]

    # Soft delete (#206): por default solo activos. Admin puede pedir ver
    # eliminados (papelera) o todos.
    if is_admin and solo_eliminados:
        base_sql += " AND e.eliminado_at IS NOT NULL"
    elif is_admin and incluir_eliminados:
        pass  # no filter
    else:
        base_sql += " AND e.eliminado_at IS NULL"

    # ── Filtros por specs estructurados (PR E) ──
    # Cada `spec=key:valor` agrega un AND EXISTS sobre equipo_specs.
    # Post refactor unificar_specs_definitions: el key del query string sigue
    # siendo el spec_key humano (montura, formato, etc.); resolvemos a
    # spec_def_id vía JOIN.
    if spec:
        for s in spec:
            if ":" not in s:
                continue
            key, value = s.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if not key or not value:
                continue
            base_sql += (
                " AND EXISTS ("
                " SELECT 1 FROM equipo_specs es"
                " JOIN spec_definitions sd ON sd.id = es.spec_def_id"
                " WHERE es.equipo_id = e.id AND LOWER(sd.spec_key) = %s"
                " AND LOWER(es.value) = LOWER(%s))"
            )
            params += [key, value]
    # Búsqueda fuzzy global (motor único backend/busqueda): sin tildes
    # ("bateria"→"Batería"), sin guiones ("a7 iii"→"A7-III"), multi-palabra
    # cruzando campos ("sony fx3") y con tolerancia a typos. El ranking por
    # relevancia (más abajo) ordena el mejor match primero.
    pred = construir(CAMPOS_EQUIPO, q) if q else None
    if pred and pred.activo:
        base_sql += f" AND ({pred.where})"
        params += pred.where_params
    if categoria:
        # Filtro recursivo: si es padre, incluye descendientes (árbol de `categorias`).
        # Acepta id numérico o nombre.
        try:
            cat_id_int = int(categoria)
            base_sql += """
              AND e.id IN (
                SELECT ec.equipo_id FROM equipo_categorias ec
                WHERE ec.categoria_id IN (
                    WITH RECURSIVE sub AS (
                        SELECT id FROM categorias WHERE id = %s
                        UNION ALL
                        SELECT c.id FROM categorias c JOIN sub ON c.parent_id = sub.id
                    )
                    SELECT id FROM sub
                )
              )"""
            params.append(cat_id_int)
        except (TypeError, ValueError):
            base_sql += """
              AND e.id IN (
                SELECT ec.equipo_id FROM equipo_categorias ec
                WHERE ec.categoria_id IN (
                    WITH RECURSIVE sub AS (
                        SELECT id FROM categorias WHERE nombre = %s
                        UNION ALL
                        SELECT c.id FROM categorias c JOIN sub ON c.parent_id = sub.id
                    )
                    SELECT id FROM sub
                )
              )"""
            params.append(categoria)
    if etiqueta:
        # Filtro plano por nombre de etiqueta (la bolsa ya no es jerárquica).
        base_sql += """
          AND e.id IN (
            SELECT ee.equipo_id FROM equipo_etiquetas ee
            JOIN etiquetas et ON et.id = ee.etiqueta_id
            WHERE LOWER(et.nombre) = LOWER(%s)
          )"""
        params.append(etiqueta)

    if marca:
        # Filtro por marca exacta (case-insensitive) contra marcas.nombre (brand_id FK).
        base_sql += f" AND LOWER(COALESCE({MARCA_NOMBRE_EXPR}, '')) = LOWER(%s)"
        params.append(marca)

    # ── Sort ──
    # Default: ranking compuesto (relevancia_manual + popularidad_score).
    # Esto pone los flagship arriba y desempata por uso real.
    # Cuando hay búsqueda (`q`) y el sort es el default, ordena por relevancia
    # del match (`_score`) primero — el mejor resultado arriba, consistente.
    _RANKING = "e.relevancia_manual ASC, e.popularidad_score DESC, e.nombre ASC"
    # Precio efectivo por jornada para ordenar: un combo se ordena por la SUMA de sus
    # componentes (mismo criterio que el display, `precios_combo_batch`); el resto por su
    # precio propio. Correlado por e.id; el subquery solo se evalúa para filas combo. Así
    # el orden coincide con el precio que se muestra y se cobra (exacto, no aproximado).
    _PRECIO_EFECTIVO = (
        "CASE WHEN e.tipo = 'combo' THEN COALESCE(("
        " SELECT ROUND(SUM(ce.precio_jornada * kc.cantidad"
        " * (1 - COALESCE(kc.descuento_pct, 0) / 100.0)))"
        " FROM kit_componentes kc JOIN equipos ce ON ce.id = kc.componente_id"
        " WHERE kc.equipo_id = e.id AND ce.eliminado_at IS NULL"
        "), 0) ELSE e.precio_jornada END"
    )
    use_score = bool(pred and pred.activo) and sort in (None, "ranking")
    if use_score:
        order_clause = f"ORDER BY _score DESC, {_RANKING}"
    else:
        order_clause = {
            None: f"ORDER BY {_RANKING}",
            "ranking": f"ORDER BY {_RANKING}",
            "nombre": "ORDER BY COALESCE(e.nombre_publico, e.nombre) ASC",
            "precio_asc": f"ORDER BY ({_PRECIO_EFECTIVO}) ASC NULLS LAST, e.nombre ASC",
            "precio_desc": f"ORDER BY ({_PRECIO_EFECTIVO}) DESC NULLS LAST, e.nombre ASC",
            "id": "ORDER BY e.id ASC",
        }.get(sort, f"ORDER BY {_RANKING}")

    with get_db() as conn:
        total = conn.execute(f"SELECT COUNT(*) {base_sql}", params).fetchone()[0]
        if use_score:
            select_cols = f"e.*, {MARCA_SUBQUERY}, ({pred.score}) AS _score"
            select_params = pred.score_params + params + [per_page, offset]
        else:
            select_cols = f"e.*, {MARCA_SUBQUERY}"
            select_params = params + [per_page, offset]
        rows  = conn.execute(
            f"SELECT {select_cols} {base_sql} {order_clause} LIMIT %s OFFSET %s",
            select_params,
        ).fetchall()
        equipos = [row_to_dict(r) for r in rows]
        for e in equipos:
            e.pop("_score", None)  # interno del ranking, no parte del contrato

        # Attach brand object (id, nombre, logo_url) — batched (#350 perf).
        # Antes era 1 query por equipo (N+1). Con 168 equipos sobre Railway
        # eso significaba 60s+ de latencia. Ahora una sola query.
        brand_ids = {e['brand_id'] for e in equipos if e.get('brand_id')}
        brands_map: dict = {}
        if brand_ids:
            placeholders = ",".join(["%s"] * len(brand_ids))
            brand_rows = conn.execute(
                f"SELECT id, nombre, logo_url FROM marcas WHERE id IN ({placeholders})",
                tuple(brand_ids),
            ).fetchall()
            brands_map = {r["id"]: row_to_dict(r) for r in brand_rows}
        for equipo in equipos:
            bid = equipo.get('brand_id')
            equipo['brand'] = brands_map.get(bid) if bid else None

        equipos = attach_tags(conn, equipos)
        equipos = attach_kit(conn, equipos)
        equipos = attach_categorias(conn, equipos)
        equipos = attach_ficha(conn, equipos)
        # Fase D: specs estructuradas para el catálogo público. Cada
        # equipo recibe `specs: {spec_key: {label, value, ...}}` desde
        # equipo_specs JOIN spec_definitions JOIN template.
        equipos = attach_specs_estructuradas(conn, equipos)
        equipos = attach_specs_destacados(conn, equipos)

        # Combos: el precio que se MUESTRA es el EFECTIVO (derivado de componentes,
        # combo-aware), no el `precio_jornada` crudo de la tabla → la card del catálogo
        # coincide con lo que el carrito cotiza/cobra (el front muestra, no calcula —
        # FASE 3). Batch: una sola query para todos los combos (sin N+1). Un combo sin
        # componentes vivos → 0. (El sort precio_asc/desc sigue sobre el crudo en SQL:
        # aproximado para combos; el display es exacto.)
        combo_ids = [e["id"] for e in equipos if e.get("tipo") == "combo"]
        if combo_ids:
            from services.precios import precios_combo_batch
            efectivos = precios_combo_batch(conn, combo_ids)
            for e in equipos:
                if e.get("tipo") == "combo":
                    e["precio_jornada"] = efectivos.get(e["id"], 0)

        # Filtrar kits/combos que no pueden armarse ni una vez (stock de
        # componentes insuficiente, sin considerar reservas). Solo para catálogo
        # público — el admin los sigue viendo para poder corregirlos.
        # Solo aplica a kits (los que tienen kit_componentes) para no afectar
        # equipos hoja con cantidad=0. Las claves de stock_teo son str(id).
        if not is_admin:
            stock_teo = _stock_sin_reservas(conn)
            equipos = [
                e for e in equipos
                if not e.get("kit")
                or stock_teo.get(str(e["id"]), 0) > 0
            ]

        if desde and hasta:
            equipos = _attach_disponibilidad(conn, equipos, desde, hasta)

        # Cache: la respuesta pública es estable para un set dado de params.
        # Admin recibe no-store (ve equipos no-visibles y filtros extra).
        response.headers["Cache-Control"] = (
            "private, no-store" if is_admin
            else "public, max-age=60, stale-while-revalidate=300"
        )
        return {"total": total, "page": page, "per_page": per_page, "items": equipos}


@router.get("/equipos/{id_or_slug}")
def get_equipo(id_or_slug: str):
    """Devuelve el detalle de un equipo.

    Acepta tanto ID numérico puro (`47`) como slug-id mixto al estilo
    Stack Overflow (`sony-fx3-cuerpo-47`). El slug es solo cosmético —
    el ID al final es lo que importa. Esto mejora SEO (keywords en URL)
    sin perder back-compat con URLs viejas `/equipo/47`.

    Si el cliente manda solo el slug sin ID (`sony-fx3-cuerpo`), devuelve
    400 — preferimos ser explícitos y no adivinar.
    """
    # Caso 1: ID puro (compat con URLs viejas)
    if id_or_slug.isdigit():
        actual_id = int(id_or_slug)
    else:
        # Caso 2: slug-id, extraer el ID del final.
        m = re.search(r"-(\d+)$", id_or_slug)
        if not m:
            raise HTTPException(400, "URL inválida — falta el id del equipo")
        actual_id = int(m.group(1))

    with get_db() as conn:
        row = conn.execute(
            f"SELECT *, {MARCA_SUBQUERY} FROM equipos e WHERE id = %s", (actual_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Equipo no encontrado")
        equipo = attach_tags(conn, [row_to_dict(row)])[0]
        equipo = attach_ficha(conn, [equipo])[0]
        equipo = attach_categorias(conn, [equipo])[0]
        # Specs estructuradas (Fase D): el catálogo público lee
        # `equipo.specs` (dict keyed por spec_key) en vez de las columnas
        # legacy de equipo_fichas. Mantenemos `ficha` para back-compat.
        equipo = attach_specs_estructuradas(conn, [equipo])[0]
        # Componentes vía la puerta única (services.contenido). `solo_activos=False`:
        # preserva el comportamiento previo de la ficha (no filtraba soft-deleted).
        equipo["kit"] = [{
            "componente_id": c["componente_id"],
            "cantidad":      c["cantidad"],
            "descuento_pct": c["descuento_pct"],
            "esencial":      c["esencial"],
            "nombre":        c["nombre"],
            "marca":         c["marca"],
            "foto_url":      c["foto_url"],
        } for c in contenido_de(conn, actual_id, solo_activos=False)]
        # Galería multi-foto (#125): el catálogo público expone las fotos de
        # `equipo_fotos` (principal primero) para que la ficha muestre la galería,
        # no solo `foto_url`. Shape liviano (url + es_principal) — sin internals.
        fotos = conn.execute(
            "SELECT url, es_principal FROM equipo_fotos "
            "WHERE equipo_id = %s AND url IS NOT NULL AND url <> '' "
            "ORDER BY es_principal DESC, orden ASC, id ASC",
            (actual_id,),
        ).fetchall()
        equipo["fotos"] = [
            {"url": r["url"], "es_principal": bool(r["es_principal"])} for r in fotos
        ]
        # Combo: el precio mostrado es el EFECTIVO (derivado de componentes), igual en
        # TODAS las superficies — listado, ficha pública, form de edición del admin y lo
        # que el carrito cotiza/cobra (el front muestra, no calcula — FASE 3). El precio
        # del combo es AUTO/derivado (no se edita a mano), así que mostrar el efectivo es
        # lo correcto también en el back-office (no hay un crudo editable que proteger).
        if equipo.get("tipo") == "combo":
            from services.precios import precio_combo
            equipo["precio_jornada"] = precio_combo(conn, actual_id)
        return equipo


# Series tipo "N/A", "ND", "-", "Sin serie" se aceptan duplicadas — son
# placeholders comunes para equipos sin serial real.
_PLACEHOLDER_SERIE_RE = re.compile(r"^(n/?a|n/?d|sin\s*serie|-+)$", re.IGNORECASE)


def _serie_es_placeholder(serie: Optional[str]) -> bool:
    if not serie:
        return True
    return bool(_PLACEHOLDER_SERIE_RE.match(serie.strip()))


def _check_serie_unica(conn, serie: Optional[str], exclude_id: Optional[int] = None) -> None:
    """Lanza 409 si la serie ya existe en otro equipo activo (no eliminado).
    Series placeholder (N/A, ND, -, sin serie) NO se chequean."""
    if _serie_es_placeholder(serie):
        return
    serie_norm = (serie or "").strip()
    if not serie_norm:
        return
    query = """
        SELECT id, nombre FROM equipos
        WHERE TRIM(LOWER(serie)) = LOWER(%s)
          AND eliminado_at IS NULL
    """
    params: list = [serie_norm]
    if exclude_id is not None:
        query += " AND id != %s"
        params.append(exclude_id)
    query += " LIMIT 1"
    existing = conn.execute(query, tuple(params)).fetchone()
    if existing:
        ed = row_to_dict(existing) if not isinstance(existing, dict) else existing
        raise HTTPException(
            409,
            f"La serie '{serie_norm}' ya existe en el equipo #{ed['id']} ('{ed['nombre']}'). "
            "Las series deben ser únicas por equipo (excepto placeholders como N/A).",
        )


def _resolve_brand_id(conn, nombre: str | None) -> int | None:
    """Find-or-create de marca por nombre (case-insensitive). Devuelve el id
    o None si nombre vacío. La marca (`marcas.nombre`) es la fuente única del
    nombre de marca; equipos.brand_id la referencia."""
    if not nombre or not nombre.strip():
        return None
    nombre = nombre.strip()
    row = conn.execute(
        "SELECT id FROM marcas WHERE LOWER(nombre) = LOWER(%s) LIMIT 1", (nombre,)
    ).fetchone()
    if row:
        return row["id"]
    conn.execute(
        "INSERT INTO marcas (nombre) VALUES (%s) ON CONFLICT (nombre) DO NOTHING", (nombre,)
    )
    row = conn.execute(
        "SELECT id FROM marcas WHERE LOWER(nombre) = LOWER(%s) LIMIT 1", (nombre,)
    ).fetchone()
    return row["id"] if row else None


@router.post("/equipos", status_code=201)
def create_equipo(data: EquipoCreate, request: Request):
    require_admin(request)
    with get_db() as conn:
        try:
            # Validar serie única (rechaza 409 si choca con otro activo)
            _check_serie_unica(conn, data.serie)
            brand_id = _resolve_brand_id(conn, data.marca)
            new_id = conn.insert_returning("""
                INSERT INTO equipos (nombre, brand_id, modelo, cantidad,
                                     precio_jornada, precio_usd, roi_pct,
                                     valor_reposicion, foto_url, fecha_compra,
                                     serie, bh_url, dueno, visible_catalogo, estado,
                                     ficha_completa, categoria_specs, tipo)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (data.nombre, brand_id, data.modelo, data.cantidad,
                  data.precio_jornada, data.precio_usd, data.roi_pct,
                  data.valor_reposicion, data.foto_url, _normalize_fecha_compra(data.fecha_compra),
                  data.serie, data.bh_url, data.dueno, data.visible_catalogo, data.estado,
                  bool(data.ficha_completa), data.categoria_specs, data.tipo or "simple"))
            # Hook: calcular nombre_publico inicial. No falla el create si esto
            # rompe (ej. si los servicios no están disponibles).
            try:
                actualizar_nombres_de(conn, new_id, commit=False)
            except Exception:
                pass
            # Slug en la creación: el equipo nuevo nace con slug (clave natural
            # del export dataio) por el camino correcto, no por el self-heal del
            # export (#922). Idempotente; reusa la fuente única del backfill.
            from dataio.slug import backfill_equipos_slug
            backfill_equipos_slug(conn)
            conn.commit()
            row    = conn.execute(f"SELECT *, {MARCA_SUBQUERY} FROM equipos e WHERE id=%s", (new_id,)).fetchone()
            equipo = attach_tags(conn, [row_to_dict(row)])[0]
            return equipo
        except Exception:
            conn.rollback()
            raise


def _normalize_fecha_compra(value):
    """`equipos.fecha_compra` es DATE, pero el front (MonthYearPicker) manda
    "YYYY-MM" (mes/año — issue #109). Postgres no castea "YYYY-MM" a DATE
    ('2024-01'::date es inválido → 500), así que completamos al día 1.
    Vacío → None. "YYYY-MM-DD" se deja igual."""
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    if re.fullmatch(r"\d{4}-\d{2}", s):
        return f"{s}-01"
    return s


@router.patch("/equipos/{id}")
def update_equipo(id: int, data: EquipoUpdate, request: Request):
    require_admin(request)
    with get_db() as conn:
        try:
            existing = conn.execute(f"SELECT *, {MARCA_SUBQUERY} FROM equipos e WHERE id=%s", (id,)).fetchone()
            if not existing:
                raise HTTPException(404, "Equipo no encontrado")
            updates = data.model_dump(exclude_unset=True)
            if not updates:
                raise HTTPException(400, "Nada para actualizar")
            # marca → brand_id: marcas.nombre es la fuente única. Resolvemos la
            # FK y NO escribimos la columna marca (eliminada).
            marca_cambio = "marca" in updates
            if marca_cambio:
                updates["brand_id"] = _resolve_brand_id(conn, updates.pop("marca"))
            # fecha_compra es DATE; el front (MonthYearPicker) manda "YYYY-MM" →
            # completar a "YYYY-MM-01"; vacío → NULL (ver _normalize_fecha_compra).
            if "fecha_compra" in updates:
                updates["fecha_compra"] = _normalize_fecha_compra(updates["fecha_compra"])
            # Validar serie única si se está cambiando (excluyendo este equipo).
            # Rechaza si otra fila activa tiene la misma serie.
            if "serie" in updates:
                _check_serie_unica(conn, updates["serie"], exclude_id=id)
            # Registrar cambio de precio si cambió
            if "precio_jornada" in updates and updates["precio_jornada"] != existing["precio_jornada"]:
                conn.execute(
                    "INSERT INTO equipo_precio_historial (equipo_id, precio_jornada) VALUES (%s,%s)",
                    (id, updates["precio_jornada"]),
                )
            # Inferencia del flag `precio_jornada_manual` cuando el cliente
            # no lo manda explícito. Heurística:
            #   - Si llega precio_jornada SIN roi_pct → asumimos override
            #     manual del admin (editó el precio directamente).
            #   - Si llega precio_jornada JUNTO con roi_pct → asumimos
            #     cálculo automático (el frontend recalculó la fórmula
            #     desde el ROI nuevo).
            # El frontend puede enviar `precio_jornada_manual` para ser
            # explícito y este bloque se saltea.
            if (
                "precio_jornada" in updates
                and "precio_jornada_manual" not in updates
            ):
                updates["precio_jornada_manual"] = "roi_pct" not in updates
            set_clause = ", ".join(f"{k} = %s" for k in updates)
            set_clause += ", updated_at = CURRENT_TIMESTAMP"
            conn.execute(f"UPDATE equipos SET {set_clause} WHERE id = %s",
                         list(updates.values()) + [id])
            # Si cambió algo que alimenta auto-tags, regenerar.
            if marca_cambio or any(k in updates for k in ("nombre", "modelo")):
                regenerate_auto_tags(conn, id)
            # Hook: si cambió algo que afecta el nombre público, recalcular.
            # No falla el update si el recálculo rompe.
            if marca_cambio or any(k in updates for k in ("nombre", "modelo")):
                try:
                    actualizar_nombres_de(conn, id, commit=False)
                except Exception:
                    pass
            conn.commit()
            row    = conn.execute(f"SELECT *, {MARCA_SUBQUERY} FROM equipos e WHERE id=%s", (id,)).fetchone()
            equipo = attach_tags(conn, [row_to_dict(row)])[0]
            return equipo
        except Exception:
            conn.rollback()
            raise


@router.post("/equipos/{id}/duplicate")
def duplicate_equipo(id: int, request: Request):
    """
    Duplica un equipo: copia equipo + ficha + categorías + kit. La nueva fila
    arranca con `serie` vacía (debe ser única por equipo), `ficha_completa = false`
    (para forzar al admin a revisar) y `cantidad = 1` (default seguro).
    Útil cuando comprás varias unidades del mismo modelo con series distintas.
    """
    require_admin(request)
    with get_db() as conn:
        try:
            src = conn.execute(f"SELECT *, {MARCA_SUBQUERY} FROM equipos e WHERE id=%s", (id,)).fetchone()
            if not src:
                raise HTTPException(404, "Equipo no encontrado")
            src_d = row_to_dict(src)

            new_id = conn.insert_returning("""
                INSERT INTO equipos (
                    nombre, brand_id, modelo, cantidad,
                    precio_jornada, precio_usd, roi_pct,
                    valor_reposicion, foto_url, fecha_compra,
                    serie, bh_url, dueno, visible_catalogo, estado,
                    ficha_completa, tipo
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                f"{src_d['nombre']} (copia)",
                src_d.get("brand_id"), src_d.get("modelo"), 1,
                src_d.get("precio_jornada"), src_d.get("precio_usd"), src_d.get("roi_pct"),
                src_d.get("valor_reposicion"), src_d.get("foto_url"), _normalize_fecha_compra(src_d.get("fecha_compra")),
                None,  # serie vacía
                src_d.get("bh_url"), src_d.get("dueno"), src_d.get("visible_catalogo", 1), src_d.get("estado", "operativo"),
                False,  # ficha_completa false para que el admin la revise
                src_d.get("tipo", "simple"),  # hereda el tipo del original
            ))

            # Copiar ficha si existe
            ficha = conn.execute("SELECT * FROM equipo_fichas WHERE equipo_id=%s", (id,)).fetchone()
            if ficha:
                f = row_to_dict(ficha)
                cols = [k for k in f.keys() if k not in ("equipo_id", "created_at", "updated_at")]
                placeholders = ", ".join(["%s"] * (len(cols) + 1))
                conn.execute(
                    f"INSERT INTO equipo_fichas (equipo_id, {', '.join(cols)}) VALUES ({placeholders})",
                    [new_id] + [f.get(c) for c in cols],
                )

            # Copiar categorías (con orden manual preservado)
            cats = conn.execute(
                "SELECT categoria_id, orden FROM equipo_categorias WHERE equipo_id=%s", (id,)
            ).fetchall()
            conn.executemany(
                "INSERT INTO equipo_categorias (equipo_id, categoria_id, orden) VALUES (%s, %s, %s)",
                [(new_id, cat["categoria_id"], cat["orden"]) for cat in cats],
            )

            # Copiar etiquetas MANUALES (las auto se regeneran al setear marca/
            # modelo/categorías). Sin esto, el duplicado pierde los tags que
            # el admin tipeó a mano.
            etqs = conn.execute(
                "SELECT etiqueta_id, orden FROM equipo_etiquetas "
                "WHERE equipo_id=%s AND origen='manual'",
                (id,),
            ).fetchall()
            conn.executemany(
                "INSERT INTO equipo_etiquetas (equipo_id, etiqueta_id, orden, origen) "
                "VALUES (%s, %s, %s, 'manual')",
                [(new_id, e["etiqueta_id"], e["orden"]) for e in etqs],
            )

            # Copiar kit
            kit = conn.execute(
                "SELECT componente_id, cantidad, orden FROM kit_componentes WHERE equipo_id=%s", (id,)
            ).fetchall()
            conn.executemany(
                "INSERT INTO kit_componentes (equipo_id, componente_id, cantidad, orden) VALUES (%s, %s, %s, %s)",
                [(new_id, componente_id, cantidad, orden) for (componente_id, cantidad, orden) in kit],
            )

            # Regenerar etiquetas auto (categoría/marca/modelo/nombre) sobre el
            # duplicado. Las manuales ya las copiamos arriba; esto agrega las auto
            # que normalmente se generan en setCategorias.
            try:
                regenerate_auto_tags(conn, new_id)
            except Exception as e:
                logger.warning("regenerate_auto_tags falló para duplicado %s: %s", new_id, e)

            conn.commit()
            row = conn.execute(f"SELECT *, {MARCA_SUBQUERY} FROM equipos e WHERE id=%s", (new_id,)).fetchone()
            return attach_tags(conn, [row_to_dict(row)])[0]
        except Exception:
            conn.rollback()
            raise


@router.post("/equipos/{id}/restore")
def restore_equipo(id: int, request: Request):
    """Restaura un equipo soft-deleted (eliminado_at = NULL). #206."""
    require_admin(request)
    with get_db() as conn:
        try:
            row = conn.execute(
                "SELECT id, eliminado_at FROM equipos WHERE id=%s", (id,)
            ).fetchone()
            if not row:
                raise HTTPException(404, "Equipo no encontrado")
            if row["eliminado_at"] is None:
                return {"ok": True, "message": "Ya estaba activo"}
            conn.execute(
                "UPDATE equipos SET eliminado_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id=%s",
                (id,),
            )
            conn.commit()
            return {"ok": True}
        except Exception:
            conn.rollback()
            raise


class BulkActionInput(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=500)
    action: str   # "set_visible" | "set_ficha_completa" | "set_categoria" | "add_categoria" | "remove_categoria" | "delete"
    visible: Optional[bool] = None
    ficha_completa: Optional[bool] = None
    categoria_id: Optional[int] = None


@router.post("/admin/equipos/bulk")
def bulk_action(payload: BulkActionInput, request: Request):
    """Aplica una acción a varios equipos a la vez. Acciones soportadas:
    - set_visible (visible: bool)
    - set_ficha_completa (ficha_completa: bool)
    - set_categoria (categoria_id: int) — REEMPLAZA las categorías existentes
    - delete (soft delete — marca eliminado_at; #206)

    Retorna {"affected": N} con la cantidad de equipos modificados.
    """
    require_admin(request)
    ids = payload.ids
    if not ids:
        return {"affected": 0}

    placeholders = ",".join(["%s"] * len(ids))
    with get_db() as conn:
        try:
            if payload.action == "set_visible":
                if payload.visible is None:
                    raise HTTPException(400, "set_visible requiere visible: bool")
                v = 1 if payload.visible else 0
                conn.execute(
                    f"UPDATE equipos SET visible_catalogo = %s, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                    [v, *ids],
                )

            elif payload.action == "set_ficha_completa":
                if payload.ficha_completa is None:
                    raise HTTPException(400, "set_ficha_completa requiere ficha_completa: bool")
                conn.execute(
                    f"UPDATE equipos SET ficha_completa = %s, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                    [bool(payload.ficha_completa), *ids],
                )

            elif payload.action == "set_categoria":
                if not payload.categoria_id:
                    raise HTTPException(400, "set_categoria requiere categoria_id: int")
                cat_exists = conn.execute(
                    "SELECT id FROM categorias WHERE id = %s", (payload.categoria_id,)
                ).fetchone()
                if not cat_exists:
                    raise HTTPException(404, f"Categoría {payload.categoria_id} no existe")
                # Expandir a ancestros una sola vez (mismo set para todos los equipos
                # del bulk): si "Montura E" (hija) se asigna, también va "Lente" (madre).
                ancestor_ids = _expand_to_ancestors(conn, [payload.categoria_id])
                # Reemplaza las categorías existentes con el set expandido
                conn.execute(
                    f"DELETE FROM equipo_categorias WHERE equipo_id IN ({placeholders})",
                    ids,
                )
                conn.executemany(
                    "INSERT INTO equipo_categorias (equipo_id, categoria_id, orden) VALUES (%s, %s, %s)",
                    [(eid, cid_int, orden) for eid in ids for orden, cid_int in enumerate(ancestor_ids)],
                )
                # Regeneración batch (1 pasada para los N equipos, no N+1).
                try:
                    regenerate_auto_tags_batch(conn, ids)
                except Exception as e:
                    logger.warning("regenerate_auto_tags_batch falló en bulk set_categoria: %s", e)

            elif payload.action == "add_categoria":
                # Igual que set_categoria pero NO borra las existentes — sólo
                # AGREGA. Útil para asignar masivamente una categoría desde
                # la vista de categorías sin perder las otras categorías que
                # cada equipo ya tenía.
                if not payload.categoria_id:
                    raise HTTPException(400, "add_categoria requiere categoria_id: int")
                cat_exists = conn.execute(
                    "SELECT id FROM categorias WHERE id = %s", (payload.categoria_id,)
                ).fetchone()
                if not cat_exists:
                    raise HTTPException(404, f"Categoría {payload.categoria_id} no existe")
                # Expandimos a ancestros una sola vez para todos los equipos.
                ancestor_ids = _expand_to_ancestors(conn, [payload.categoria_id])
                conn.executemany(
                    """
                    INSERT INTO equipo_categorias (equipo_id, categoria_id, orden)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (equipo_id, categoria_id) DO NOTHING
                    """,
                    [(eid, cid_int, orden) for eid in ids for orden, cid_int in enumerate(ancestor_ids)],
                )
                # Regeneración batch (1 pasada para los N equipos, no N+1).
                try:
                    regenerate_auto_tags_batch(conn, ids)
                except Exception as e:
                    logger.warning("regenerate_auto_tags_batch falló en bulk add_categoria: %s", e)

            elif payload.action == "remove_categoria":
                # Saca UNA categoría de cada equipo sin tocar las otras. Si la
                # categoría es padre/abuela y los equipos tienen hijas suyas,
                # NO borramos esas hijas — solo la categoría exacta indicada.
                if not payload.categoria_id:
                    raise HTTPException(400, "remove_categoria requiere categoria_id: int")
                placeholders_ids = ",".join("%s" * len(ids))
                conn.execute(
                    f"DELETE FROM equipo_categorias WHERE categoria_id = %s AND equipo_id IN ({placeholders_ids})",
                    [payload.categoria_id, *ids],
                )
                # Regeneración batch (1 pasada para los N equipos, no N+1).
                try:
                    regenerate_auto_tags_batch(conn, ids)
                except Exception as e:
                    logger.warning("regenerate_auto_tags_batch falló en bulk remove_categoria: %s", e)

            elif payload.action == "delete":
                # Soft delete: consistente con el endpoint single DELETE (#206).
                conn.execute(
                    f"UPDATE equipos SET eliminado_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                    ids,
                )

            elif payload.action == "delete_permanent":
                # Hard delete (DROP). Usado desde la vista papelera para vaciar
                # definitivamente. CASCADE borra ficha, kit, categorías, etiquetas
                # del equipo. Los alquiler_items quedan huérfanos pero el catálogo
                # público ya no los referencia. #punto4
                conn.execute(
                    f"DELETE FROM equipos WHERE id IN ({placeholders})",
                    ids,
                )

            else:
                raise HTTPException(400, f"Acción desconocida: {payload.action}")

            conn.commit()
            return {"affected": len(ids)}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            logger.exception("bulk_action falló: %s", payload.action)
            raise HTTPException(500, f"Error bulk: {type(e).__name__}")


@router.delete("/equipos/{id}", status_code=204)
def delete_equipo(id: int, request: Request):
    """Soft delete: marca eliminado_at = NOW(). Preserva historial de
    alquileres del equipo dado de baja. Restaurable vía POST /restore (#206)."""
    require_admin(request)
    html_source_url = None
    with get_db() as conn:
        try:
            row = conn.execute(
                "SELECT id, html_source_url FROM equipos WHERE id=%s", (id,)
            ).fetchone()
            if not row:
                raise HTTPException(404, "Equipo no encontrado")
            html_source_url = row["html_source_url"]
            conn.execute(
                "UPDATE equipos SET eliminado_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id=%s",
                (id,),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # Cleanup R2 blob after successful soft-delete (best-effort, no rollback if fails).
    if html_source_url:
        try:
            cfg = _r2_config()
            key = html_source_url.removeprefix(f"{cfg['public_base']}/")
            _delete_from_r2(key)
        except Exception as _e:
            logger.warning("delete_equipo: no se pudo borrar HTML blob de R2: %s", _e)


@router.get("/equipos/{id}/disponibilidad-calendario")
def disponibilidad_calendario(
    id: int,
    desde: Optional[str] = Query(None),
    hasta: Optional[str] = Query(None),
):
    """Estado de disponibilidad por día de UN equipo (#808), catálogo-facing.

    Devuelve `{'stock': N, 'dias': {YYYY-MM-DD: 'parcial'|'reservado'}}` — los días
    `libre` se OMITEN (default en el front). Lectura sobre el motor de reservas
    (`estado_diario_equipo`), sin recalcular overlap. Sin auth (igual que el catálogo).
    """
    from reservas.disponibilidad import estado_diario_equipo

    hoy = _date.today()
    d_desde = desde or hoy.isoformat()
    d_hasta = hasta or (hoy + timedelta(days=90)).isoformat()
    # Cap defensivo del rango (≤ 180 días) para no abusar de la lectura.
    try:
        span = (_date.fromisoformat(d_hasta[:10]) - _date.fromisoformat(d_desde[:10])).days
    except ValueError:
        raise HTTPException(400, "Fechas inválidas (usar YYYY-MM-DD)")
    if span < 0:
        raise HTTPException(400, "El rango es inválido (hasta < desde)")
    if span > 180:
        raise HTTPException(400, "El rango no puede superar 180 días")

    with get_db() as conn:
        res = estado_diario_equipo(conn, id, d_desde, d_hasta)
    if res is None:
        raise HTTPException(404, "Equipo no encontrado")
    # Slim: solo días no-libres (libre = ausente).
    res["dias"] = {d: e for d, e in res["dias"].items() if e != "libre"}
    return res


# ── Historial de alquileres por equipo ───────────────────────────────────────

@router.get("/equipos/{id}/historial")
def get_equipo_historial(id: int):
    with get_db() as conn:
        if not conn.execute("SELECT id FROM equipos WHERE id=%s", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")

        rows = conn.execute("""
            SELECT
                p.id, p.numero_pedido, p.estado,
                p.fecha_desde, p.fecha_hasta,
                COALESCE(c.nombre || ' ' || c.apellido, p.cliente_nombre) AS cliente,
                pi.cantidad, pi.precio_jornada AS precio_item,
                GREATEST(1, (p.fecha_hasta::date - p.fecha_desde::date))::INTEGER AS dias
            FROM alquiler_items pi
            JOIN alquileres p ON p.id = pi.pedido_id
            LEFT JOIN clientes c ON c.id = p.cliente_id
            WHERE pi.equipo_id = %s
            ORDER BY p.fecha_desde DESC
        """, (id,)).fetchall()

        items      = [row_to_dict(r) for r in rows]
        total_dias = sum(r["dias"] or 1 for r in items)
        total_rev  = sum((r["precio_item"] or 0) * (r["cantidad"] or 1) * (r["dias"] or 1) for r in items)

        return {
            "historial": items,
            "stats": {
                "total_alquileres": len(items),
                "total_dias":       total_dias,
                "total_revenue":    total_rev,
                "ultimo_alquiler":  items[0]["fecha_desde"] if items else None,
            },
        }


# ── Historial de precios ─────────────────────────────────────────────────────

@router.get("/equipos/{id}/precio-historial")
def get_precio_historial(id: int):
    with get_db() as conn:
        if not conn.execute("SELECT id FROM equipos WHERE id=%s", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        rows = conn.execute("""
            SELECT precio_jornada, changed_at
            FROM equipo_precio_historial
            WHERE equipo_id = %s
            ORDER BY changed_at DESC
        """, (id,)).fetchall()
        return [row_to_dict(r) for r in rows]


# ── Categorías por equipo ────────────────────────────────────────────────────

def _expand_to_ancestors(conn, ids) -> list[int]:
    """
    Expande una lista de categoria_ids agregando todos los ancestros
    (padres, abuelos, …) hasta la raíz.

    Hoy las categorías tienen máximo 2 niveles (raíz / hija), pero la
    implementación es recursiva por si más adelante se permite mayor
    profundidad.

    Ejemplo: si "Montura E" (id=42, parent_id=10) está en `ids` y "Lente"
    (id=10, parent_id=None) no, devuelve [42, 10].

    Issue: implementación de la regla "asigno hija → se asigna madre" del
    sistema de categorías sugeridas (rule of the project).
    """
    if not ids:
        return []
    out: set[int] = set()
    pending: list[int] = []
    for raw in ids:
        try:
            iv = int(raw)
        except (TypeError, ValueError):
            continue
        if iv not in out:
            out.add(iv)
            pending.append(iv)

    while pending:
        placeholders = ",".join(["%s"] * len(pending))
        rows = conn.execute(
            f"SELECT id, parent_id FROM categorias WHERE id IN ({placeholders})",
            pending,
        ).fetchall()
        next_pending: list[int] = []
        for row in rows:
            pid = row["parent_id"]
            if pid is not None and int(pid) not in out:
                out.add(int(pid))
                next_pending.append(int(pid))
        pending = next_pending

    return list(out)


@router.get("/equipos/{id}/calendario")
def get_equipo_calendario(id: int, year: int = Query(...), month: int = Query(...)):
    """Unidades libres por día de un equipo en un mes.

    Delega el conteo de "reservado" en el motor único `reservas.reservado_total`,
    que sube por TODO el grafo de composición (combos/kits anidados, a cualquier
    profundidad). Antes este endpoint reimplementaba el overlap a 1 solo nivel de
    kit (`directas` + `via_kit`) → mostraba un equipo como libre aunque estuviera
    reservado vía un compuesto anidado (#923; violaba la fuente única, MEMORIA
    2026-05-30 / 2026-05-31). El grafo inverso se calcula una vez y se reusa por día.
    Comportamiento por día = overlap a nivel timestamp (igual que el gate): un día
    en el que el alquiler sigue ocupado, aunque devuelva más tarde, cuenta como
    ocupado (la versión vieja, a fecha exclusiva, lo mostraba libre — optimista).
    """
    if not (1 <= month <= 12):
        raise HTTPException(400, "Mes inválido")

    with get_db() as conn:
        equipo = conn.execute(
            "SELECT id, cantidad FROM equipos WHERE id=%s", (id,)
        ).fetchone()
        if not equipo:
            raise HTTPException(404, "Equipo no encontrado")

        stock_total = equipo["cantidad"]
        _, days_in_month = _cal.monthrange(year, month)
        rev = parientes_de(conn)  # grafo inverso de composición — una vez (motor)

        result: dict[str, int] = {}
        for day_num in range(1, days_in_month + 1):
            d0 = _date(year, month, day_num)
            d1 = d0 + timedelta(days=1)
            # Reservado recursivo (directo + vía cualquier compuesto que lo
            # contenga) que se pisa con [d0, d1). excl=-1 → no excluir ningún
            # pedido (contar todos). Sin buffer (vista de día, no chequeo de gate).
            reservado = reservado_total(
                conn, id, -1, d1.isoformat(), d0.isoformat(), rev_graph=rev,
            )
            result[d0.isoformat()] = max(0, stock_total - reservado)

        return result
