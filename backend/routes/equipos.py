"""
routes/equipos.py — CRUD de equipos, kits, etiquetas, categorías y fichas.
"""

import calendar as _cal
import datetime
import logging
import os
import re
import unicodedata
from datetime import date as _date
from typing import Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Query, HTTPException, Request
from pydantic import BaseModel, Field

from database import (
    get_db, row_to_dict, attach_tags, attach_kit, attach_categorias,
    attach_ficha, attach_specs_destacados, regenerate_auto_tags,
)
from routes.auth import get_session
from admin_guard import require_admin
from services.nombre_service import actualizar_nombres_de

router = APIRouter()


# ── Constantes de fotos / scraping ───────────────────────────────────────────
# Antes estaban hardcodeadas como números mágicos en 3 lugares con valores
# distintos (6, 8, 10, 18). Centralizadas acá con nombres explícitos.

# Cuántos candidatos guarda cada scrape individual (B&H o sitio oficial).
# Más alto que esto = más data redundante; el merge ya deduplica entre fuentes.
MAX_PHOTO_CANDIDATES_PER_SCRAPE = 6

# Cuántos candidatos validamos vía HTTP en /enriquecer (B&H + alt mergeados).
# Validar es lento (HEAD por imagen) → mantener bajo.
MAX_PHOTO_CANDIDATES_TO_VALIDATE = 8

# /buscar-fotos: cuántos validamos y cuántos devolvemos. Este flow inspecciona
# más fuentes (Wikipedia, reviews, manufacturer) por eso el límite es mayor.
MAX_PHOTO_CANDIDATES_BUSCAR_VALIDATE = 18
MAX_PHOTO_CANDIDATES_BUSCAR_RETURN   = 10


# ── Modelos ──────────────────────────────────────────────────────────────────

class EquipoCreate(BaseModel):
    nombre:           str
    marca:            Optional[str]   = None
    modelo:           Optional[str]   = None
    cantidad:         int             = 1
    precio_jornada:   Optional[int]   = None   # precio diario de alquiler (ARS)
    precio_usd:       Optional[float] = None   # valor de mercado (USD)
    roi_pct:          Optional[float] = None   # retorno % (ej: 2.0 → precio = valor*0.02)
    valor_reposicion: Optional[float] = None   # valor para seguro (USD)
    foto_url:         Optional[str]   = None
    fecha_compra:     Optional[str]   = None
    serie:            Optional[str]   = None
    bh_url:           Optional[str]   = None
    dueno:            Optional[str]   = "Rambla"
    visible_catalogo: Optional[int]   = 1
    estado:           Optional[str]   = "operativo"   # operativo / en_mantenimiento / fuera_servicio
    ficha_completa:   Optional[bool]  = False


class EquipoUpdate(BaseModel):
    nombre:           Optional[str]   = None
    marca:            Optional[str]   = None
    modelo:           Optional[str]   = None
    cantidad:         Optional[int]   = None
    precio_jornada:   Optional[int]   = None
    # Flag explícito que el frontend manda para indicar si el precio
    # viene de la fórmula (auto, false) o lo tipeó el admin a mano (true).
    # Si no se manda y se cambia precio_jornada, el endpoint infiere
    # según contexto (ver update_equipo).
    precio_jornada_manual: Optional[bool] = None
    precio_usd:       Optional[float] = None
    roi_pct:          Optional[float] = None
    valor_reposicion: Optional[float] = None
    foto_url:         Optional[str]   = None
    fecha_compra:     Optional[str]   = None
    serie:            Optional[str]   = None
    bh_url:           Optional[str]   = None
    dueno:            Optional[str]   = None
    visible_catalogo: Optional[int]   = None
    estado:           Optional[str]   = None
    ficha_completa:   Optional[bool]  = None


class FichaUpdate(BaseModel):
    descripcion:   Optional[str] = None
    notas:         Optional[str] = None
    specs_json:    Optional[str] = None
    montura:       Optional[str] = None
    formato:       Optional[str] = None
    resolucion:    Optional[str] = None
    keywords_json: Optional[str] = None
    nombre_publico_template: Optional[str] = None
    # Ficha extendida (enriquecimiento)
    peso:                Optional[str]   = None
    dimensiones:         Optional[str]   = None
    alimentacion:        Optional[str]   = None
    incluye_json:        Optional[str]   = None
    conectividad_json:   Optional[str]   = None
    compatible_con_json: Optional[str]   = None
    video_url:           Optional[str]   = None
    precio_bh_usd:       Optional[float] = None
    fuente_url:          Optional[str]   = None
    fuente_titulo:       Optional[str]   = None
    raw_json:            Optional[str]   = None
    enriquecido_fuente:  Optional[str]   = None


class KitItem(BaseModel):
    componente_id: int
    cantidad:      int = 1


class KitReorder(BaseModel):
    orden: list[int]  # lista de componente_id en el orden deseado


class EtiquetasUpdate(BaseModel):
    # Lista ordenada de etiquetas MANUALES. Las auto (marca/modelo/nombre/categorías)
    # se regeneran solas, no las toques desde acá.
    etiquetas: list[str]


class CategoriasUpdate(BaseModel):
    # Lista de IDs de categorías hoja (o raíz) asignadas al equipo.
    categoria_ids: list[int]


class MantenimientoCreate(BaseModel):
    fecha:            str
    tipo:             Optional[str] = "revision"   # revision / reparacion / limpieza / otro
    descripcion:      Optional[str] = None
    costo:            Optional[int] = None
    proxima_revision: Optional[str] = None


class MantenimientoUpdate(BaseModel):
    fecha:            Optional[str] = None
    tipo:             Optional[str] = None
    descripcion:      Optional[str] = None
    costo:            Optional[int] = None
    proxima_revision: Optional[str] = None


# ── Disponibilidad en tiempo real ────────────────────────────────────────────

@router.get("/equipos/afuera")
def equipos_afuera():
    """
    Devuelve los equipos actualmente retirados (pedidos en estado 'retirado'
    con fecha_hasta >= hoy), con cantidad afuera y fecha de devolución.
    Respuesta: { "equipo_id": { cantidad_afuera, stock_total, devuelve, pedidos } }
    """
    conn  = get_db()
    today = datetime.date.today().isoformat()
    try:
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
              AND p.fecha_hasta >= ?
            GROUP BY pi.equipo_id, e.cantidad
        """, (today,)).fetchall()
        return {str(r["equipo_id"]): row_to_dict(r) for r in rows}
    finally:
        conn.close()


# ── Rutas de equipos ─────────────────────────────────────────────────────────

@router.get("/equipos")
def list_equipos(
    request:       Request,
    q:                Optional[str]  = Query(None),
    etiqueta:         Optional[str]  = Query(None),
    categoria:        Optional[str]  = Query(None),
    solo_visibles:    Optional[bool] = Query(None),
    solo_incompletos: Optional[bool] = Query(None),
    sort:          Optional[str]  = Query(None, description="ranking | nombre | precio_asc | precio_desc | id"),
    spec:          Optional[list[str]] = Query(None, description="Filtros por specs: spec=key:valor"),
    page:          int = Query(1, ge=1),
    per_page:      int = Query(200, ge=1, le=500),
):
    """Lista equipos con sort y filtros.

    sort por defecto: "ranking" → ORDER BY relevancia_manual ASC,
    popularidad_score DESC, nombre ASC. Otros valores: nombre,
    precio_asc, precio_desc, id.

    spec: filtros por specs estructurados. Formato `key:valor`. Múltiples
    valores se AND-ean. Ej. `?spec=montura:E&spec=video_max:4K` filtra
    equipos con montura=E Y video_max=4K.
    """
    conn   = get_db()
    offset = (page - 1) * per_page
    base_sql = "FROM equipos e WHERE 1=1"
    params: list = []

    is_admin = bool(get_session(request))
    if solo_visibles or not is_admin:
        base_sql += " AND e.visible_catalogo = 1 AND e.estado != 'fuera_servicio'"

    # Filtro admin: equipos cuya ficha el admin aún no marcó como completa.
    if solo_incompletos and is_admin:
        base_sql += " AND e.ficha_completa = FALSE"

    # ── Filtros por specs estructurados (PR E) ──
    # Cada `spec=key:valor` agrega un AND EXISTS sobre equipo_specs.
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
                " AND EXISTS (SELECT 1 FROM equipo_specs es "
                "WHERE es.equipo_id = e.id AND es.spec_key = ? "
                "AND LOWER(es.value) = LOWER(?))"
            )
            params += [key, value]
    if q:
        # Búsqueda fuzzy global: ILIKE case-insensitive sobre nombre/marca/modelo
        # del equipo + serie + campos de la ficha (descripción, specs, keywords).
        # Convierte la barra en un find-anything: buscás "log3" o "iso 25600" y
        # aparece el equipo aunque la palabra esté en un spec, no en el nombre.
        like = f"%{q}%"
        base_sql += """ AND (
            e.nombre ILIKE ?
            OR COALESCE(e.marca, '') ILIKE ?
            OR COALESCE(e.modelo, '') ILIKE ?
            OR COALESCE(e.serie, '') ILIKE ?
            OR EXISTS (
                SELECT 1 FROM equipo_fichas ef
                WHERE ef.equipo_id = e.id AND (
                    COALESCE(ef.descripcion, '') ILIKE ?
                    OR COALESCE(ef.specs_json, '') ILIKE ?
                    OR COALESCE(ef.keywords_json, '') ILIKE ?
                )
            )
        )"""
        params += [like] * 7
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
                        SELECT id FROM categorias WHERE id = ?
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
                        SELECT id FROM categorias WHERE nombre = ?
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
            WHERE LOWER(et.nombre) = LOWER(?)
          )"""
        params.append(etiqueta)

    # ── Sort ──
    # Default: ranking compuesto (relevancia_manual + popularidad_score).
    # Esto pone los flagship arriba y desempata por uso real.
    order_clause = {
        None: "ORDER BY e.relevancia_manual ASC, e.popularidad_score DESC, e.nombre ASC",
        "ranking": "ORDER BY e.relevancia_manual ASC, e.popularidad_score DESC, e.nombre ASC",
        "nombre": "ORDER BY COALESCE(e.nombre_publico, e.nombre) ASC",
        "precio_asc": "ORDER BY e.precio_jornada ASC NULLS LAST, e.nombre ASC",
        "precio_desc": "ORDER BY e.precio_jornada DESC NULLS LAST, e.nombre ASC",
        "id": "ORDER BY e.id ASC",
    }.get(sort, "ORDER BY e.relevancia_manual ASC, e.popularidad_score DESC, e.nombre ASC")

    try:
        total = conn.execute(f"SELECT COUNT(*) {base_sql}", params).fetchone()[0]
        rows  = conn.execute(
            f"SELECT e.* {base_sql} {order_clause} LIMIT ? OFFSET ?",
            params + [per_page, offset]
        ).fetchall()
        equipos = [row_to_dict(r) for r in rows]

        # Attach brand object (id, nombre, logo_url)
        for equipo in equipos:
            if equipo.get('brand_id'):
                brand_row = conn.execute(
                    "SELECT id, nombre, logo_url FROM marcas WHERE id = ?",
                    (equipo['brand_id'],)
                ).fetchone()
                if brand_row:
                    equipo['brand'] = row_to_dict(brand_row)
            else:
                equipo['brand'] = None

        equipos = attach_tags(conn, equipos)
        equipos = attach_kit(conn, equipos)
        equipos = attach_categorias(conn, equipos)
        equipos = attach_ficha(conn, equipos)
        equipos = attach_specs_destacados(conn, equipos)
        return {"total": total, "page": page, "per_page": per_page, "items": equipos}
    finally:
        conn.close()


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

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM equipos WHERE id = ?", (actual_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Equipo no encontrado")
        equipo = attach_tags(conn, [row_to_dict(row)])[0]
        equipo = attach_ficha(conn, [equipo])[0]
        kit = conn.execute("""
            SELECT kc.componente_id, kc.cantidad, e.nombre, e.marca, e.foto_url
            FROM kit_componentes kc JOIN equipos e ON e.id = kc.componente_id
            WHERE kc.equipo_id = ?  ORDER BY e.nombre
        """, (actual_id,)).fetchall()
        equipo["kit"] = [row_to_dict(r) for r in kit]
        return equipo
    finally:
        conn.close()


