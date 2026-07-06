"""
routes/equipos/core.py — búsqueda/listado + CRUD real de equipos.

Split #1258: los modelos Pydantic viven en `modelos.py` (Corte A) y
disponibilidad/calendario/historial en `disponibilidad.py` (Corte B). Acá
queda el corazón del módulo: búsqueda (`list_equipos`/`get_equipo`) + el CRUD
(`create_equipo`/`update_equipo`/`duplicate_equipo`/`restore_equipo`) + bulk
actions + `delete_equipo` (por los 4 monkeypatch paths de test que lo atan acá).
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Query, HTTPException, Request, Response

from database import (
    get_db, row_to_dict,
    MARCA_SUBQUERY, MARCA_NOMBRE_EXPR,
)
from busqueda import construir
from reservas import (
    ESTADOS_RESERVADO,  # noqa: F401 — re-export canónico (guard: test_reservas_sql_safety)
)
from auth.session import get_session
from auth.guards import require_admin
from services.nombre_service import actualizar_nombres_de
from services.catalogo import proyectar_lista, proyectar_uno
from services.categorias import (
    set_categoria_masivo,
    add_categoria_masivo,
    remove_categoria_masivo,
    copiar_categorias,
    expandir_a_descendientes,
    sql_filtro_categoria,
    sql_filtro_equipos_por_categoria,
    buscar_id_por_nombre,
)
from services.specs.queries.search_source import specs_search_expr
from services.categorias.errors import CategoriaNoExiste
# `delete_equipo` limpia el blob HTML scrapeado en R2 al borrar un equipo; los
# endpoints de fotos viven en `routes.equipos.fotos` (importan estos mismos
# helpers de `services.media.storage` por su cuenta). Lo testea
# `test_delete_equipo_r2_cleanup` parcheando estos nombres sobre `core`.
from services.media.storage import _r2_config, delete_object as _delete_from_r2
# Modelos Pydantic: viven en `modelos.py` (split #1258, Corte A). Re-importados
# tal cual — `routes/equipos/__init__.py` sigue tomando `EquipoCreate`/
# `EquipoUpdate` de acá.
from routes.equipos.modelos import (
    EquipoCreate,
    EquipoUpdate,
    BulkActionInput,
)

router = APIRouter()


# Campos buscables del equipo (motor único backend/busqueda). Incluye la marca
# (subquery por brand_id), los textos de la ficha (descripción + keywords), y
# las specs estructuradas (#1163 F4: value+label+aliases de cada spec, vía el
# embudo de alias de valor) — la barra es un "find anything": buscás "log3",
# "iso 25600" o "FF" y aparece aunque la palabra viva en un spec, no en el
# nombre ni en la ficha.
_FICHA_EXPR = (
    "(SELECT string_agg(coalesce(ef.descripcion, '') || ' ' || coalesce(ef.keywords_json, ''), ' ') "
    "FROM equipo_fichas ef WHERE ef.equipo_id = e.id)"
)
CAMPOS_EQUIPO = [
    "e.nombre", MARCA_NOMBRE_EXPR, "e.modelo", "e.serie", _FICHA_EXPR,
    specs_search_expr(),
]

# `disponibilidad.py` registra rutas de PATH LITERAL (`/equipos/afuera`,
# `/equipos/kpis`) que el router de Starlette matchea en orden de registro —
# tienen que quedar ANTES de `/equipos/{id_or_slug}` (más abajo), o esa ruta
# wildcard se las "come" (una request a /equipos/kpis matchearía
# id_or_slug="kpis" en vez del endpoint real). Import posicional a propósito,
# no al final del archivo — reemplaza el import repetido en `__init__.py`
# (donde el orden entre submódulos ya no alcanza para esto: ese import
# corre DESPUÉS de que `core.py` ya registró su wildcard).
from routes.equipos import disponibilidad as _disponibilidad  # noqa: F401,E402


# ── Rutas de equipos ─────────────────────────────────────────────────────────


@router.get("/equipos")
def list_equipos(
    request:       Request,
    response:      Response,
    q:                Optional[str]  = Query(None),
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
    incluir_detalle: Optional[bool] = Query(
        None,
        description="Si false (solo admin — se ignora en catálogo público), "
        "saltea kit/ficha/specs para vistas de listado que no los muestran "
        "(ej. la tabla de búsqueda del admin). El detalle de un equipo puntual "
        "(GET /equipos/{id}) los trae completos siempre, sin cambios.",
    ),
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
            "categoria": sql_filtro_categoria(),
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
        try:
            cat_id = int(categoria)
        except ValueError:
            with get_db() as conn0:
                cat_id = buscar_id_por_nombre(conn0, categoria)
        if cat_id is not None:
            with get_db() as conn0:
                sub_ids = expandir_a_descendientes(conn0, cat_id)
            if sub_ids:
                fragment, _ = sql_filtro_equipos_por_categoria("e", sub_ids)
                base_sql += fragment
                params += sub_ids
            else:
                base_sql += " AND 1=0"
        else:
            base_sql += " AND 1=0"
    if marca:
        # Filtro por marca exacta (case-insensitive) contra marcas.nombre (brand_id FK).
        base_sql += f" AND LOWER(COALESCE({MARCA_NOMBRE_EXPR}, '')) = LOWER(%s)"
        params.append(marca)

    # El catálogo público SIEMPRE necesita el detalle completo (filtra/rankea
    # por specs y kit client-side) — `incluir_detalle=false` solo lo puede
    # pedir una sesión admin.
    incluir_detalle_val = (incluir_detalle if incluir_detalle is not None else True) if is_admin else True

    with get_db() as conn:
        result = proyectar_lista(
            conn,
            filtro_sql=base_sql,
            filtro_params=params,
            sort=sort,
            pred=pred,
            page=page,
            per_page=per_page,
            desde=desde,
            hasta=hasta,
            is_admin=is_admin,
            incluir_detalle=incluir_detalle_val,
        )
    # Cache: respuesta pública estable para un set dado de params;
    # admin recibe no-store (ve equipos no-visibles y filtros extra).
    response.headers["Cache-Control"] = (
        "private, no-store" if is_admin
        else "public, max-age=60, stale-while-revalidate=300"
    )
    return result


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
        equipo = proyectar_uno(conn, actual_id)
    if not equipo:
        raise HTTPException(404, "Equipo no encontrado")
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
            return row_to_dict(row)
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
            # Hook: si cambió algo que afecta el nombre público, recalcular.
            # No falla el update si el recálculo rompe.
            if marca_cambio or any(k in updates for k in ("nombre", "modelo")):
                try:
                    actualizar_nombres_de(conn, id, commit=False)
                except Exception:
                    pass
            conn.commit()
            row    = conn.execute(f"SELECT *, {MARCA_SUBQUERY} FROM equipos e WHERE id=%s", (id,)).fetchone()
            return row_to_dict(row)
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

            copiar_categorias(conn, id, new_id)

            # Copiar kit
            kit = conn.execute(
                "SELECT componente_id, cantidad, orden FROM kit_componentes WHERE equipo_id=%s", (id,)
            ).fetchall()
            conn.executemany(
                "INSERT INTO kit_componentes (equipo_id, componente_id, cantidad, orden) VALUES (%s, %s, %s, %s)",
                [(new_id, componente_id, cantidad, orden) for (componente_id, cantidad, orden) in kit],
            )

            conn.commit()
            row = conn.execute(f"SELECT *, {MARCA_SUBQUERY} FROM equipos e WHERE id=%s", (new_id,)).fetchone()
            return row_to_dict(row)
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
                try:
                    set_categoria_masivo(conn, ids, payload.categoria_id)
                except CategoriaNoExiste as e:
                    raise HTTPException(404, str(e))

            elif payload.action == "add_categoria":
                if not payload.categoria_id:
                    raise HTTPException(400, "add_categoria requiere categoria_id: int")
                try:
                    add_categoria_masivo(conn, ids, payload.categoria_id)
                except CategoriaNoExiste as e:
                    raise HTTPException(404, str(e))

            elif payload.action == "remove_categoria":
                if not payload.categoria_id:
                    raise HTTPException(400, "remove_categoria requiere categoria_id: int")
                remove_categoria_masivo(conn, ids, payload.categoria_id)

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