@router.post("/equipos", status_code=201)
def create_equipo(data: EquipoCreate):
    conn = get_db()
    try:
        cur  = conn.execute("""
            INSERT INTO equipos (nombre, marca, modelo, cantidad,
                                 precio_jornada, precio_usd, roi_pct,
                                 valor_reposicion, foto_url, fecha_compra,
                                 serie, bh_url, dueno, visible_catalogo, estado,
                                 ficha_completa)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (data.nombre, data.marca, data.modelo, data.cantidad,
              data.precio_jornada, data.precio_usd, data.roi_pct,
              data.valor_reposicion, data.foto_url, data.fecha_compra,
              data.serie, data.bh_url, data.dueno, data.visible_catalogo, data.estado,
              bool(data.ficha_completa)))
        new_id = cur.lastrowid
        # Hook: calcular nombre_publico inicial. No falla el create si esto
        # rompe (ej. si los servicios no están disponibles).
        try:
            actualizar_nombres_de(conn, new_id, commit=False)
        except Exception:
            pass
        conn.commit()
        row    = conn.execute("SELECT * FROM equipos WHERE id=?", (new_id,)).fetchone()
        equipo = attach_tags(conn, [row_to_dict(row)])[0]
        return equipo
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.patch("/equipos/{id}")
def update_equipo(id: int, data: EquipoUpdate):
    conn     = get_db()
    try:
        existing = conn.execute("SELECT * FROM equipos WHERE id=?", (id,)).fetchone()
        if not existing:
            raise HTTPException(404, "Equipo no encontrado")
        updates = data.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(400, "Nada para actualizar")
        # Registrar cambio de precio si cambió
        if "precio_jornada" in updates and updates["precio_jornada"] != existing["precio_jornada"]:
            conn.execute(
                "INSERT INTO equipo_precio_historial (equipo_id, precio_jornada) VALUES (?,?)",
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
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        set_clause += ", updated_at = CURRENT_TIMESTAMP"
        conn.execute(f"UPDATE equipos SET {set_clause} WHERE id = ?",
                     list(updates.values()) + [id])
        # Si cambió algo que alimenta auto-tags, regenerar.
        if any(k in updates for k in ("nombre", "marca", "modelo")):
            regenerate_auto_tags(conn, id)
        # Hook: si cambió algo que afecta el nombre público, recalcular.
        # No falla el update si el recálculo rompe.
        if any(k in updates for k in ("nombre", "marca", "modelo")):
            try:
                actualizar_nombres_de(conn, id, commit=False)
            except Exception:
                pass
        conn.commit()
        row    = conn.execute("SELECT * FROM equipos WHERE id=?", (id,)).fetchone()
        equipo = attach_tags(conn, [row_to_dict(row)])[0]
        return equipo
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.delete("/equipos/{id}", status_code=204)
def delete_equipo(id: int):
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        conn.execute("DELETE FROM equipos WHERE id=?", (id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Ficha por equipo ─────────────────────────────────────────────────────────

@router.get("/equipos/{id}/ficha")
def get_ficha(id: int):
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        row = conn.execute(
            "SELECT * FROM equipo_fichas WHERE equipo_id = ?", (id,)
        ).fetchone()
        if row:
            return row_to_dict(row)
        return {
            "equipo_id": id, "descripcion": None, "notas": None, "specs_json": None,
            "montura": None, "formato": None, "resolucion": None, "keywords_json": None,
            "nombre_publico_template": None,
        }
    finally:
        conn.close()


@router.put("/equipos/{id}/ficha")
def upsert_ficha(id: int, data: FichaUpdate):
    """
    PATCH-style upsert: solo actualiza columnas que vinieron en el body
    (no las nullea si el cliente no las mandó). Esto evita que enriquecer con
    IA borre montura/formato/resolución existentes.
    """
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")

        patch = data.model_dump(exclude_unset=True)
        # Inserta una fila vacía si no existe (para que el UPDATE encuentre algo).
        conn.execute(
            "INSERT INTO equipo_fichas (equipo_id) VALUES (?) ON CONFLICT(equipo_id) DO NOTHING",
            (id,),
        )
        if patch:
            set_clause = ", ".join(f"{k} = ?" for k in patch)
            set_clause += ", updated_at = CURRENT_TIMESTAMP"
            conn.execute(
                f"UPDATE equipo_fichas SET {set_clause} WHERE equipo_id = ?",
                list(patch.values()) + [id],
            )
            # Hook: si cambió el template de nombre o specs estructuradas
            # (montura/formato/resolucion legacy), recalcular nombre_publico.
            keys_que_afectan_nombre = {
                "nombre_publico_template", "montura", "formato", "resolucion",
            }
            if any(k in patch for k in keys_que_afectan_nombre):
                try:
                    actualizar_nombres_de(conn, id, commit=False)
                except Exception:
                    pass
        conn.commit()
        row = conn.execute(
            "SELECT * FROM equipo_fichas WHERE equipo_id = ?", (id,)
        ).fetchone()
        return row_to_dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Historial de alquileres por equipo ───────────────────────────────────────

@router.get("/equipos/{id}/historial")
def get_equipo_historial(id: int):
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")

        rows = conn.execute("""
            SELECT
                p.id, p.numero_pedido, p.estado,
                p.fecha_desde, p.fecha_hasta,
                COALESCE(c.nombre || ' ' || c.apellido, p.cliente_nombre) AS cliente,
                pi.cantidad, pi.precio_jornada AS precio_item,
                GREATEST(1, DATE_PART('day', LEFT(p.fecha_hasta, 10)::TIMESTAMP - LEFT(p.fecha_desde, 10)::TIMESTAMP))::INTEGER AS dias
            FROM alquiler_items pi
            JOIN alquileres p ON p.id = pi.pedido_id
            LEFT JOIN clientes c ON c.id = p.cliente_id
            WHERE pi.equipo_id = ?
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
    finally:
        conn.close()


# ── Mantenimiento log ────────────────────────────────────────────────────────

@router.get("/equipos/{id}/mantenimiento")
def list_mantenimiento(id: int):
    """Lista los eventos de mantenimiento del equipo, más recientes primero."""
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        rows = conn.execute("""
            SELECT id, equipo_id, fecha, tipo, descripcion, costo, proxima_revision, created_at
            FROM equipo_mantenimiento WHERE equipo_id = ?
            ORDER BY fecha DESC, id DESC
        """, (id,)).fetchall()
        items = [row_to_dict(r) for r in rows]
        # Proxima revisión pendiente más cercana (futura o vencida).
        pendientes = [r for r in items if r.get("proxima_revision")]
        proxima = min(pendientes, key=lambda r: r["proxima_revision"]) if pendientes else None
        return {
            "items": items,
            "stats": {
                "total_eventos": len(items),
                "total_costo": sum((r.get("costo") or 0) for r in items),
                "proxima_revision": proxima["proxima_revision"] if proxima else None,
            },
        }
    finally:
        conn.close()


@router.post("/equipos/{id}/mantenimiento", status_code=201)
def add_mantenimiento(id: int, data: MantenimientoCreate):
    """Agrega un evento de mantenimiento al equipo."""
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        cur = conn.execute("""
            INSERT INTO equipo_mantenimiento (equipo_id, fecha, tipo, descripcion, costo, proxima_revision)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (id, data.fecha, data.tipo or "revision", data.descripcion, data.costo, data.proxima_revision))
        conn.commit()
        new_id = cur.lastrowid
        row = conn.execute(
            "SELECT * FROM equipo_mantenimiento WHERE id = ?", (new_id,)
        ).fetchone()
        return row_to_dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.patch("/equipos/{id}/mantenimiento/{log_id}")
def update_mantenimiento(id: int, log_id: int, data: MantenimientoUpdate):
    """Actualiza un evento de mantenimiento existente."""
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT * FROM equipo_mantenimiento WHERE id = ? AND equipo_id = ?",
            (log_id, id),
        ).fetchone()
        if not existing:
            raise HTTPException(404, "Evento no encontrado")
        updates = data.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(400, "Nada para actualizar")
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE equipo_mantenimiento SET {set_clause} WHERE id = ?",
            list(updates.values()) + [log_id],
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM equipo_mantenimiento WHERE id = ?", (log_id,)
        ).fetchone()
        return row_to_dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.delete("/equipos/{id}/mantenimiento/{log_id}", status_code=204)
def delete_mantenimiento(id: int, log_id: int):
    """Elimina un evento de mantenimiento."""
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM equipo_mantenimiento WHERE id = ? AND equipo_id = ?",
            (log_id, id),
        ).fetchone()
        if not existing:
            raise HTTPException(404, "Evento no encontrado")
        conn.execute("DELETE FROM equipo_mantenimiento WHERE id = ?", (log_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Kit / Componentes ────────────────────────────────────────────────────────

@router.get("/equipos/{id}/kit")
def get_kit(id: int):
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        rows = conn.execute("""
            SELECT kc.id, kc.componente_id, kc.cantidad, kc.orden,
                   e.nombre, e.marca, e.modelo, e.foto_url, e.visible_catalogo
            FROM kit_componentes kc
            JOIN equipos e ON e.id = kc.componente_id
            WHERE kc.equipo_id = ?
            ORDER BY kc.orden ASC, e.nombre ASC
        """, (id,)).fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


@router.post("/equipos/{id}/kit", status_code=201)
def add_kit_item(id: int, data: KitItem):
    if id == data.componente_id:
        raise HTTPException(400, "Un equipo no puede ser componente de sí mismo")
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (data.componente_id,)).fetchone():
            raise HTTPException(404, "Componente no encontrado")
        try:
            conn.execute("""
                INSERT INTO kit_componentes (equipo_id, componente_id, cantidad)
                VALUES (?,?,?)
                ON CONFLICT(equipo_id, componente_id) DO UPDATE SET cantidad=excluded.cantidad
            """, (id, data.componente_id, data.cantidad))
            conn.commit()
        except Exception as e:
            raise HTTPException(400, str(e))
        return get_kit(id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.delete("/equipos/{id}/kit/{componente_id}", status_code=204)
def remove_kit_item(id: int, componente_id: int):
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM kit_componentes WHERE equipo_id=? AND componente_id=?",
            (id, componente_id)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.post("/admin/equipos/{id}/kit/reorder")
def reorder_kit(id: int, data: KitReorder, request: Request):
    """Reordena los componentes del kit según el array de componente_id."""
    require_admin(request)
    conn = get_db()
    try:
        for i, componente_id in enumerate(data.orden):
            conn.execute(
                "UPDATE kit_componentes SET orden=? WHERE equipo_id=? AND componente_id=?",
                (i, id, componente_id)
            )
        conn.commit()
        return {"ok": True}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Historial de precios ─────────────────────────────────────────────────────

@router.get("/equipos/{id}/precio-historial")
def get_precio_historial(id: int):
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        rows = conn.execute("""
            SELECT precio_jornada, changed_at
            FROM equipo_precio_historial
            WHERE equipo_id = ?
            ORDER BY changed_at DESC
        """, (id,)).fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


# ── Etiquetas por equipo (reemplaza todas) ────────────────────────────────────

@router.put("/equipos/{id}/etiquetas", status_code=200)
def set_etiquetas(id: int, data: EtiquetasUpdate):
    """Reemplaza SOLO las etiquetas manuales del equipo. Las auto se preservan."""
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        # Borrar solo manuales; las auto siguen vivas.
        conn.execute(
            "DELETE FROM equipo_etiquetas WHERE equipo_id = ? AND origen = 'manual'",
            (id,),
        )
        for orden, nombre in enumerate(data.etiquetas):
            nombre = (nombre or "").strip()
            if not nombre:
                continue
            conn.execute(
                "INSERT INTO etiquetas (nombre) VALUES (?) ON CONFLICT (nombre) DO NOTHING",
                (nombre,),
            )
            row = conn.execute(
                "SELECT id FROM etiquetas WHERE nombre = ?", (nombre,)
            ).fetchone()
            if not row:
                continue
            conn.execute("""
                INSERT INTO equipo_etiquetas (equipo_id, etiqueta_id, orden, origen)
                VALUES (?, ?, ?, 'manual')
                ON CONFLICT (equipo_id, etiqueta_id)
                DO UPDATE SET orden = EXCLUDED.orden, origen = 'manual'
            """, (id, row["id"], orden))
        conn.commit()
        row    = conn.execute("SELECT * FROM equipos WHERE id=?", (id,)).fetchone()
        equipo = attach_tags(conn, [row_to_dict(row)])[0]
        return equipo
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Categorías por equipo ────────────────────────────────────────────────────

@router.put("/equipos/{id}/categorias", status_code=200)
def set_categorias(id: int, data: CategoriasUpdate):
    """
    Reemplaza la lista de categorías asignadas al equipo y regenera auto-tags
    (porque los nombres de categoría alimentan la bolsa de etiquetas auto).
    """
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        conn.execute("DELETE FROM equipo_categorias WHERE equipo_id = ?", (id,))
        for orden, cid in enumerate(data.categoria_ids):
            try:
                cid_int = int(cid)
            except (TypeError, ValueError):
                continue
            conn.execute("""
                INSERT INTO equipo_categorias (equipo_id, categoria_id, orden)
                VALUES (?, ?, ?)
                ON CONFLICT (equipo_id, categoria_id) DO UPDATE SET orden = EXCLUDED.orden
            """, (id, cid_int, orden))
        regenerate_auto_tags(conn, id)
        # Hook: cambió la categoría → cambia el template de specs aplicable
        # → puede cambiar el nombre público auto-generado.
        try:
            actualizar_nombres_de(conn, id, commit=False)
        except Exception:
            pass
        conn.commit()
        row    = conn.execute("SELECT * FROM equipos WHERE id=?", (id,)).fetchone()
        equipo = attach_tags(conn, [row_to_dict(row)])[0]
        equipo = attach_categorias(conn, [equipo])[0]
        return equipo
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Etiquetas / Categorías ───────────────────────────────────────────────────

@router.get("/etiquetas")
def list_etiquetas(incluir_auto: int = Query(0)):
    """
    Lista etiquetas. Por defecto devuelve solo las que tienen al menos un uso
    MANUAL (las auto inflan demasiado). `incluir_auto=1` devuelve todo.
    """
    conn = get_db()
    try:
        if incluir_auto:
            rows = conn.execute("""
                SELECT et.nombre, COUNT(ee.equipo_id) AS total
                FROM etiquetas et
                LEFT JOIN equipo_etiquetas ee ON ee.etiqueta_id = et.id
                GROUP BY et.id, et.nombre
                ORDER BY LOWER(et.nombre)
            """).fetchall()
        else:
            rows = conn.execute("""
                SELECT et.nombre, COUNT(ee.equipo_id) AS total
                FROM etiquetas et
                JOIN equipo_etiquetas ee ON ee.etiqueta_id = et.id
                WHERE ee.origen = 'manual'
                GROUP BY et.id, et.nombre
                ORDER BY LOWER(et.nombre)
            """).fetchall()
        return [{"nombre": r["nombre"], "total": r["total"]} for r in rows]
    finally:
        conn.close()


@router.get("/categorias")
def get_categorias(flat: int = Query(0)):
    """
    Devuelve el árbol de categorías desde la tabla `categorias`.
    `total` cuenta equipos asignados a esa categoría o a cualquier descendiente
    (vía `equipo_categorias`).
    """
    conn = get_db()
    try:
        # #131: agregamos popularidad_score como tiebreaker después de
        # prioridad (manual override del admin). Si todas tienen la misma
        # prioridad (default 100), gana la popularidad real.
        cats = conn.execute("""
            SELECT id, nombre, prioridad, parent_id, popularidad_score
            FROM categorias
            ORDER BY prioridad ASC, popularidad_score DESC, LOWER(nombre) ASC
        """).fetchall()

        nodes = {
            r["id"]: {
                "id": r["id"], "nombre": r["nombre"], "prioridad": r["prioridad"],
                "parent_id": r["parent_id"], "total": 0, "children": [],
            }
            for r in cats
        }
        roots = []
        for r in cats:
            n = nodes[r["id"]]
            if r["parent_id"] and r["parent_id"] in nodes:
                nodes[r["parent_id"]]["children"].append(n)
            else:
                roots.append(n)

        # Conteo por subárbol: equipos distintos asignados a la categoría o a un descendiente.
        eq_rows = conn.execute(
            "SELECT equipo_id, categoria_id FROM equipo_categorias"
        ).fetchall()
        from collections import defaultdict
        eq_cats: dict[int, set] = defaultdict(set)
        for r in eq_rows:
            eq_cats[r["equipo_id"]].add(r["categoria_id"])

        def descendants(nid: int) -> set:
            out = {nid}
            stack = [nid]
            while stack:
                cur = stack.pop()
                for n in nodes.values():
                    if n["parent_id"] == cur:
                        out.add(n["id"]); stack.append(n["id"])
            return out

        for nid, n in nodes.items():
            sub = descendants(nid)
            n["total"] = sum(1 for tags in eq_cats.values() if tags & sub)

        for n in nodes.values():
            n["children"].sort(key=lambda x: (x["prioridad"], x["nombre"].lower()))
        roots.sort(key=lambda x: (x["prioridad"], x["nombre"].lower()))

        if flat:
            return [
                {
                    "nombre": r["nombre"], "total": r["total"], "prioridad": r["prioridad"],
                    "subtags": [{"nombre": c["nombre"], "total": c["total"]} for c in r["children"]],
                }
                for r in roots
            ]

        def clean(n):
            return {
                "id": n["id"], "nombre": n["nombre"], "prioridad": n["prioridad"],
                "total": n["total"], "parent_id": n["parent_id"],
                "children": [clean(c) for c in n["children"]],
            }
        return [clean(r) for r in roots]
    finally:
        conn.close()


# ── Admin: gestión de etiquetas / categorías ─────────────────────────────────

class EtiquetaCreate(BaseModel):
    nombre:    str
    prioridad: Optional[int] = 100
    parent_id: Optional[int] = None


class EtiquetaPatch(BaseModel):
    nombre:    Optional[str] = None
    prioridad: Optional[int] = None
    parent_id: Optional[int] = None  # explícito None para "limpiar" no soportado vía PATCH; usar -1 para nullear
    set_parent_null: Optional[bool] = False


class EtiquetasReorder(BaseModel):
    ids: list[int]


@router.get("/admin/equipos/sin-serie")
def admin_equipos_sin_serie(request: Request):
    """Lista equipos sin número de serie cargado.

    Útil para que el admin priorice completar el inventario (issue #91).
    Ordena por valor de reposición DESC — primero los equipos más caros
    (importantes para identificar en caso de pérdida/daño).

    Considera \"sin serie\" cualquier valor NULL, vacío o solo espacios.
    NOTA: 'N/A' es un valor válido — significa \"no aplica\" (reflectores,
    cables sin serie, etc.). El admin lo seteó explícitamente, no falta.
    """
    require_admin(request)
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT id, nombre, marca, modelo, foto_url,
                   valor_reposicion, dueno, cantidad
            FROM equipos
            WHERE serie IS NULL OR TRIM(serie) = ''
            ORDER BY COALESCE(valor_reposicion, 0) DESC, id ASC
        """).fetchall()
        return {
            "total": len(rows),
            "equipos": [row_to_dict(r) for r in rows],
        }
    finally:
        conn.close()


@router.get("/admin/etiquetas")
def admin_list_etiquetas(request: Request):
    require_admin(request)
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT et.id, et.nombre, et.prioridad, et.parent_id,
                   COUNT(ee.equipo_id) AS total
            FROM etiquetas et
            LEFT JOIN equipo_etiquetas ee ON ee.etiqueta_id = et.id
            GROUP BY et.id, et.nombre, et.prioridad, et.parent_id
            ORDER BY et.prioridad ASC, LOWER(et.nombre) ASC
        """).fetchall()
        return [
            {
                "id":        r["id"],
                "nombre":    r["nombre"],
                "prioridad": r["prioridad"],
                "parent_id": r["parent_id"],
                "total":     r["total"],
            }
            for r in rows
        ]
    finally:
        conn.close()


@router.post("/admin/etiquetas", status_code=201)
def admin_create_etiqueta(data: EtiquetaCreate, request: Request):
    require_admin(request)
    nombre = (data.nombre or "").strip()
    if not nombre:
        raise HTTPException(400, "Nombre vacío")
    conn = get_db()
    try:
        # Validar parent: debe existir y ser raíz (forzar 2 niveles).
        if data.parent_id is not None:
            prow = conn.execute(
                "SELECT id, parent_id FROM etiquetas WHERE id = ?", (data.parent_id,)
            ).fetchone()
            if not prow:
                raise HTTPException(400, "parent_id no existe")
            if prow["parent_id"] is not None:
                raise HTTPException(400, "Solo se permiten 2 niveles (el padre ya es subcategoría)")
        cur = conn.execute("""
            INSERT INTO etiquetas (nombre, prioridad, parent_id)
            VALUES (?, ?, ?)
            ON CONFLICT (nombre) DO UPDATE
                SET prioridad = EXCLUDED.prioridad,
                    parent_id = EXCLUDED.parent_id
            RETURNING id, nombre, prioridad, parent_id
        """, (nombre, data.prioridad or 100, data.parent_id))
        row = cur.fetchone()
        conn.commit()
        return {
            "id": row["id"], "nombre": row["nombre"],
            "prioridad": row["prioridad"], "parent_id": row["parent_id"],
            "total": 0,
        }
    except HTTPException:
        conn.rollback(); raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(400, str(e))
    finally:
        conn.close()


@router.patch("/admin/etiquetas/{eid}")
def admin_update_etiqueta(eid: int, patch: EtiquetaPatch, request: Request):
    require_admin(request)
    sets, vals = [], []
    if patch.nombre is not None:
        sets.append("nombre = ?"); vals.append(patch.nombre.strip())
    if patch.prioridad is not None:
        sets.append("prioridad = ?"); vals.append(int(patch.prioridad))
    if patch.set_parent_null:
        sets.append("parent_id = NULL")
    elif patch.parent_id is not None:
        if patch.parent_id == eid:
            raise HTTPException(400, "Una etiqueta no puede ser su propio padre")
        # Validar que el padre exista y sea raíz.
        conn0 = get_db()
        try:
            prow = conn0.execute(
                "SELECT id, parent_id FROM etiquetas WHERE id = ?", (patch.parent_id,)
            ).fetchone()
            if not prow:
                raise HTTPException(400, "parent_id no existe")
            if prow["parent_id"] is not None:
                raise HTTPException(400, "Solo se permiten 2 niveles")
            # Verificar que esta etiqueta no tenga hijos (sino bajaríamos un nivel raíz).
            chrow = conn0.execute(
                "SELECT 1 FROM etiquetas WHERE parent_id = ? LIMIT 1", (eid,)
            ).fetchone()
            if chrow:
                raise HTTPException(400, "Esta etiqueta tiene hijos; no puede convertirse en hija")
        finally:
            conn0.close()
        sets.append("parent_id = ?"); vals.append(int(patch.parent_id))
    if not sets:
        raise HTTPException(400, "Sin cambios")
    conn = get_db()
    try:
        vals.append(eid)
        conn.execute(f"UPDATE etiquetas SET {', '.join(sets)} WHERE id = ?", tuple(vals))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.delete("/admin/etiquetas/{eid}", status_code=204)
def admin_delete_etiqueta(eid: int, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        # ON DELETE CASCADE en equipo_etiquetas + SET NULL en parent_id de hijos.
        conn.execute("DELETE FROM etiquetas WHERE id = ?", (eid,))
        conn.commit()
    finally:
        conn.close()


@router.post("/admin/etiquetas/reorder")
def admin_reorder_etiquetas(payload: EtiquetasReorder, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        for idx, eid in enumerate(payload.ids):
            conn.execute(
                "UPDATE etiquetas SET prioridad = ? WHERE id = ?",
                ((idx + 1) * 10, eid),
            )
        conn.commit()
        return {"ok": True, "count": len(payload.ids)}
    finally:
        conn.close()


# ── Admin: clasificación automática de equipos ───────────────────────────────

# Reglas leaf → keywords. Orden importa: más específico primero.
# Cada equipo recibe TODAS las hojas que matcheen (multi-asignación).
# Se aplica sobre nombre + marca + modelo (lowercase).
_RULES_LEAF = [
    # ── CÁMARAS (multi: foto+video para mirrorless híbridas) ────────────
    ("Foto",           ["a7 v", "zv-e1"]),  # mirrorless híbridas → también foto
    ("Video",          ["a7 v", "zv-e1", "fx3", "komodo", "c200"]),
    ("Acción",         ["gopro", "insta360"]),
    # ── LENTES ─────────────────────────────────────────────────────────
    ("Vintage",        ["vintage", "carl zeiss jena"]),
    ("Especiales",     ["laowa", "probe macro"]),
    ("Zoom E-mount",   ["sony gm", "montura e"]),
    ("Zoom EF",        ["sigma art 18-35", "sigma art 24-70", "tokina 11-16", "canon 70-200"]),
    ("Fijos EF",       ["sigma art 35mm", "sigma art 50mm"]),
    # ── ADAPTADORES Y FILTROS ──────────────────────────────────────────
    ("Adaptadores de montura", ["adaptador "]),
    ("Filtros 82mm",   ["filtro "]),
    # ── ILUMINACIÓN ────────────────────────────────────────────────────
    ("LED RGB",        ["rgb", "tl60", "m1 mini", "amaran 300c", "accent b7c"]),
    ("LED daylight/bicolor", ["led", "amaran", "nanlite", "godox vl", "spotlight"]),
    ("Tungsteno",      ["tungsteno", "fresnel arri", "mole richardson", "lowel par", "open face", "focus light"]),
    ("Fluorescente",   ["kino flo", "caselight", "pampa tubo", "fluorescente"]),
    ("On-camera / Flash", ["flash godox", "luz on-camera", "yongnuo yn300", "dracast bicolor"]),
    ("Práctica / efecto", ["globo china", "máquina de humo", "smokegenie"]),
    # ── MODIFICADORES ──────────────────────────────────────────────────
    ("Softbox",        ["softbox", "light dome", "ad-s60"]),
    ("Difusión / Frame", ["frame difusión", "fresnel attachment"]),
    ("Reflectores",    ["reflector"]),
    ("Banderas",       ["bandera"]),
    # ── SOPORTES ───────────────────────────────────────────────────────
    ("Trípodes video", ["manfrotto 502", "manfrotto 504", "manfrotto 529", "trípode fluido", "trípode galera"]),
    ("Trípodes foto",  ["xpro 4s", "trípode foto", "manfrotto elements"]),
    ("C-Stands",       ["c-stand"]),
    ("Estabilización", ["gimbal", "ronin", "steadicam", "glidecam", "tilta gravity"]),
    ("Slider / Dolly / Riel", ["slider", "dolly", "riel "]),
    ("Car Mount",      ["car mount", "tilta hydra"]),
    # ── GRIP ───────────────────────────────────────────────────────────
    ("Brazos",         ["brazo ", "boom arm", "magic arm", "superflex", "brazo mágico"]),
    ("Clamps",         ["clamp", "superclamp", "avenger c1510", "avenger c4462", "avenger e390"]),
    ("Wall plates / pins", ["wall plate", "baby pin", "junior pin"]),
    ("Pinzas",         ["pinza"]),
    ("Líneas de seguridad", ["línea de seguridad", "linea de seguridad"]),
    ("Sopapa",         ["sopapa"]),
    ("Lastre",         ["bolsa de arena", "saco de arena"]),
    # ── SONIDO ─────────────────────────────────────────────────────────
    ("Inalámbricos / Lavalier", ["dji mic", "wireless go", "lavalier"]),
    ("Shotgun / Boom", ["shotgun", "ntg2", "mke 600", "caña boom", "zeppelin"]),
    ("On-camera (sonido)", ["videomic", "mke 400"]),
    ("Estudio / Podcast", ["procaster", "rodecaster"]),
    ("Intercom",       ["intercom", "solidcom", "hollyland"]),
    # ── MONITORES Y VIDEO ──────────────────────────────────────────────
    ("Monitores",      ["monitor de campo", "smallhd", "lilliput", "viltrox 6", "monitor on-camera"]),
    ("Grabadores",     ["video assist", "grabador"]),
    ("Transmisión inalámbrica", ["sdr transmission", "transmisor inalámbrico"]),
    ("Follow Focus / Matebox", ["follow focus", "nucleus", "matebox", "matte box"]),
    # ── ENERGÍA ────────────────────────────────────────────────────────
    ("V-Mount",        ["v-mount", "vmount"]),
    ("NP / LP-E6",     ["np-f", "np-fz", "lp-e6", "np serie-l"]),
    ("Distribución eléctrica", ["zapatilla", "alargue eléctrico"]),
    # ── MEDIA Y DATOS ──────────────────────────────────────────────────
    ("Tarjetas SD",    ["tarjeta sd"]),
    ("Tarjetas CFexpress", ["cfexpress"]),
    ("Lectores",       ["lector"]),
    # ── ESTUDIO Y PRODUCCIÓN ───────────────────────────────────────────
    ("Set / Backdrops", ["backdrop", "mesa de producción"]),
    ("Paquetes",       ["rambla estudio", "estudio equipos promo"]),
]


def _propose_tags(nombre: str, marca: str, modelo: str) -> list[str]:
    """Devuelve la lista de etiquetas hoja propuestas para un equipo."""
    text = f"{nombre} {marca or ''} {modelo or ''}".lower()
    matches = []
    for leaf, kws in _RULES_LEAF:
        for kw in kws:
            if kw in text:
                matches.append(leaf)
                break
    # Dedupe preservando orden
    seen = set()
    out = []
    for m in matches:
        if m not in seen:
            out.append(m); seen.add(m)
    return out


# ── Admin: CRUD de categorías (árbol propio) ─────────────────────────────────

class CategoriaCreate(BaseModel):
    nombre:    str
    prioridad: Optional[int] = 100
    parent_id: Optional[int] = None


class CategoriaPatch(BaseModel):
    nombre:    Optional[str] = None
    prioridad: Optional[int] = None
    parent_id: Optional[int] = None
    set_parent_null: Optional[bool] = False


class CategoriasReorder(BaseModel):
    ids: list[int]


@router.get("/admin/categorias")
def admin_list_categorias(request: Request):
    require_admin(request)
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT c.id, c.nombre, c.prioridad, c.parent_id,
                   COUNT(ec.equipo_id) AS total
            FROM categorias c
            LEFT JOIN equipo_categorias ec ON ec.categoria_id = c.id
            GROUP BY c.id, c.nombre, c.prioridad, c.parent_id
            ORDER BY c.prioridad ASC, LOWER(c.nombre) ASC
        """).fetchall()
        return [
            {"id": r["id"], "nombre": r["nombre"], "prioridad": r["prioridad"],
             "parent_id": r["parent_id"], "total": r["total"]}
            for r in rows
        ]
    finally:
        conn.close()


@router.post("/admin/categorias", status_code=201)
def admin_create_categoria(data: CategoriaCreate, request: Request):
    require_admin(request)
    nombre = (data.nombre or "").strip()
    if not nombre:
        raise HTTPException(400, "Nombre vacío")
    conn = get_db()
    try:
        if data.parent_id is not None:
            prow = conn.execute(
                "SELECT id, parent_id FROM categorias WHERE id = ?", (data.parent_id,)
            ).fetchone()
            if not prow:
                raise HTTPException(400, "parent_id no existe")
            if prow["parent_id"] is not None:
                raise HTTPException(400, "Solo se permiten 2 niveles")
        cur = conn.execute("""
            INSERT INTO categorias (nombre, prioridad, parent_id)
            VALUES (?, ?, ?)
            ON CONFLICT (nombre) DO UPDATE
                SET prioridad = EXCLUDED.prioridad,
                    parent_id = EXCLUDED.parent_id
            RETURNING id, nombre, prioridad, parent_id
        """, (nombre, data.prioridad or 100, data.parent_id))
        row = cur.fetchone()
        conn.commit()
        return {"id": row["id"], "nombre": row["nombre"],
                "prioridad": row["prioridad"], "parent_id": row["parent_id"], "total": 0}
    except HTTPException:
        conn.rollback(); raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(400, str(e))
    finally:
        conn.close()


@router.patch("/admin/categorias/{cid}")
def admin_update_categoria(cid: int, patch: CategoriaPatch, request: Request):
    require_admin(request)
    sets, vals = [], []
    nuevo_nombre = None
    if patch.nombre is not None:
        nuevo_nombre = patch.nombre.strip()
        if not nuevo_nombre:
            raise HTTPException(400, "El nombre no puede estar vacío")
        sets.append("nombre = ?"); vals.append(nuevo_nombre)
    if patch.prioridad is not None:
        sets.append("prioridad = ?"); vals.append(int(patch.prioridad))
    if patch.set_parent_null:
        sets.append("parent_id = NULL")
    elif patch.parent_id is not None:
        if patch.parent_id == cid:
            raise HTTPException(400, "Una categoría no puede ser su propio padre")
        conn0 = get_db()
        try:
            prow = conn0.execute(
                "SELECT id, parent_id FROM categorias WHERE id = ?", (patch.parent_id,)
            ).fetchone()
            if not prow:
                raise HTTPException(400, "parent_id no existe")
            if prow["parent_id"] is not None:
                raise HTTPException(400, "Solo se permiten 2 niveles")
            chrow = conn0.execute(
                "SELECT 1 FROM categorias WHERE parent_id = ? LIMIT 1", (cid,)
            ).fetchone()
            if chrow:
                raise HTTPException(400, "Esta categoría tiene hijos")
        finally:
            conn0.close()
        sets.append("parent_id = ?"); vals.append(int(patch.parent_id))
    if not sets:
        raise HTTPException(400, "Sin cambios")

    # Pre-check: si hay rename, verificar que la categoría existe y que el
    # nuevo nombre no choca con otra. Mejor error de conflicto explícito que
    # 500 por UniqueViolation de psycopg2.
    if nuevo_nombre is not None:
        conn0 = get_db()
        try:
            existe = conn0.execute(
                "SELECT id FROM categorias WHERE id = ?", (cid,)
            ).fetchone()
            if not existe:
                raise HTTPException(404, f"Categoría {cid} no existe")
            choca = conn0.execute(
                "SELECT id, nombre FROM categorias WHERE LOWER(nombre) = LOWER(?) AND id != ?",
                (nuevo_nombre, cid),
            ).fetchone()
            if choca:
                raise HTTPException(409, f"Ya existe una categoría llamada '{choca['nombre']}'")
        finally:
            conn0.close()

    conn = get_db()
    try:
        vals.append(cid)
        conn.execute(f"UPDATE categorias SET {', '.join(sets)} WHERE id = ?", tuple(vals))
        # Si renombró, regenerar auto-tags de los equipos afectados.
        if nuevo_nombre is not None:
            eq_rows = conn.execute(
                "SELECT equipo_id FROM equipo_categorias WHERE categoria_id = ?", (cid,)
            ).fetchall()
            for r in eq_rows:
                try:
                    regenerate_auto_tags(conn, r["equipo_id"])
                except Exception:
                    # No abortar el rename si un equipo falla regenerar tags.
                    logger.warning("regenerate_auto_tags falló para equipo %s tras rename de cat %s",
                                   r["equipo_id"], cid, exc_info=True)
        conn.commit()
        return {"ok": True}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        logger.error("Error en admin_update_categoria(cid=%s): %s", cid, e, exc_info=True)
        raise HTTPException(500, "Error al actualizar categoría — ver logs del servidor")
    finally:
        conn.close()


@router.delete("/admin/categorias/{cid}", status_code=204)
def admin_delete_categoria(cid: int, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        eq_rows = conn.execute(
            "SELECT equipo_id FROM equipo_categorias WHERE categoria_id = ?", (cid,)
        ).fetchall()
        affected = [r["equipo_id"] for r in eq_rows]
        conn.execute("DELETE FROM categorias WHERE id = ?", (cid,))
        for eid in affected:
            regenerate_auto_tags(conn, eid)
        conn.commit()
    finally:
        conn.close()


@router.post("/admin/categorias/reorder")
def admin_reorder_categorias(payload: CategoriasReorder, request: Request):
    require_admin(request)
    conn = get_db()
    try:
        for idx, cid in enumerate(payload.ids):
            conn.execute(
                "UPDATE categorias SET prioridad = ? WHERE id = ?",
                ((idx + 1) * 10, cid),
            )
        conn.commit()
        return {"ok": True, "count": len(payload.ids)}
    finally:
        conn.close()


# ── Admin: clasificación automática (escribe en equipo_categorias) ───────────

@router.post("/admin/categorias/clasificar")
def admin_clasificar(request: Request, apply: int = Query(0)):
    """
    Calcula categorías hoja propuestas para todos los equipos.
    - apply=0: dry-run.
    - apply=1: REEMPLAZA las categorías de cada equipo que matchee al menos 1
      regla; los que no matchean no se tocan. Regenera auto-tags después.
    """
    require_admin(request)

    conn = get_db()
    try:
        equipos = conn.execute("""
            SELECT e.id, e.nombre, e.marca, e.modelo
            FROM equipos e
            ORDER BY e.nombre
        """).fetchall()

        # Categorías actuales por equipo (para mostrar el diff).
        rows = conn.execute("""
            SELECT ec.equipo_id, c.nombre
            FROM equipo_categorias ec
            JOIN categorias c ON c.id = ec.categoria_id
        """).fetchall()
        from collections import defaultdict
        actuales: dict[int, list[str]] = defaultdict(list)
        for r in rows:
            actuales[r["equipo_id"]].append(r["nombre"])

        # Mapa nombre→id de categorías hoja válidas.
        leaf_rows = conn.execute(
            "SELECT id, nombre FROM categorias WHERE parent_id IS NOT NULL"
        ).fetchall()
        leaf_id = {r["nombre"]: r["id"] for r in leaf_rows}

        items = []
        matched = 0
        applied = 0
        for eq in equipos:
            propuestas = _propose_tags(eq["nombre"], eq["marca"] or "", eq["modelo"] or "")
            propuestas = [p for p in propuestas if p in leaf_id]
            if propuestas:
                matched += 1
                if apply:
                    conn.execute(
                        "DELETE FROM equipo_categorias WHERE equipo_id = ?", (eq["id"],)
                    )
                    for orden, name in enumerate(propuestas):
                        conn.execute("""
                            INSERT INTO equipo_categorias (equipo_id, categoria_id, orden)
                            VALUES (?, ?, ?)
                            ON CONFLICT (equipo_id, categoria_id)
                            DO UPDATE SET orden = EXCLUDED.orden
                        """, (eq["id"], leaf_id[name], orden))
                    regenerate_auto_tags(conn, eq["id"])
                    applied += 1
            items.append({
                "id":        eq["id"],
                "nombre":    eq["nombre"],
                "marca":     eq["marca"],
                "propuestas": propuestas,
                "actuales":  actuales.get(eq["id"], []),
            })

        if apply:
            conn.commit()

        return {
            "total":     len(equipos),
            "matched":   matched,
            "unmatched": len(equipos) - matched,
            "applied":   applied,
            "items":     items,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()



@router.get("/equipos/{id}/calendario")
def get_equipo_calendario(id: int, year: int = Query(...), month: int = Query(...)):
    """Per-day available unit count for a given equipment and month."""
    if not (1 <= month <= 12):
        raise HTTPException(400, "Mes inválido")

    conn = get_db()
    try:
        equipo = conn.execute(
            "SELECT id, cantidad FROM equipos WHERE id=?", (id,)
        ).fetchone()
        if not equipo:
            raise HTTPException(404, "Equipo no encontrado")

        stock_total     = equipo["cantidad"]
        _, days_in_month = _cal.monthrange(year, month)
        first_day       = _date(year, month, 1).isoformat()
        last_day        = _date(year, month, days_in_month).isoformat()

        ESTADOS = "('presupuesto','confirmado','retirado')"

        # Direct reservations that overlap this month
        directas = conn.execute(f"""
            SELECT LEFT(p.fecha_desde, 10) AS desde,
                   LEFT(p.fecha_hasta, 10) AS hasta,
                   pi.cantidad
            FROM alquiler_items pi
            JOIN alquileres p ON p.id = pi.pedido_id
            WHERE pi.equipo_id = ?
              AND p.estado IN {ESTADOS}
              AND LEFT(p.fecha_desde, 10) <= ?
              AND LEFT(p.fecha_hasta, 10) > ?
        """, (id, last_day, first_day)).fetchall()

        # Via-kit reservations: this equipment is a component of a rented kit
        via_kit = conn.execute(f"""
            SELECT LEFT(p.fecha_desde, 10) AS desde,
                   LEFT(p.fecha_hasta, 10) AS hasta,
                   pi.cantidad * kc.cantidad AS cantidad
            FROM kit_componentes kc
            JOIN alquiler_items pi ON pi.equipo_id = kc.equipo_id
            JOIN alquileres p ON p.id = pi.pedido_id
            WHERE kc.componente_id = ?
              AND p.estado IN {ESTADOS}
              AND LEFT(p.fecha_desde, 10) <= ?
              AND LEFT(p.fecha_hasta, 10) > ?
        """, (id, last_day, first_day)).fetchall()

        reservations = [dict(r) for r in directas] + [dict(r) for r in via_kit]

        result: dict[str, int] = {}
        for day_num in range(1, days_in_month + 1):
            d_str    = _date(year, month, day_num).isoformat()
            reservado = sum(
                r["cantidad"]
                for r in reservations
                if r["desde"] <= d_str < r["hasta"]
            )
            result[d_str] = max(0, stock_total - reservado)

        return result
    finally:
        conn.close()


# ── Admin: enriquecimiento con IA (Firecrawl + Lovable AI) ────────────────────

class EnriquecerInput(BaseModel):
    nombre: Optional[str] = None
    marca:  Optional[str] = None
    modelo: Optional[str] = None
    url:    Optional[str] = None   # Si está presente, salta la búsqueda y scrapea esa URL directo


class BatchEnriquecerInput(BaseModel):
    # Hasta 3 equipo_ids por request (evita timeouts). El frontend re-batchea.
    # `max_length=50` defensivo: aunque solo procesamos los primeros 3, evita
    # que el body de la request crezca arbitrariamente (DoS por payload size).
    equipo_ids: list[int] = Field(..., min_length=1, max_length=50)


@router.post("/admin/equipos/batch-enriquecer")
def admin_batch_enriquecer(payload: BatchEnriquecerInput, request: Request):
    """
    Procesa un chunk de equipos: para cada uno, scrapea su bh_url y guarda el
    resultado en `equipo_fichas.raw_json` (cache). El admin después aplica los
    campos por sección con los botones ✨ del form V2.

    Límite: 3 equipos por request. El frontend re-batchea hasta terminar.
    Entre cada scrape duerme 1s para no rate-limitear B&H.

    NO sobrescribe campos no vacíos del equipo. Solo llena marca/modelo/foto_url
    si están vacíos. Specs y descripción siempre van al cache; el admin decide
    qué aplicar después.
    """
    require_admin(request)

    import time as _time, json as _json

    ids = payload.equipo_ids[:3]   # hard cap defensivo
    if not ids:
        return {"results": []}

    conn = get_db()
    results = []
    try:
        for eid in ids:
            eq = conn.execute("SELECT id, nombre, marca, modelo, foto_url, bh_url FROM equipos WHERE id=?", (eid,)).fetchone()
            if not eq:
                results.append({"equipo_id": eid, "status": "error", "error": "no existe"})
                continue
            eq_d = row_to_dict(eq)
            if not eq_d.get("bh_url"):
                results.append({"equipo_id": eid, "status": "skipped", "reason": "sin bh_url"})
                continue

            # Defense-in-depth: aunque bh_url ya pasó por validación cuando se guardó
            # el equipo, revalidamos antes de scrapear (impide SSRF a IPs privadas si
            # el equipo viene de una migración vieja o de un campo no validado).
            try:
                _validate_ssrf_only(eq_d["bh_url"])
            except HTTPException as he:
                results.append({"equipo_id": eid, "status": "error", "error": f"URL inválida: {he.detail}"[:200]})
                continue

            try:
                # Llamada interna al enriquecer. Pasamos el mismo `request` ya
                # validado — require_admin se ejecuta de nuevo (idempotente)
                # pero no hace daño y mantiene el endpoint protegido si se
                # llama directo.
                scrape = admin_enriquecer_equipo(
                    EnriquecerInput(url=eq_d["bh_url"]),
                    request,
                )

                # Persistir raw_json en equipo_fichas (cache para botones ✨)
                conn.execute(
                    """INSERT INTO equipo_fichas (equipo_id, raw_json, fuente_url, enriquecido_at)
                       VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT (equipo_id) DO UPDATE
                       SET raw_json = EXCLUDED.raw_json,
                           fuente_url = COALESCE(EXCLUDED.fuente_url, equipo_fichas.fuente_url),
                           enriquecido_at = EXCLUDED.enriquecido_at""",
                    (eid, _json.dumps(scrape, ensure_ascii=False), scrape.get("fuente_url") or eq_d["bh_url"]),
                )

                # Llenar campos top-level del equipo si están vacíos
                patch = {}
                if not eq_d.get("marca") and scrape.get("marca"):
                    patch["marca"] = scrape["marca"]
                if not eq_d.get("modelo") and scrape.get("modelo"):
                    patch["modelo"] = scrape["modelo"]
                if not eq_d.get("foto_url") and scrape.get("foto_url"):
                    patch["foto_url"] = scrape["foto_url"]
                if patch:
                    set_clause = ", ".join(f"{k} = ?" for k in patch)
                    set_clause += ", updated_at = CURRENT_TIMESTAMP"
                    conn.execute(
                        f"UPDATE equipos SET {set_clause} WHERE id = ?",
                        list(patch.values()) + [eid],
                    )

                conn.commit()
                results.append({
                    "equipo_id": eid,
                    "status": "ok",
                    "specs_count": len(scrape.get("specs") or []),
                    "filled": list(patch.keys()),
                })
            except HTTPException as he:
                # Errores HTTP del scrape: mostrar el detail (que ya está
                # sanitizado por el endpoint upstream).
                conn.rollback()
                results.append({"equipo_id": eid, "status": "error", "error": str(he.detail)[:200]})
            except Exception as e:
                # Errores no esperados: NO exponer str(e) al frontend (puede
                # contener paths/internals). Log completo server-side; al user
                # un mensaje genérico.
                conn.rollback()
                logger.exception("batch-enriquecer falló para equipo %s", eid)
                results.append({
                    "equipo_id": eid,
                    "status": "error",
                    "error": f"Error inesperado ({type(e).__name__})",
                })

            # Rate limit B&H — saltamos el sleep en la última iteración del
            # chunk para no demorar la respuesta gratis.
            if eid != ids[-1]:
                _time.sleep(1)

        return {"results": results}
    finally:
        conn.close()


@router.post("/admin/equipos/enriquecer")
def admin_enriquecer_equipo(payload: EnriquecerInput, request: Request):
    """
    Busca el equipo en B&H/Adorama, scrapea la página y usa Lovable AI para
    extraer marca/modelo/specs/foto en JSON estructurado. Devuelve un preview;
    el frontend decide qué campos aplicar via PATCH normal.
    """
    require_admin(request)

    import os, httpx

    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
    if not FIRECRAWL_API_KEY:
        raise HTTPException(500, "FIRECRAWL_API_KEY no configurado en el backend")

    direct_url = (payload.url or "").strip() or None
    if direct_url and not direct_url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "URL inválida (debe empezar con http:// o https://)")

    query = " ".join(x for x in [payload.marca, payload.nombre, payload.modelo] if x).strip()
    if not direct_url and not query:
        raise HTTPException(400, "Falta nombre/marca o url para enriquecer")

    # ── Specs guiados por template ─────────────────────────────────────────
    # Cargamos los specs definidos en `categoria_spec_templates` y los inyectamos
    # al prompt para que la IA use labels canónicos consistentes con nuestro modelo.
    # (Schema sigue siendo `specs: [{label,value}]` para mantener compat con el
    # migrador y los flujos viejos — solo guiamos al LLM con los labels esperados.)
    def _build_specs_guide() -> str:
        try:
            conn = get_db()
            try:
                rows = conn.execute("""
                    SELECT c.nombre AS categoria, t.label, t.tipo, t.unidad, t.enum_options, t.prioridad
                    FROM categoria_spec_templates t
                    JOIN categorias c ON c.id = t.categoria_id
                    ORDER BY c.prioridad NULLS LAST, c.nombre, t.prioridad NULLS LAST, t.label
                """).fetchall()
            finally:
                conn.close()
        except Exception:
            return ""

        if not rows:
            return ""

        # Agrupamos por categoría
        from collections import defaultdict
        by_cat: dict[str, list[str]] = defaultdict(list)
        for r in rows:
            r = row_to_dict(r) if not isinstance(r, dict) else r
            label = r.get("label") or ""
            tipo = r.get("tipo") or ""
            unidad = r.get("unidad") or ""
            enum_options = r.get("enum_options")
            hint = label
            if tipo == "enum" and enum_options:
                import json as _json
                try:
                    opts = enum_options if isinstance(enum_options, list) else _json.loads(enum_options)
                    if opts:
                        hint = f"{label} (uno de: {', '.join(map(str, opts[:8]))})"
                except Exception:
                    pass
            elif tipo == "number" and unidad:
                hint = f"{label} (numérico en {unidad})"
            elif tipo == "bool":
                hint = f"{label} (sí/no)"
            by_cat[r["categoria"]].append(hint)

        lines = ["LABELS CANÓNICOS DE SPECS POR CATEGORÍA — usá estos labels exactos cuando aplique:"]
        for cat, specs in by_cat.items():
            lines.append(f"  • {cat}: {' / '.join(specs)}.")
        lines.append(
            "Si el equipo no encaja en ninguna categoría, usá los labels más naturales. "
            "Para enums, devolvé exactamente uno de los valores listados (case-sensitive)."
        )
        return "\n".join(lines)

    specs_guide = _build_specs_guide()

    headers_fc = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type":  "application/json",
    }

    def _extract_results(j: dict) -> list[dict]:
        data = j.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("web", []) or []
        return []

    OFFICIAL_SITES = (
        "site:canon.com OR site:usa.canon.com OR site:sony.com OR site:nikon.com OR "
        "site:fujifilm.com OR site:fujifilm-x.com OR site:panasonic.com OR "
        "site:blackmagicdesign.com OR site:aputure.com OR site:godox.com OR "
        "site:rode.com OR site:sennheiser.com OR site:dji.com OR site:atomos.com OR "
        "site:tilta.com OR site:smallrig.com OR site:zoom-na.com OR site:zhiyun-tech.com"
    )

    def _search(q: str, client: "httpx.Client") -> list[dict]:
        try:
            rr = client.post(
                "https://api.firecrawl.dev/v2/search",
                headers=headers_fc,
                json={"query": q, "limit": 3},
            )
        except httpx.HTTPError:
            return []
        if rr.status_code != 200:
            return []
        return _extract_results(rr.json())

    def _first_valid(results: list[dict]) -> dict | None:
        for r in results:
            u = (r.get("url") or "").strip()
            if u.lower().startswith(("http://", "https://")) and not u.lower().endswith(".pdf"):
                return r
        return None

    json_format = {
        "type": "json",
        "prompt": (
            "Extraé información completa del equipo audiovisual (cámara, lente, "
            "luz, audio, soporte) desde la ficha de producto. "
            "Descripcion: 1-2 oraciones en español neutral. "
            "Specs: máximo 10, label corto y value conciso (ej. 'Sensor': 'Full-frame 24MP'). "
            "Keywords: 3-6 palabras clave cortas en español lowercase que describan la "
            "PERSONALIDAD/diferenciales del equipo (ej: 'bicolor', 'silenciosa', "
            "'v-mount', 'global shutter', 'weather sealed', 'cri 96', 'cine-ready'). "
            "Distintas y específicas — nada genérico como 'profesional' o 'calidad'. "
            "Peso: con unidad (ej '640g', '1.2kg'). "
            "Dimensiones: WxHxD con unidad (ej '129.7 x 77.8 x 84.5 mm'). "
            "Montura: nombre canónico (ej 'Sony E', 'Canon RF', 'EF', 'MFT', 'PL'). "
            "Formato: 'Full-frame' | 'APS-C' | 'MFT' | 'Super 35' | etc. para cámaras/lentes. "
            "Resolucion: para cámaras/monitores (ej '4K 120p', '6K Open Gate', '1080p'). "
            "Alimentacion: tipo de batería o fuente (ej 'NP-FZ100', 'V-mount', 'AC 220V', '2x AA'). "
            "Incluye: array de items que vienen en la caja (ej ['Cuerpo','Tapa','Cargador']). "
            "Conectividad: array de puertos (ej ['USB-C','HDMI Type-A','XLR x2','Mini-jack 3.5mm']). "
            "Compatible_con: array de etiquetas de compatibilidad (montura, formato, sistemas). "
            "Precio_usd: precio listado en USD si está visible (sólo número). "
            "Video_url: URL absoluta a un video YouTube de demo si aparece linkeado. "
            "Categoria_sugerida: una de ['Cámara','Lente','Iluminación','Audio','Soporte','Monitor','Accesorio']. "
            "Foto_urls: array con hasta 5 URLs ABSOLUTAS (http/https) de imágenes del producto, "
            "ordenadas de MÁS A MENOS relevante para el producto principal. "
            "Incluí ángulos distintos (frente, lateral, detalle) si están disponibles. "
            "JPG/PNG/WebP únicamente — NO uses placeholders, sprites, SVGs decorativos, "
            "tracking pixels, banners de categoría, fotos de productos relacionados, ni rutas relativas. "
            "Si no estás 100% seguro de que una URL existe y apunta al producto, NO la incluyas. "
            "Cualquier campo que no esté en la ficha → dejalo vacío. NO inventes."
            + ("\n\n" + specs_guide if specs_guide else "")
        ),
        "schema": {
            "type": "object",
            "properties": {
                "marca":  {"type": "string"},
                "modelo": {"type": "string"},
                "nombre_normalizado": {"type": "string"},
                "descripcion": {"type": "string"},
                "foto_urls": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                "specs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "value": {"type": "string"},
                        },
                        "required": ["label", "value"],
                    },
                },
                "keywords":          {"type": "array", "items": {"type": "string"}},
                "peso":              {"type": "string"},
                "dimensiones":       {"type": "string"},
                "montura":           {"type": "string"},
                "formato":           {"type": "string"},
                "resolucion":        {"type": "string"},
                "alimentacion":      {"type": "string"},
                "incluye":           {"type": "array", "items": {"type": "string"}},
                "conectividad":      {"type": "array", "items": {"type": "string"}},
                "compatible_con":    {"type": "array", "items": {"type": "string"}},
                "precio_usd":        {"type": "number"},
                "video_url":         {"type": "string"},
                "categoria_sugerida": {"type": "string"},
            },
            "required": ["marca", "modelo", "descripcion", "specs"],
        },
    }

    def _scrape(url: str, client: "httpx.Client") -> dict | None:
        """Devuelve {extracted, foto_candidates, meta} o None si falló.
        foto_candidates es una lista ordenada de URLs candidatas (LLM primero,
        luego og:image, twitter:image, dedupe).
        """
        try:
            rs = client.post(
                "https://api.firecrawl.dev/v2/scrape",
                headers=headers_fc,
                json={
                    "url": url,
                    "formats": ["markdown", json_format],
                    "onlyMainContent": True,
                },
            )
        except httpx.HTTPError:
            return None
        if rs.status_code == 402:
            raise HTTPException(402, "Sin créditos de Firecrawl. Recargá tu plan.")
        if rs.status_code == 429:
            raise HTTPException(429, "Rate-limit de Firecrawl. Probá en un minuto.")
        if rs.status_code != 200:
            return None
        sj = rs.json()
        sd = sj.get("data") or sj
        meta      = sd.get("metadata") or {}
        extracted = sd.get("json") or {}

        # Candidatos: LLM (array) primero (mejor ranking), después meta tags
        candidates: list[str] = []
        seen_lower: set[str] = set()

        def _push(u: str | None) -> None:
            if not u or not isinstance(u, str):
                return
            u = u.strip()
            if not u.lower().startswith(("http://", "https://")):
                return
            key = u.lower()
            if key in seen_lower:
                return
            seen_lower.add(key)
            candidates.append(u)

        # 1. LLM array (foto_urls) — orden de relevancia ya viene de la IA
        for u in (extracted.get("foto_urls") or []):
            _push(u)
        # 2. Backwards-compat: si vino foto_url scalar (esquema viejo)
        _push(extracted.get("foto_url"))
        # 3. Meta tags
        _push(meta.get("ogImage") or meta.get("og:image"))
        _push(meta.get("twitterImage") or meta.get("twitter:image"))

        return {
            "extracted": extracted,
            "foto_candidates": candidates[:MAX_PHOTO_CANDIDATES_PER_SCRAPE],
            "meta": meta,
            "source_url": url,   # URL original scrapeada (para trazabilidad)
        }

    with httpx.Client(timeout=45.0) as client:
        if direct_url:
            # Modo URL directa: scrape de esa página, sin búsqueda.
            # Si la URL es de B&H la tratamos como bh_top, sino como alt_top
            # (esto sólo afecta dónde queda el canonical_url y el labelling).
            from urllib.parse import urlparse as _up
            host = (_up(direct_url).hostname or "").lower()
            top_entry = {"url": direct_url, "title": direct_url}
            if "bhphotovideo" in host:
                bh_top, alt_top = top_entry, None
                bh_scrape, alt_scrape = _scrape(direct_url, client), None
            else:
                bh_top, alt_top = None, top_entry
                bh_scrape, alt_scrape = None, _scrape(direct_url, client)

            if bh_scrape is None and alt_scrape is None:
                raise HTTPException(422, "No se pudo scrapear la URL")
        else:
            # Etapa A: B&H (canónico para bh_url)
            bh_results = _search(f"{query} site:bhphotovideo.com", client)
            bh_top = _first_valid(bh_results)

            # Etapa B: sitios oficiales del fabricante
            alt_results = _search(f"{query} ({OFFICIAL_SITES})", client)
            alt_top = _first_valid(alt_results)

            # Etapa C: Adorama / Amazon (último recurso)
            if not alt_top:
                adoram_results = _search(f"{query} site:adorama.com OR site:amazon.com", client)
                alt_top = _first_valid(adoram_results)

            if not bh_top and not alt_top:
                raise HTTPException(404, "No se encontraron resultados en internet")

            bh_scrape  = _scrape(bh_top["url"], client) if bh_top else None
            alt_scrape = None
            # Sólo scrapeamos alternativa si B&H no aportó datos o foto
            needs_alt = (
                alt_top is not None and (
                    bh_scrape is None
                    or not bh_scrape.get("foto_candidates")
                    or not (bh_scrape.get("extracted") or {}).get("descripcion")
                )
            )
            if needs_alt:
                alt_scrape = _scrape(alt_top["url"], client)

    # ── Merge B&H + alt (B&H pisa, alt rellena gaps) ────────────────────────
    primary = bh_scrape or alt_scrape or {}
    secondary = alt_scrape if bh_scrape else None
    extracted = dict(primary.get("extracted") or {})
    _MERGE_KEYS = (
        "descripcion", "specs", "keywords", "marca", "modelo", "nombre_normalizado",
        "peso", "dimensiones", "montura", "formato", "resolucion", "alimentacion",
        "incluye", "conectividad", "compatible_con", "precio_usd", "video_url",
        "categoria_sugerida",
    )
    if secondary:
        sec_ext = secondary.get("extracted") or {}
        for k in _MERGE_KEYS:
            if not extracted.get(k):
                extracted[k] = sec_ext.get(k)

    # `not {}` es True, pero `not {"a": None}` es False — necesitamos también
    # rechazar dicts donde todos los valores son falsy/vacíos (caso real:
    # Firecrawl devuelve el schema con todas las keys pero todas en None).
    if not extracted or not any(extracted.values()):
        raise HTTPException(422, "No se pudo extraer información estructurada")

    # ── Validación de foto: HEAD/GET parcial antes de devolver ──────────────
    def _validate_image(url: str | None) -> tuple[bool, str]:
        """Devuelve (ok, motivo). motivo es '' si ok=True."""
        if not url:
            return False, "sin candidata"
        if not url.lower().startswith(("http://", "https://")):
            return False, "URL no absoluta"
        from urllib.parse import urlparse as _up
        host = (_up(url).hostname or "").lower()
        ref = f"https://{host}/" if host else None
        hdrs = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if ref:
            hdrs["Referer"] = ref
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as c:
                # HEAD primero
                try:
                    rh = c.head(url, headers=hdrs)
                    if rh.status_code == 200:
                        ct = rh.headers.get("content-type", "")
                        cl = int(rh.headers.get("content-length", "0") or "0")
                        if ct.startswith("image/") and (cl == 0 or cl > 1024):
                            return True, ""
                        if not ct.startswith("image/"):
                            return False, f"content-type {ct or 'desconocido'}"
                        if cl and cl <= 1024:
                            return False, "imagen muy chica (<1KB)"
                except httpx.HTTPError:
                    pass
                # GET con Range como fallback (HEAD a veces no está soportado)
                hdrs["Range"] = "bytes=0-2048"
                rg = c.get(url, headers=hdrs)
                if rg.status_code in (200, 206):
                    ct = rg.headers.get("content-type", "")
                    if ct.startswith("image/"):
                        return True, ""
                    return False, f"content-type {ct or 'desconocido'}"
                return False, f"HTTP {rg.status_code} en origen"
        except httpx.HTTPError as e:
            return False, f"error de red: {type(e).__name__}"

    # Juntar todos los candidatos: B&H primero, después alt (sin dedupe-cross,
    # se dedupe cuando los unimos)
    bh_cands  = (bh_scrape or {}).get("foto_candidates") or []
    alt_cands = (alt_scrape or {}).get("foto_candidates") or []

    # Si alt no se scrapeó pero existe URL, scrape ahora para sumar candidatos
    if not alt_scrape and alt_top:
        try:
            with httpx.Client(timeout=45.0) as c2:
                alt_scrape = _scrape(alt_top["url"], c2)
            alt_cands = (alt_scrape or {}).get("foto_candidates") or []
        except Exception:
            pass

    all_candidates: list[str] = []
    seen_lc: set[str] = set()
    for u in (bh_cands + alt_cands):
        k = u.lower()
        if k in seen_lc:
            continue
        seen_lc.add(k)
        all_candidates.append(u)

    # Validar cada candidato (HEAD/GET); guardar los que pasen + motivo de los que no
    foto_validas: list[str] = []
    foto_invalidas: list[dict] = []
    for u in all_candidates[:MAX_PHOTO_CANDIDATES_TO_VALIDATE]:
        ok, motivo = _validate_image(u)
        if ok:
            foto_validas.append(u)
        else:
            foto_invalidas.append({"url": u, "motivo": motivo})

    foto_url = foto_validas[0] if foto_validas else None
    fuente_foto_url = (bh_top or alt_top or {}).get("url") if foto_url else None
    foto_motivo = ""
    if not foto_url:
        if foto_invalidas:
            foto_motivo = " | ".join(f"{(d['motivo'] or 'inválida')}" for d in foto_invalidas[:3])
        else:
            foto_motivo = "no se encontró imagen en ninguna fuente"

    # bh_url canónico = el de B&H si hubo, sino el alternativo (como referencia)
    canonical_url = (bh_top or alt_top)["url"]
    canonical_title = (bh_top or alt_top).get("title") or canonical_url

    # Sanitizar keywords: lowercase, trim, dedupe, max 6
    raw_kws = extracted.get("keywords") or []
    seen_kw: set[str] = set()
    keywords: list[str] = []
    for k in raw_kws:
        if not isinstance(k, str):
            continue
        kk = k.strip().lower()
        if not kk or kk in seen_kw or len(kk) > 40:
            continue
        seen_kw.add(kk)
        keywords.append(kk)
        if len(keywords) >= 6:
            break

    # ── Sanitización de listas de strings ──────────────────────────────────
    def _clean_str_list(raw, max_items: int = 12, max_len: int = 80) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        if not isinstance(raw, list):
            return out
        for v in raw:
            if not isinstance(v, str):
                continue
            s = v.strip()
            if not s or len(s) > max_len or s.lower() in seen:
                continue
            seen.add(s.lower())
            out.append(s)
            if len(out) >= max_items:
                break
        return out

    incluye        = _clean_str_list(extracted.get("incluye"),        max_items=15)
    conectividad   = _clean_str_list(extracted.get("conectividad"),   max_items=10)
    compatible_con = _clean_str_list(extracted.get("compatible_con"), max_items=8)

    # video_url: validar http(s), nada de javascript: ni rutas relativas
    video_url = extracted.get("video_url")
    if isinstance(video_url, str) and not video_url.lower().startswith(("http://", "https://")):
        video_url = None

    # precio_usd: aceptar número o string numérico, sino None
    precio_bh_usd = None
    raw_precio = extracted.get("precio_usd")
    if isinstance(raw_precio, (int, float)) and raw_precio > 0:
        precio_bh_usd = float(raw_precio)
    elif isinstance(raw_precio, str):
        try:
            v = float(raw_precio.replace(",", "").replace("$", "").strip())
            if v > 0:
                precio_bh_usd = v
        except ValueError:
            pass

    # Trazabilidad: distinguir de qué tipo de fuente vino la data ayuda a
    # debuggear "¿por qué este equipo tiene esta info rara?". Antes era
    # genérico ("firecrawl" para todo lo no-B&H), ahora distinguimos
    # bh / adorama / amazon / manufacturer / generic.
    def _fuente_for(scrape: dict | None) -> str | None:
        if not scrape:
            return None
        from urllib.parse import urlparse as _up
        url = scrape.get("source_url") or (scrape.get("meta") or {}).get("sourceURL") or ""
        host = (_up(url).hostname or "").lower()
        if "bhphotovideo.com" in host:
            return "firecrawl-bh"
        if "adorama.com" in host:
            return "firecrawl-adorama"
        if "amazon." in host:
            return "firecrawl-amazon"
        if host:
            return "firecrawl-manufacturer"
        return "firecrawl"

    fuente_de_enriquecimiento = (
        _fuente_for(bh_scrape) or _fuente_for(alt_scrape) or "firecrawl"
    )

    return {
        "marca":  (extracted.get("marca")  or payload.marca  or "").strip() or None,
        "modelo": (extracted.get("modelo") or payload.modelo or "").strip() or None,
        "nombre_normalizado": (extracted.get("nombre_normalizado") or payload.nombre or "").strip() or None,
        "descripcion": (extracted.get("descripcion") or "").strip(),
        "specs": (extracted.get("specs") or [])[:12],
        "keywords": keywords,
        "foto_url": foto_url,
        "foto_candidates": foto_validas,  # todas las URLs válidas (la primera es la elegida por defecto)
        # Ficha técnica extendida
        "peso":           (extracted.get("peso") or "").strip() or None,
        "dimensiones":    (extracted.get("dimensiones") or "").strip() or None,
        "montura":        (extracted.get("montura") or "").strip() or None,
        "formato":        (extracted.get("formato") or "").strip() or None,
        "resolucion":     (extracted.get("resolucion") or "").strip() or None,
        "alimentacion":   (extracted.get("alimentacion") or "").strip() or None,
        "incluye":        incluye,
        "conectividad":   conectividad,
        "compatible_con": compatible_con,
        "video_url":      video_url,
        "precio_bh_usd":  precio_bh_usd,
        "categoria_sugerida": (extracted.get("categoria_sugerida") or "").strip() or None,
        # Trazabilidad
        "fuente_url":      canonical_url,
        "fuente_titulo":   canonical_title,
        "fuente_foto_url": fuente_foto_url,
        "foto_motivo":     foto_motivo or None,
        "enriquecido_fuente": fuente_de_enriquecimiento,
        # Raw para guardar tal cual (preserva todo lo que la IA devolvió)
        "raw": extracted,
    }


# ── Admin: búsqueda dedicada de fotos (separada del enriquecimiento) ─────────
#
# El enriquecedor general usa B&H/Adorama (mejor para specs) pero esos sitios
# bloquean hotlinking de fotos. Este endpoint busca específicamente en sitios
# con imágenes confiables (Wikipedia, manufacturer, sitios de review).

class BuscarFotosInput(BaseModel):
    nombre: Optional[str]      = None
    marca:  Optional[str]      = None
    modelo: Optional[str]      = None
    url:    Optional[str]      = None
    exclude: Optional[list[str]] = None  # URLs ya conocidas (para "buscar más")


@router.post("/admin/equipos/buscar-fotos")
def admin_buscar_fotos(payload: BuscarFotosInput, request: Request):
    """Busca fotos del equipo en fuentes optimizadas para imágenes (Wikipedia,
    manufacturer oficial, review sites). Devuelve lista validada de candidatos."""
    require_admin(request)

    import httpx
    import re

    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
    if not FIRECRAWL_API_KEY:
        raise HTTPException(500, "FIRECRAWL_API_KEY no configurado")

    direct_url = (payload.url or "").strip() or None
    if direct_url and not direct_url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "URL inválida")

    query = " ".join(x for x in [payload.marca, payload.nombre, payload.modelo] if x).strip()
    if not direct_url and not query:
        raise HTTPException(400, "Falta nombre/marca o url")

    exclude_lc: set[str] = {(u or "").strip().lower() for u in (payload.exclude or [])}

    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type":  "application/json",
    }

    # Queries optimizados para fotos de producto con fondo blanco/neutro,
    # bien iluminadas — ideal para equipos audiovisuales de renta.
    # B&H primero: hero shots standarizados sobre fondo gris/blanco.
    PHOTO_QUERIES = [
        # 1. B&H Photo: fotos hero de producto, alta resolución, fondo neutro
        f"{query} product photo site:bhphotovideo.com",
        # 2. Adorama / KEH: misma categoría de retailers
        f"{query} product image (site:adorama.com OR site:keh.com)",
        # 3. Manufacturer oficial — página de producto
        f"{query} product page (site:canon.com OR site:usa.canon.com OR site:sony.com OR site:nikon.com OR "
        f"site:fujifilm.com OR site:panasonic.com OR site:blackmagicdesign.com OR site:aputure.com OR "
        f"site:godox.com OR site:rode.com OR site:sennheiser.com OR site:dji.com OR site:atomos.com OR "
        f"site:tilta.com OR site:smallrig.com OR site:saramonic.com OR site:zoom-na.com)",
        # 4. Wikipedia: fallback con imágenes limpias y sin paywall
        f"{query} (site:en.wikipedia.org OR site:commons.wikimedia.org OR site:es.wikipedia.org)",
    ]

    def _fc_search(q: str, client) -> list[str]:
        try:
            r = client.post(
                "https://api.firecrawl.dev/v2/search",
                headers=headers,
                json={"query": q, "limit": 3},
            )
        except httpx.HTTPError:
            return []
        if r.status_code != 200:
            return []
        data = r.json().get("data")
        rows = data if isinstance(data, list) else (data.get("web") if isinstance(data, dict) else None) or []
        urls = []
        for row in rows:
            u = (row.get("url") or "").strip() if isinstance(row, dict) else ""
            if u.lower().startswith(("http://", "https://")) and not u.lower().endswith(".pdf"):
                urls.append(u)
        return urls

    def _extract_images_from_page(url: str, client, trust_url: bool = False) -> list[str]:
        """Scrapea una página y extrae URLs de imagen (meta + markdown img tags).
        Si trust_url=True (cuando el usuario pega el link explícitamente), no
        descarta candidatos por dimensiones pequeñas en la URL — solo filtra
        patrones obvios de basura (thumbs, iconos, logos)."""
        try:
            r = client.post(
                "https://api.firecrawl.dev/v2/scrape",
                headers=headers,
                json={"url": url, "formats": ["markdown"], "onlyMainContent": False},
            )
        except httpx.HTTPError:
            return []
        if r.status_code != 200:
            return []
        sd = r.json().get("data") or {}
        meta = sd.get("metadata") or {}
        markdown = sd.get("markdown") or ""

        cands: list[str] = []
        seen: set[str] = set()

        def push(u: str | None) -> None:
            if not u or not isinstance(u, str):
                return
            u = u.strip()
            if not u.lower().startswith(("http://", "https://")):
                return
            # Filtrar tracking pixels y svgs decorativos
            if u.lower().endswith(".svg"):
                return
            lo = u.lower()
            # Filtrar thumbnails, iconos, logos y dimensiones pequeñas en la URL.
            # Patrones comunes que indican imagen de baja calidad:
            #   _thumb, -thumb, /thumbs/, _small, _sm, /icons/, /logos/,
            #   width=NN (≤200), w=NN (≤200), -100x100, _50x50, etc.
            LOW_QUALITY_PATTERNS = (
                "/thumb", "_thumb", "-thumb", "/thumbs/", "thumbnail",
                "/icon", "_icon", "-icon",
                "/logo", "_logo", "-logo", "favicon",
                "/avatar", "_avatar", "-avatar",
                "/sprite", "spacer.gif", "pixel.gif",
                "_sm.", "-sm.", "_small.", "-small.",
            )
            if any(p in lo for p in LOW_QUALITY_PATTERNS):
                return
            if not trust_url:
                # Dimensiones pequeñas en URL: -100x100, _50x50, 200x150
                import re as _re
                m = _re.search(r"[-_/](\d{2,4})x(\d{2,4})", lo)
                if m:
                    w, h = int(m.group(1)), int(m.group(2))
                    if w < 800 or h < 800:
                        return
                # width=NN o w=NN <= 300 en query string
                m = _re.search(r"[?&](?:width|w|size)=(\d+)", lo)
                if m and int(m.group(1)) < 800:
                    return
            k = lo
            if k in seen or k in exclude_lc:
                return
            seen.add(k)
            cands.append(u)

        push(meta.get("ogImage") or meta.get("og:image"))
        push(meta.get("twitterImage") or meta.get("twitter:image"))
        # ![alt](url) en markdown
        for m in re.finditer(r"!\[[^\]]*\]\(([^)\s]+)", markdown):
            push(m.group(1))
        # <img src="..."> en HTML embebido
        for m in re.finditer(r'<img[^>]+src=["\']?([^"\'>\s]+)', markdown):
            push(m.group(1))

        # Ordenar: primero URLs con indicadores de foto de producto (fondo blanco/hero)
        PRODUCT_INDICATORS = (
            "/product/", "_hero", "-hero", "_main", "-main",
            "-product-", "/images/", "bhphotovideo.com",
            "_front", "-front", "_top", "-top",
        )
        def _product_score(u: str) -> int:
            lo = u.lower()
            return sum(1 for p in PRODUCT_INDICATORS if p in lo)

        cands.sort(key=_product_score, reverse=True)
        return cands[:10]

    # Validación rápida: HEAD/GET parcial, descarta lo que no sea imagen real
    def _is_valid_image(url: str, client) -> bool:
        try:
            from urllib.parse import urlparse as _up
            host = (_up(url).hostname or "").lower()
            hdrs = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
                "Referer": f"https://{host}/" if host else "",
            }
            try:
                rh = client.head(url, headers=hdrs, follow_redirects=True, timeout=8.0)
                if rh.status_code == 200:
                    ct = rh.headers.get("content-type", "")
                    cl = int(rh.headers.get("content-length", "0") or "0")
                    if ct.startswith("image/") and (cl == 0 or cl > 1024):
                        return True
            except httpx.HTTPError:
                pass
            # Fallback con Range
            hdrs["Range"] = "bytes=0-2048"
            rg = client.get(url, headers=hdrs, follow_redirects=True, timeout=8.0)
            if rg.status_code in (200, 206):
                ct = rg.headers.get("content-type", "")
                if ct.startswith("image/"):
                    return True
        except httpx.HTTPError:
            pass
        return False

    def _og_images_from_html(url: str, client) -> list[str]:
        """Extrae og:image y twitter:image directamente del HTML sin Firecrawl.
        Más rápido y confiable para páginas de producto de B&H y similares."""
        try:
            r = client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=15.0,
                follow_redirects=True,
            )
        except httpx.HTTPError:
            return []
        if r.status_code != 200:
            return []
        html = r.text[:100_000]
        imgs: list[str] = []
        seen: set[str] = set()
        def _push_og(u: str | None) -> None:
            if not u:
                return
            u = u.strip()
            if u.lower().startswith(("http://", "https://")) and u.lower() not in seen:
                seen.add(u.lower())
                imgs.append(u)
        # og:image (dos posibles órdenes de atributos)
        for pat in [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'og:image["\'][^>]*content=["\']([^"\']+)["\']',
        ]:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                _push_og(m.group(1))
                break
        # twitter:image
        for pat in [
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
        ]:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                _push_og(m.group(1))
                break
        return imgs

    all_cands: list[str] = []
    seen_lc: set[str] = set()
    # Cuando el usuario pegó una URL directa, marcamos las fotos obtenidas para
    # saltear la validación HEAD (B&H CDN puede rechazar HEADs cross-origin).
    direct_url_cands: set[str] = set()

    with httpx.Client(timeout=45.0) as client:
        if direct_url:
            # 1) Si la URL es directamente una imagen, usarla tal cual.
            if direct_url.lower().rsplit(".", 1)[-1] in ("jpg", "jpeg", "png", "webp", "avif", "gif"):
                all_cands.append(direct_url)
                seen_lc.add(direct_url.lower())
                direct_url_cands.add(direct_url.lower())

            # 2) Extraer og:image directamente del HTML (rápido, sin Firecrawl).
            #    Más confiable para B&H y sitios JS-pesados.
            for u in _og_images_from_html(direct_url, client):
                if u.lower() not in seen_lc:
                    seen_lc.add(u.lower())
                    all_cands.append(u)
                    direct_url_cands.add(u.lower())

            # 3) Firecrawl para más candidatos (especialmente imgs del body).
            for u in _extract_images_from_page(direct_url, client, trust_url=True):
                if u.lower() not in seen_lc:
                    seen_lc.add(u.lower())
                    all_cands.append(u)
        else:
            for q in PHOTO_QUERIES:
                if len(all_cands) >= 18:
                    break
                for top in _fc_search(q, client)[:2]:
                    for u in _extract_images_from_page(top, client):
                        if u.lower() not in seen_lc:
                            seen_lc.add(u.lower())
                            all_cands.append(u)

        # Validar candidatos — los que vienen de URL directa se saltan la
        # validación (B&H CDN rechaza HEADs cross-origin; el og:image del propio
        # sitio es confiable sin necesidad de un round-trip extra).
        with httpx.Client(timeout=10.0) as vc:
            validated = [
                u for u in all_cands[:MAX_PHOTO_CANDIDATES_BUSCAR_VALIDATE]
                if u.lower() in direct_url_cands or _is_valid_image(u, vc)
            ][:MAX_PHOTO_CANDIDATES_BUSCAR_RETURN]

    return {"foto_candidates": validated, "total_inspeccionadas": len(all_cands)}


# ── Admin: aplicar resultado de enriquecimiento en una sola llamada ──────────
#
# El frontend manda el preview (parcial o completo) + flags "apply_*" para
# decidir qué piezas grabar. Esto evita N round-trips PATCH equipo + PUT ficha.

class AplicarEnriquecimientoInput(BaseModel):
    # Núcleo equipo
    marca:    Optional[str]   = None
    modelo:   Optional[str]   = None
    foto_url: Optional[str]   = None
    bh_url:   Optional[str]   = None
    # Ficha
    descripcion:   Optional[str] = None
    specs:         Optional[list[dict]] = None
    keywords:      Optional[list[str]]  = None
    peso:          Optional[str]   = None
    dimensiones:   Optional[str]   = None
    montura:       Optional[str]   = None
    formato:       Optional[str]   = None
    resolucion:    Optional[str]   = None
    alimentacion:  Optional[str]   = None
    incluye:        Optional[list[str]] = None
    conectividad:   Optional[list[str]] = None
    compatible_con: Optional[list[str]] = None
    video_url:     Optional[str]   = None
    precio_bh_usd: Optional[float] = None
    fuente_url:    Optional[str]   = None
    fuente_titulo: Optional[str]   = None
    raw:           Optional[dict]  = None
    enriquecido_fuente: Optional[str] = None


@router.post("/admin/equipos/{id}/aplicar-enriquecimiento")
def admin_aplicar_enriquecimiento(id: int, payload: AplicarEnriquecimientoInput, request: Request):
    """
    Toma el resultado del endpoint /enriquecer (parcial o completo) y graba
    en una sola transacción los campos que el cliente decidió aplicar.
    Cualquier campo NO incluido en el body queda como está (no se nullea).
    """
    require_admin(request)

    import json as _json

    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM equipos WHERE id=?", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")

        body = payload.model_dump(exclude_unset=True)

        # ── Equipos (núcleo) ────────────────────────────────────────────
        eq_fields = {}
        for k in ("marca", "modelo", "foto_url", "bh_url"):
            if k in body and body[k] is not None:
                eq_fields[k] = body[k]
        if eq_fields:
            set_clause = ", ".join(f"{k} = ?" for k in eq_fields)
            set_clause += ", updated_at = CURRENT_TIMESTAMP"
            conn.execute(
                f"UPDATE equipos SET {set_clause} WHERE id = ?",
                list(eq_fields.values()) + [id],
            )

        # ── Ficha (asegurar fila) ───────────────────────────────────────
        conn.execute(
            "INSERT INTO equipo_fichas (equipo_id) VALUES (?) ON CONFLICT(equipo_id) DO NOTHING",
            (id,),
        )

        # Mapeo: API → columna DB. Listas/dicts → JSON string.
        ficha_fields: dict = {}
        if "descripcion" in body:
            ficha_fields["descripcion"] = body["descripcion"]
        if "specs" in body and body["specs"] is not None:
            ficha_fields["specs_json"] = _json.dumps(body["specs"], ensure_ascii=False)
        if "keywords" in body and body["keywords"] is not None:
            ficha_fields["keywords_json"] = _json.dumps(body["keywords"], ensure_ascii=False)
        if "incluye" in body and body["incluye"] is not None:
            ficha_fields["incluye_json"] = _json.dumps(body["incluye"], ensure_ascii=False)
        if "conectividad" in body and body["conectividad"] is not None:
            ficha_fields["conectividad_json"] = _json.dumps(body["conectividad"], ensure_ascii=False)
        if "compatible_con" in body and body["compatible_con"] is not None:
            ficha_fields["compatible_con_json"] = _json.dumps(body["compatible_con"], ensure_ascii=False)
        for k in ("peso", "dimensiones", "montura", "formato", "resolucion",
                  "alimentacion", "video_url", "precio_bh_usd",
                  "fuente_url", "fuente_titulo", "enriquecido_fuente"):
            if k in body:
                ficha_fields[k] = body[k]
        if "raw" in body and body["raw"] is not None:
            ficha_fields["raw_json"] = _json.dumps(body["raw"], ensure_ascii=False)

        # Si vino algún dato de ficha, marcar enriquecido_at
        if ficha_fields:
            ficha_fields["enriquecido_at"] = datetime.datetime.utcnow().isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in ficha_fields)
            set_clause += ", updated_at = CURRENT_TIMESTAMP"
            conn.execute(
                f"UPDATE equipo_fichas SET {set_clause} WHERE equipo_id = ?",
                list(ficha_fields.values()) + [id],
            )

        conn.commit()

        # Devolver equipo + ficha actualizados
        eq_row = conn.execute("SELECT * FROM equipos WHERE id = ?", (id,)).fetchone()
        ficha_row = conn.execute("SELECT * FROM equipo_fichas WHERE equipo_id = ?", (id,)).fetchone()
        return {
            "equipo": row_to_dict(eq_row),
            "ficha":  row_to_dict(ficha_row) if ficha_row else None,
        }
    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Admin: descargar imagen externa y subirla a Cloudflare R2 ────────────────
#
# El frontend NO sube directamente al bucket porque eso requeriría exponer
# credenciales de R2 al browser. Acá lo hacemos en el backend con el secret
# guardado en env vars.
#
# SSRF guard
# ----------
# El admin autenticado puede pedir descargar cualquier URL externa. Sin
# allowlist, esto sería SSRF: un admin malicioso/comprometido podría hacer
# que el backend descargue http://localhost:5432/, http://169.254.169.254/
# (metadata cloud), o cualquier IP de la VPC interna de Railway. Filtramos:
# (1) sólo http(s) en puerto estándar (80/443), (2) host en allowlist de
# dominios conocidos, (3) la IP resuelta del host no es privada/loopback.

_ALLOWED_PHOTO_HOSTS = frozenset([
    # Retailers
    "bhphotovideo.com", "adorama.com", "amazon.com", "amazon.ca",
    "amazonaws.com",
    # Wikipedia / commons
    "wikimedia.org", "wikipedia.org",
    # Reviews / press
    "dpreview.com", "fstoppers.com", "petapixel.com", "cinema5d.com",
    # Manufacturer (cámaras, lentes, audio, video, iluminación, soportes)
    "sony.com", "sonycreativesoftware.com",
    "canon.com", "usa.canon.com", "canon-europe.com",
    "nikon.com", "nikonusa.com",
    "fujifilm.com", "fujifilm-x.com",
    "panasonic.com",
    "blackmagicdesign.com", "red.com", "atomos.com",
    "tilta.com", "smallrig.com", "manfrotto.com",
    "saramonic.com", "rode.com", "shure.com", "sennheiser.com",
    "sigmaphoto.com", "tamron.com", "samyangopticsamericas.com",
    "leofoto.com", "godox.com", "aputure.com", "nanlite.com",
    "zhiyun-tech.com", "dji.com", "insta360.com", "gopro.com",
    # CDNs comunes que sirven assets de los hosts de arriba
    "cloudfront.net", "akamaized.net", "akamaihd.net",
    "shopifycdn.com", "wp.com", "googleusercontent.com",
])


def _is_photo_host_allowed(host: str) -> bool:
    """True si `host` es un dominio del allowlist o subdominio de uno."""
    host = (host or "").lower().rstrip(".")
    return any(host == h or host.endswith("." + h) for h in _ALLOWED_PHOTO_HOSTS)


def _host_resolves_to_private(host: str) -> bool:
    """True si el host resuelve a alguna IP privada/loopback/link-local/
    multicast/reserved. Defense-in-depth: bloquea el caso (improbable pero
    posible) de un dominio del allowlist apuntando a IPs internas.
    """
    import ipaddress as _ip
    import socket as _socket
    try:
        infos = _socket.getaddrinfo(host, None)
    except (_socket.gaierror, OSError):
        return True   # No resolver → no descargar
    for info in infos:
        addr = info[4][0]
        try:
            ip = _ip.ip_address(addr)
            if (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
                return True
        except ValueError:
            continue
    return False


def _validate_ssrf_only(url: str) -> None:
    """Anti-SSRF sin whitelist de dominios. Usado cuando el admin selecciona
    manualmente una URL (no batch import). Protege contra IPs privadas/loopback
    pero no restringe el dominio."""
    from urllib.parse import urlparse as _urlparse
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "URL inválida — sólo http/https")
    parsed = _urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        raise HTTPException(400, "URL inválida — host vacío")
    port = parsed.port
    if port and port not in (80, 443):
        raise HTTPException(400, f"Puerto no permitido: {port}")
    if _host_resolves_to_private(host):
        raise HTTPException(403, f"Host '{host}' resuelve a IP privada/interna")


def _validate_external_image_url(url: str) -> None:
    """Anti-SSRF con whitelist de dominios. Eleva HTTPException si la URL no es segura."""
    from urllib.parse import urlparse as _urlparse
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "URL inválida — sólo http/https")
    parsed = _urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        raise HTTPException(400, "URL inválida — host vacío")
    port = parsed.port
    if port and port not in (80, 443):
        raise HTTPException(400, f"Puerto no permitido: {port}")
    if not _is_photo_host_allowed(host):
        raise HTTPException(
            403,
            f"Host no permitido para descarga: {host}. Si es un sitio "
            "legítimo, agregar a _ALLOWED_PHOTO_HOSTS.",
        )
    if _host_resolves_to_private(host):
        raise HTTPException(403, f"Host '{host}' resuelve a IP privada/interna")


def _download_image_bytes(url: str) -> tuple[bytes, str]:
    """Descarga una imagen externa con todos los fallbacks del proxy
    (Referer del host, sin Referer, Referer=google, weserv).
    Devuelve (bytes, content_type). Eleva HTTPException si no se pudo.

    NOTA: el caller debe haber pasado `url` por `_validate_external_image_url`
    antes (SSRF guard). Acá hacemos una validación final por las dudas.
    """
    import httpx
    from urllib.parse import urlparse, quote

    _validate_external_image_url(url)
    host = (urlparse(url).hostname or "").lower()

    def _headers(referer: str | None) -> dict:
        h = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Fetch-Dest": "image",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "cross-site",
            "Cache-Control": "no-cache",
        }
        if referer:
            h["Referer"] = referer
        return h

    referer_map = {
        "bhphotovideo.com": "https://www.bhphotovideo.com/",
        "www.bhphotovideo.com": "https://www.bhphotovideo.com/",
        "adorama.com": "https://www.adorama.com/",
        "www.adorama.com": "https://www.adorama.com/",
    }
    primary_referer = next(
        (v for k, v in referer_map.items() if host.endswith(k)),
        f"https://{host}/",
    )

    last_status = None
    last_body = b""
    r = None
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True, http2=False, max_redirects=3) as client:
            r = client.get(url, headers=_headers(primary_referer))
            last_status, last_body = r.status_code, r.content
            if r.status_code == 403:
                r2 = client.get(url, headers=_headers(None))
                if r2.status_code == 200:
                    r = r2
                else:
                    last_status, last_body = r2.status_code, r2.content
            if r.status_code == 403:
                r3 = client.get(url, headers=_headers("https://www.google.com/"))
                if r3.status_code == 200:
                    r = r3
                else:
                    last_status, last_body = r3.status_code, r3.content
            if r.status_code in (401, 403, 404, 429) or r.status_code >= 500:
                stripped = url.split("://", 1)[1] if "://" in url else url
                weserv_url = f"https://images.weserv.nl/?url={quote(stripped, safe='')}"
                r4 = client.get(weserv_url, headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "image/*,*/*;q=0.8",
                })
                if r4.status_code == 200 and r4.headers.get("content-type", "").startswith("image/"):
                    r = r4
                else:
                    last_status, last_body = r4.status_code, r4.content
    except httpx.HTTPError as e:
        raise HTTPException(502, f"No se pudo descargar la imagen: {e}")

    if r is None or r.status_code != 200:
        snippet = ""
        try:
            snippet = last_body[:200].decode("utf-8", errors="ignore")
        except Exception:
            pass
        raise HTTPException(
            502,
            f"Origen devolvió {last_status} para host {host}. {snippet}".strip(),
        )

    ctype = r.headers.get("content-type", "image/jpeg")
    if not ctype.startswith("image/"):
        raise HTTPException(415, f"La URL no devolvió una imagen ({ctype})")

    if len(r.content) < 1024:
        raise HTTPException(415, f"Imagen muy chica ({len(r.content)} bytes)")

    return r.content, ctype


def _ext_from_ctype(ct: str) -> str:
    ct = (ct or "").lower()
    if "png" in ct:  return "png"
    if "webp" in ct: return "webp"
    if "avif" in ct: return "avif"
    if "gif" in ct:  return "gif"
    return "jpg"


def _trim_and_square(img, padding_pct: float = 0.06):
    """Recorta bordes (transparentes o casi blancos) y empareja a cuadrado
    con fondo blanco + padding. Sirve para que productos con mucho whitespace
    queden visualmente del mismo tamaño que productos con poco whitespace.

    Args:
        img: PIL.Image (RGB o RGBA)
        padding_pct: porcentaje de padding alrededor del bbox encontrado.
                     0.06 = 6% del lado más largo.
    Returns:
        PIL.Image en modo RGB cuadrado con fondo blanco.
    """
    from PIL import Image, ImageChops

    # 1) Encontrar el bbox del contenido
    if img.mode == "RGBA":
        # Bbox por canal alpha — funciona perfecto con PNG transparente
        bbox = img.split()[-1].getbbox()
        if bbox:
            img = img.crop(bbox)
        img_rgb = Image.new("RGB", img.size, (255, 255, 255))
        img_rgb.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = img_rgb
    else:
        img = img.convert("RGB")
        # Bbox por diferencia con un fondo blanco — captura productos sobre fondo blanco
        bg = Image.new("RGB", img.size, (255, 255, 255))
        diff = ImageChops.difference(img, bg)
        # Reducir ruido (compresión JPEG deja píxeles "casi blancos")
        diff = ImageChops.add(diff, diff, 2.0, -30)
        bbox = diff.getbbox()
        if bbox:
            img = img.crop(bbox)

    # 2) Hacer cuadrado: pegar centrado en un canvas blanco más grande
    w, h = img.size
    side = max(w, h)
    pad = int(side * padding_pct)
    canvas_side = side + 2 * pad
    canvas = Image.new("RGB", (canvas_side, canvas_side), (255, 255, 255))
    offset = ((canvas_side - w) // 2, (canvas_side - h) // 2)
    canvas.paste(img, offset)
    return canvas


def _optimize_image(content: bytes) -> tuple[bytes, str, int, int]:
    """Optimiza la imagen: auto-orient + trim de bordes + cuadrado con fondo
    blanco + resize a 1200x1200 + WebP q=85. Devuelve (bytes, ct, w, h).
    Si algo falla, devuelve el contenido original como fallback.

    El trim+cuadrado normaliza el tamaño visual de los productos en el grid:
    sin esto, los PNG con mucho whitespace alrededor se ven chicos comparados
    con los que llenan el frame.
    """
    try:
        from PIL import Image, ImageOps
        from io import BytesIO
    except ImportError:
        return content, "image/jpeg", 0, 0

    try:
        img = Image.open(BytesIO(content))
        img = ImageOps.exif_transpose(img)  # auto-orient

        # Normalizar a RGBA o RGB según corresponda (preservamos transparencia en PNG)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.mode else "RGB")

        # Trim + cuadrado con fondo blanco (#8 — tamaños inconsistentes)
        try:
            img = _trim_and_square(img, padding_pct=0.06)
        except Exception as e:
            logger.warning("optimize_image: trim_and_square falló, sigo sin trim: %s", e)

        # Resize a 1200x1200 (cuadrado) si excede
        TARGET_SIDE = 1200
        if img.width > TARGET_SIDE:
            img = img.resize((TARGET_SIDE, TARGET_SIDE), Image.Resampling.LANCZOS)

        out = BytesIO()
        img.save(out, format="WEBP", quality=85, method=6)
        return out.getvalue(), "image/webp", img.width, img.height
    except Exception as e:
        logger.warning("optimize_image: fallback (no se pudo optimizar): %s", e, exc_info=True)
        return content, "image/jpeg", 0, 0


def _r2_config() -> dict:
    """Lee la configuración de Cloudflare R2 desde env. Eleva 500 si falta algo."""
    import os
    cfg = {
        "account_id":      os.getenv("R2_ACCOUNT_ID") or "",
        "access_key_id":   os.getenv("R2_ACCESS_KEY_ID") or "",
        "secret_key":      os.getenv("R2_SECRET_ACCESS_KEY") or "",
        "bucket":          os.getenv("R2_BUCKET") or "equipos-fotos",
        "public_base":     (os.getenv("R2_PUBLIC_BASE") or "").rstrip("/"),
    }
    missing = [k for k in ("account_id", "access_key_id", "secret_key") if not cfg[k]]
    if missing:
        raise HTTPException(
            500,
            f"R2 no configurado: faltan env vars {', '.join('R2_'+m.upper() for m in missing)}. "
            "Configurá en Railway: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, "
            "R2_BUCKET, R2_PUBLIC_BASE.",
        )
    if not cfg["public_base"]:
        # Default al endpoint público de R2 (sin custom domain) — válido si activaste public bucket
        cfg["public_base"] = f"https://pub-{cfg['account_id']}.r2.dev"
    return cfg


# Cliente boto3 singleton: crearlo cuesta ~50ms (parse config, init session,
# resolver endpoint) y antes lo creabamos en cada upload. Con singleton, el
# costo es one-time. Cacheamos la tupla (config, client) y la invalidamos
# si cambia la config (ej. rotación de credenciales en runtime).
_r2_client_cache: tuple[tuple, object] | None = None


def _get_r2_client(cfg: dict) -> object:
    """Devuelve un cliente boto3 reutilizable para el bucket R2."""
    global _r2_client_cache
    cfg_key = (cfg["account_id"], cfg["access_key_id"], cfg["secret_key"])
    if _r2_client_cache is not None and _r2_client_cache[0] == cfg_key:
        return _r2_client_cache[1]
    try:
        import boto3
        from botocore.config import Config as BotoConfig
    except ImportError:
        raise HTTPException(500, "boto3 no instalado en el backend")
    client = boto3.client(
        "s3",
        endpoint_url=f"https://{cfg['account_id']}.r2.cloudflarestorage.com",
        aws_access_key_id=cfg["access_key_id"],
        aws_secret_access_key=cfg["secret_key"],
        region_name="auto",
        config=BotoConfig(signature_version="s3v4"),
    )
    _r2_client_cache = (cfg_key, client)
    return client


def _foto_path(equipo_id: int, ext: str) -> str:
    """Genera path R2: equipos/{id}_{slug}/{id}_{slug}.{ext}
    Busca el nombre del equipo en la BD; si falla usa solo el id."""
    try:
        conn = get_db()
        row = conn.execute("SELECT nombre FROM equipos WHERE id = %s", (equipo_id,)).fetchone()
        conn.close()
        nombre = row[0] if row else ""
    except Exception:
        nombre = ""

    if nombre:
        slug = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
        slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")[:50]
    else:
        slug = ""

    if slug:
        folder   = f"{equipo_id}_{slug}"
        filename = f"{equipo_id}_{slug}.{ext}"
    else:
        folder   = f"{equipo_id}"
        filename = f"{equipo_id}.{ext}"
    return f"equipos/{folder}/{filename}"


def _upload_to_r2(path: str, content: bytes, content_type: str) -> str:
    """Sube `content` al bucket R2 vía S3 API (boto3). Devuelve la URL pública."""
    cfg = _r2_config()
    client = _get_r2_client(cfg)
    try:
        client.put_object(
            Bucket=cfg["bucket"],
            Key=path,
            Body=content,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )
    except Exception as e:
        raise HTTPException(502, f"R2 upload falló: {e}")

    return f"{cfg['public_base']}/{path}"


def _upload_to_supabase_storage(path: str, content: bytes, content_type: str) -> str:
    """Sube `content` al bucket equipos-fotos vía REST API usando service role.
    Devuelve la URL pública. Eleva HTTPException si falla.
    """
    import os
    import httpx

    base = (
        os.getenv("SUPABASE_URL")
        or os.getenv("SUPABASE_PROJECT_URL")
        or "https://ytujjqoffcdsdowfqaex.supabase.co"
    ).rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not service_key:
        raise HTTPException(
            500,
            "Falta SUPABASE_SERVICE_ROLE_KEY en el backend. "
            "Configurala como env var en Railway.",
        )

    bucket = "equipos-fotos"
    upload_url = f"{base}/storage/v1/object/{bucket}/{path}"
    headers = {
        "Authorization": f"Bearer {service_key}",
        "apikey": service_key,
        "Content-Type": content_type,
        "x-upsert": "false",
        "Cache-Control": "3600",
    }
    try:
        with httpx.Client(timeout=30.0) as c:
            r = c.post(upload_url, headers=headers, content=content)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"No se pudo subir a Storage: {e}")

    if r.status_code not in (200, 201):
        snippet = (r.text or "")[:300]
        raise HTTPException(
            r.status_code if r.status_code >= 400 else 502,
            f"Storage devolvió {r.status_code}: {snippet}",
        )

    return f"{base}/storage/v1/object/public/{bucket}/{path}"


class UploadFotoFromUrlInput(BaseModel):
    url: str
    bypass_whitelist: bool = False


@router.post("/admin/equipos/{equipo_id}/upload-foto-from-url")
def admin_upload_foto_from_url(
    equipo_id: int,
    payload: UploadFotoFromUrlInput,
    request: Request,
):
    """Descarga imagen externa, la optimiza (resize + WebP) y la sube a Cloudflare R2.
    Devuelve {public_url, path, size, content_type}.

    Reemplaza el upload directo desde el browser y el storage de Supabase.
    """
    require_admin(request)

    url = (payload.url or "").strip()
    if not url:
        raise HTTPException(400, "URL vacía")

    # Si ya es una URL del propio bucket R2 (público), no rehospedamos
    cfg_pub = (os.getenv("R2_PUBLIC_BASE") or "").rstrip("/")
    if cfg_pub and url.startswith(cfg_pub + "/"):
        return {"public_url": url, "path": None, "skipped": True}

    # SSRF guard: validar host antes de descargar.
    if payload.bypass_whitelist:
        _validate_ssrf_only(url)
    else:
        _validate_external_image_url(url)

    raw_content, raw_ctype = _download_image_bytes(url)
    # Optimización: resize a max 1600px + WebP q=85
    content, ctype, w, h = _optimize_image(raw_content)
    ext = _ext_from_ctype(ctype)

    path = _foto_path(equipo_id, ext)
    public_url = _upload_to_r2(path, content, ctype)

    return {
        "public_url": public_url,
        "path": path,
        "size": len(content),
        "size_original": len(raw_content),
        "content_type": ctype,
        "width": w or None,
        "height": h or None,
    }


# ── Admin: subir bytes de un archivo (multipart) directo a R2 ─────────────

@router.post("/admin/equipos/{equipo_id}/upload-foto")
async def admin_upload_foto_file(
    equipo_id: int,
    request: Request,
):
    """Sube un archivo (multipart/form-data, campo `file`) a R2 después de
    optimizarlo. Devuelve {public_url, path, ...}.
    """
    require_admin(request)

    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(400, "Falta el campo 'file' en el form-data")

    raw_content = await file.read()
    if not raw_content:
        raise HTTPException(400, "Archivo vacío")
    if len(raw_content) > 20 * 1024 * 1024:
        raise HTTPException(413, "Archivo muy grande (máx 20MB)")

    content, ctype, w, h = _optimize_image(raw_content)
    ext = _ext_from_ctype(ctype)

    path = _foto_path(equipo_id, ext)
    public_url = _upload_to_r2(path, content, ctype)

    return {
        "public_url": public_url,
        "path": path,
        "size": len(content),
        "size_original": len(raw_content),
        "content_type": ctype,
        "width": w or None,
        "height": h or None,
    }


# ── Admin: diagnóstico de R2 (sin exponer secretos) ─────────────────────────

@router.get("/admin/storage/diag")
def admin_storage_diag(request: Request):
    """Verifica que R2 esté configurado correctamente. Sólo dice si las vars
    están presentes y si el upload+read end-to-end funciona. NUNCA devuelve
    el contenido del secret."""
    require_admin(request)

    import time as _time
    import httpx

    vars_status = {
        "R2_ACCOUNT_ID":         bool(os.getenv("R2_ACCOUNT_ID")),
        "R2_ACCESS_KEY_ID":      bool(os.getenv("R2_ACCESS_KEY_ID")),
        "R2_SECRET_ACCESS_KEY":  bool(os.getenv("R2_SECRET_ACCESS_KEY")),
        "R2_BUCKET":             os.getenv("R2_BUCKET") or "equipos-fotos",
        "R2_PUBLIC_BASE":        os.getenv("R2_PUBLIC_BASE") or None,
    }
    missing = [k for k, v in vars_status.items() if v is False]
    if missing:
        return {"ok": False, "vars": vars_status, "missing": missing, "tested": False}

    # Smoke test: subir un blob chico y leerlo
    try:
        sample = b"R2 smoke test " + str(int(_time.time())).encode()
        path = f"diag/smoke-{int(_time.time())}.txt"
        public_url = _upload_to_r2(path, sample, "text/plain")
        verify = httpx.get(public_url, timeout=10.0)
        ok = verify.status_code == 200 and verify.content == sample
        return {
            "ok":         ok,
            "vars":       vars_status,
            "tested":     True,
            "public_url": public_url,
            "verify":     verify.status_code,
        }
    except HTTPException as e:
        return {"ok": False, "vars": vars_status, "tested": True, "error": e.detail}
    except Exception as e:
        return {"ok": False, "vars": vars_status, "tested": True, "error": str(e)}


# ── Admin: migración de paths R2 al nuevo esquema {id}_{slug}/ ───────────────

@router.post("/admin/storage/migrate-paths")
def admin_migrate_storage_paths(request: Request, dry_run: bool = True):
    """Renombra todos los objetos R2 que están bajo el prefijo 'equipos/'
    al nuevo esquema {id}_{slug}/{id}_{slug}.ext.
    Con dry_run=true (default) solo lista los cambios sin aplicarlos.
    Llamar con ?dry_run=false para ejecutar la migración real."""
    require_admin(request)

    cfg    = _r2_config()
    client = _get_r2_client(cfg)
    bucket = cfg["bucket"]
    public_base = cfg["public_base"]

    # 1. Cargar todos los equipos para construir el mapa id → slug
    conn = get_db()
    try:
        equipo_rows = conn.execute("SELECT id, nombre FROM equipos").fetchall()
    finally:
        conn.close()

    def _make_slug(nombre: str) -> str:
        s = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50]

    equipo_slugs: dict[int, str] = {}
    for row in equipo_rows:
        eid, nombre = int(row[0]), row[1] or ""
        equipo_slugs[eid] = _make_slug(nombre) if nombre else ""

    # 2. Listar objetos con prefix equipos/ (paginado)
    old_keys: list[str] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix="equipos/"):
        for obj in page.get("Contents", []):
            old_keys.append(obj["Key"])

    # 3. Calcular nuevos paths
    renames: list[dict] = []
    skipped: list[str] = []
    for old_key in old_keys:
        parts = old_key.split("/")
        if len(parts) < 3:
            skipped.append(old_key)
            continue
        try:
            equipo_id = int(parts[1])
        except ValueError:
            skipped.append(old_key)
            continue
        filename = parts[-1]
        m = re.search(r"\.([a-z0-9]+)$", filename, re.IGNORECASE)
        if not m:
            skipped.append(old_key)
            continue
        ext  = m.group(1).lower()
        slug = equipo_slugs.get(equipo_id, "")
        if slug:
            new_key = f"equipos/{equipo_id}_{slug}/{equipo_id}_{slug}.{ext}"
        else:
            new_key = f"equipos/{equipo_id}/{equipo_id}.{ext}"
        if old_key == new_key:
            continue
        renames.append({
            "equipo_id": equipo_id,
            "old": old_key,
            "new": new_key,
            "old_url": f"{public_base}/{old_key}",
            "new_url": f"{public_base}/{new_key}",
        })

    if dry_run:
        return {
            "dry_run":  True,
            "to_rename": len(renames),
            "skipped":  len(skipped),
            "detail":   renames,
        }

    # 4. Ejecutar copias + actualizaciones + borrado
    moved:      list[dict] = []
    db_updated: list[dict] = []
    errors:     list[dict] = []

    _CT_MAP = {"webp": "image/webp", "jpg": "image/jpeg", "jpeg": "image/jpeg",
               "png": "image/png", "avif": "image/avif", "gif": "image/gif"}

    for r in renames:
        ext_new = r["new"].rsplit(".", 1)[-1].lower()
        ctype   = _CT_MAP.get(ext_new, "image/webp")
        try:
            client.copy_object(
                Bucket=bucket,
                CopySource={"Bucket": bucket, "Key": r["old"]},
                Key=r["new"],
                CacheControl="public, max-age=31536000, immutable",
                MetadataDirective="REPLACE",
                ContentType=ctype,
            )
        except Exception as e:
            errors.append({"key": r["old"], "stage": "copy", "error": str(e)})
            continue

        # Actualizar foto en DB si coincide con la URL vieja
        try:
            db_conn = get_db()
            try:
                db_conn.execute(
                    "UPDATE equipos SET foto = %s WHERE id = %s AND foto = %s",
                    (r["new_url"], r["equipo_id"], r["old_url"]),
                )
                db_conn.commit()
                db_updated.append({"equipo_id": r["equipo_id"], "new_url": r["new_url"]})
            finally:
                db_conn.close()
        except Exception as e:
            errors.append({"key": r["old"], "stage": "db_update", "error": str(e)})

        try:
            client.delete_object(Bucket=bucket, Key=r["old"])
            moved.append({"old": r["old"], "new": r["new"]})
        except Exception as e:
            errors.append({"key": r["old"], "stage": "delete", "error": str(e)})

    return {
        "dry_run":   False,
        "moved":     len(moved),
        "db_updated": len(db_updated),
        "errors":    len(errors),
        "error_detail": errors,
    }
