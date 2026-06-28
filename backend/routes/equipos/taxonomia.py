"""Taxonomía de equipos: etiquetas (tags) + categorías (#501 fase a, extraído de `core`).

Concentra la taxonomía del equipo, sacada del god-module en dos sub-cortes:
etiquetas (PR1) y categorías + clasificador automático (PR2). Registra sus rutas
en el router compartido del paquete `routes.equipos`. `_expand_to_ancestors` se
queda en `core` (lo usa también `bulk_action` del CRUD) y se importa de ahí.
"""
import logging
from typing import Optional

from fastapi import HTTPException, Query, Request
from pydantic import BaseModel

from admin_guard import require_admin
from database import (
    get_db, row_to_dict, attach_tags, attach_categorias,
    regenerate_auto_tags, regenerate_auto_tags_batch, MARCA_SUBQUERY,
)
from services.nombre_service import actualizar_nombres_de
from routes.equipos.core import router, _expand_to_ancestors

logger = logging.getLogger(__name__)

class EtiquetasUpdate(BaseModel):
    # Lista ordenada de etiquetas MANUALES. Las auto (marca/modelo/nombre/categorías)
    # se regeneran solas, no las toques desde acá.
    etiquetas: list[str]


# ── Etiquetas por equipo (reemplaza todas) ────────────────────────────────────

@router.put("/equipos/{id}/etiquetas", status_code=200)
def set_etiquetas(id: int, data: EtiquetasUpdate, request: Request):
    """Reemplaza SOLO las etiquetas manuales del equipo. Las auto se preservan."""
    require_admin(request)
    with get_db() as conn:
        try:
            if not conn.execute("SELECT id FROM equipos WHERE id=%s", (id,)).fetchone():
                raise HTTPException(404, "Equipo no encontrado")
            # Borrar solo manuales; las auto siguen vivas.
            conn.execute(
                "DELETE FROM equipo_etiquetas WHERE equipo_id = %s AND origen = 'manual'",
                (id,),
            )
            for orden, nombre in enumerate(data.etiquetas):
                nombre = (nombre or "").strip()
                if not nombre:
                    continue
                conn.execute(
                    "INSERT INTO etiquetas (nombre) VALUES (%s) ON CONFLICT (nombre) DO NOTHING",
                    (nombre,),
                )
                row = conn.execute(
                    "SELECT id FROM etiquetas WHERE nombre = %s", (nombre,)
                ).fetchone()
                if not row:
                    continue
                conn.execute("""
                    INSERT INTO equipo_etiquetas (equipo_id, etiqueta_id, orden, origen)
                    VALUES (%s, %s, %s, 'manual')
                    ON CONFLICT (equipo_id, etiqueta_id)
                    DO UPDATE SET orden = EXCLUDED.orden, origen = 'manual'
                """, (id, row["id"], orden))
            conn.commit()
            row    = conn.execute(f"SELECT *, {MARCA_SUBQUERY} FROM equipos e WHERE id=%s", (id,)).fetchone()
            equipo = attach_tags(conn, [row_to_dict(row)])[0]
            return equipo
        except Exception:
            conn.rollback()
            raise


@router.get("/etiquetas")
def list_etiquetas(incluir_auto: int = Query(0)):
    """
    Lista etiquetas. Por defecto devuelve solo las que tienen al menos un uso
    MANUAL (las auto inflan demasiado). `incluir_auto=1` devuelve todo.
    """
    with get_db() as conn:
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


@router.get("/admin/etiquetas")
def admin_list_etiquetas(request: Request):
    require_admin(request)
    with get_db() as conn:
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


@router.post("/admin/etiquetas", status_code=201)
def admin_create_etiqueta(data: EtiquetaCreate, request: Request):
    require_admin(request)
    nombre = (data.nombre or "").strip()
    if not nombre:
        raise HTTPException(400, "Nombre vacío")
    with get_db() as conn:
        try:
            # Validar parent: debe existir y ser raíz (forzar 2 niveles).
            if data.parent_id is not None:
                prow = conn.execute(
                    "SELECT id, parent_id FROM etiquetas WHERE id = %s", (data.parent_id,)
                ).fetchone()
                if not prow:
                    raise HTTPException(400, "parent_id no existe")
                if prow["parent_id"] is not None:
                    raise HTTPException(400, "Solo se permiten 2 niveles (el padre ya es subcategoría)")
            cur = conn.execute("""
                INSERT INTO etiquetas (nombre, prioridad, parent_id)
                VALUES (%s, %s, %s)
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
        with get_db() as conn0:
            prow = conn0.execute(
                "SELECT id, parent_id FROM etiquetas WHERE id = %s", (patch.parent_id,)
            ).fetchone()
            if not prow:
                raise HTTPException(400, "parent_id no existe")
            if prow["parent_id"] is not None:
                raise HTTPException(400, "Solo se permiten 2 niveles")
            # Verificar que esta etiqueta no tenga hijos (sino bajaríamos un nivel raíz).
            chrow = conn0.execute(
                "SELECT 1 FROM etiquetas WHERE parent_id = %s LIMIT 1", (eid,)
            ).fetchone()
            if chrow:
                raise HTTPException(400, "Esta etiqueta tiene hijos; no puede convertirse en hija")
        sets.append("parent_id = ?"); vals.append(int(patch.parent_id))
    if not sets:
        raise HTTPException(400, "Sin cambios")
    with get_db() as conn:
        vals.append(eid)
        conn.execute(f"UPDATE etiquetas SET {', '.join(sets)} WHERE id = %s", tuple(vals))
        conn.commit()
        return {"ok": True}


@router.delete("/admin/etiquetas/{eid}", status_code=204)
def admin_delete_etiqueta(eid: int, request: Request):
    require_admin(request)
    with get_db() as conn:
        # ON DELETE CASCADE en equipo_etiquetas + SET NULL en parent_id de hijos.
        conn.execute("DELETE FROM etiquetas WHERE id = %s", (eid,))
        conn.commit()


@router.post("/admin/etiquetas/reorder")
def admin_reorder_etiquetas(payload: EtiquetasReorder, request: Request):
    require_admin(request)
    with get_db() as conn:
        for idx, eid in enumerate(payload.ids):
            conn.execute(
                "UPDATE etiquetas SET prioridad = %s WHERE id = %s",
                ((idx + 1) * 10, eid),
            )
        conn.commit()
        return {"ok": True, "count": len(payload.ids)}


class CategoriasUpdate(BaseModel):
    # Lista de IDs de categorías hoja (o raíz) asignadas al equipo.
    categoria_ids: list[int]


@router.put("/equipos/{id}/categorias", status_code=200)
def set_categorias(id: int, data: CategoriasUpdate, request: Request):
    """
    Reemplaza la lista de categorías asignadas al equipo y regenera auto-tags
    (porque los nombres de categoría alimentan la bolsa de etiquetas auto).
    """
    require_admin(request)
    with get_db() as conn:
        try:
            if not conn.execute("SELECT id FROM equipos WHERE id=%s", (id,)).fetchone():
                raise HTTPException(404, "Equipo no encontrado")
            # Expandir a ancestros: si llega "Montura E" (hija), también se asigna
            # "Lente" (madre). Mantiene el orden original para las que ya vinieron;
            # los ancestros agregados van al final.
            expanded_ids = _expand_to_ancestors(conn, data.categoria_ids)
            # Preservar el orden del input para las que ya estaban, agregar las nuevas
            # (ancestros) al final.
            seen: set[int] = set()
            ordered: list[int] = []
            for cid in data.categoria_ids:
                try:
                    iv = int(cid)
                except (TypeError, ValueError):
                    continue
                if iv not in seen:
                    seen.add(iv)
                    ordered.append(iv)
            for iv in expanded_ids:
                if iv not in seen:
                    seen.add(iv)
                    ordered.append(iv)

            conn.execute("DELETE FROM equipo_categorias WHERE equipo_id = %s", (id,))
            for orden, cid_int in enumerate(ordered):
                conn.execute("""
                    INSERT INTO equipo_categorias (equipo_id, categoria_id, orden)
                    VALUES (%s, %s, %s)
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
            row    = conn.execute(f"SELECT *, {MARCA_SUBQUERY} FROM equipos e WHERE id=%s", (id,)).fetchone()
            equipo = attach_tags(conn, [row_to_dict(row)])[0]
            equipo = attach_categorias(conn, [equipo])[0]
            return equipo
        except Exception:
            conn.rollback()
            raise


# ── Etiquetas / Categorías ───────────────────────────────────────────────────


@router.get("/categorias")
def get_categorias(flat: int = Query(0)):
    """
    Devuelve el árbol de categorías desde la tabla `categorias`.
    `total` cuenta equipos asignados a esa categoría o a cualquier descendiente
    (vía `equipo_categorias`).
    """
    with get_db() as conn:
        # #131: agregamos popularidad_score como tiebreaker después de
        # prioridad (manual override del admin). Si todas tienen la misma
        # prioridad (default 100), gana la popularidad real.
        cats = conn.execute("""
            SELECT id, nombre, prioridad, parent_id, popularidad_score
            FROM categorias
            WHERE COALESCE(visible, TRUE) = TRUE
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


# ── Admin: gestión de etiquetas / categorías ─────────────────────────────────


# ── Admin: clasificación automática de equipos ───────────────────────────────

# Reglas leaf → keywords. Orden importa: más específico primero.
# Cada equipo recibe TODAS las hojas que matcheen (multi-asignación).
# Se aplica sobre nombre + marca + modelo (lowercase).
_RULES_LEAF = [
    # ── CÁMARAS (multi: foto+video para mirrorless híbridas) ────────────
    ("Foto",           ["a7 v", "zv-e1"]),  # mirrorless híbridas → también foto
    ("Video",          ["a7 v", "zv-e1", "fx3", "komodo", "c200"]),
    ("Acción",         ["gopro", "insta360"]),
    # ── LENTES (taxonomía: Zoom / Fijos / Vintage / Especiales; montura es filtro) ─
    ("Vintage",        ["vintage", "carl zeiss jena", "m42"]),
    ("Especiales",     ["laowa", "probe macro", "cinema pl", "master prime"]),
    ("Zoom",           ["sony gm", "sigma art 18-35", "sigma art 24-70",
                        "tokina 11-16", "canon 70-200"]),
    ("Fijos",          ["sigma art 35mm", "sigma art 50mm"]),
    # ── ADAPTADORES (raíz separada) ────────────────────────────────────
    ("Adaptadores",    ["adaptador ", "speedbooster", "mc-11"]),
    # ── FILTROS (raíz separada) ────────────────────────────────────────
    ("Filtros",        ["filtro ", "pro-mist", "tiffen"]),
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
    visible:   Optional[bool] = None
    nombre_publico_template: Optional[str] = None


class CategoriasReorder(BaseModel):
    ids: list[int]


@router.get("/admin/categorias")
def admin_list_categorias(request: Request):
    require_admin(request)
    with get_db() as conn:
        rows = conn.execute("""
            SELECT c.id, c.nombre, c.prioridad, c.parent_id,
                   COALESCE(c.visible, TRUE) AS visible,
                   c.nombre_publico_template,
                   COUNT(e.id) AS total
            FROM categorias c
            LEFT JOIN equipo_categorias ec ON ec.categoria_id = c.id
            LEFT JOIN equipos e ON e.id = ec.equipo_id AND e.eliminado_at IS NULL
            GROUP BY c.id, c.nombre, c.prioridad, c.parent_id, c.visible, c.nombre_publico_template
            ORDER BY c.prioridad ASC, LOWER(c.nombre) ASC
        """).fetchall()
        return [
            {"id": r["id"], "nombre": r["nombre"], "prioridad": r["prioridad"],
             "parent_id": r["parent_id"], "visible": bool(r["visible"]),
             "nombre_publico_template": r["nombre_publico_template"],
             "total": r["total"]}
            for r in rows
        ]


@router.post("/admin/categorias", status_code=201)
def admin_create_categoria(data: CategoriaCreate, request: Request):
    require_admin(request)
    nombre = (data.nombre or "").strip()
    if not nombre:
        raise HTTPException(400, "Nombre vacío")
    with get_db() as conn:
        try:
            if data.parent_id is not None:
                prow = conn.execute(
                    "SELECT id, parent_id FROM categorias WHERE id = %s", (data.parent_id,)
                ).fetchone()
                if not prow:
                    raise HTTPException(400, "parent_id no existe")
                # Permitimos hasta 3 niveles (depth 0, 1, 2). El padre puede
                # estar en depth 0 (root) o depth 1 (sub). No puede estar a
                # depth 2 — eso convertiría a esta cat en depth 3.
                grandparent_id = prow["parent_id"]
                if grandparent_id is not None:
                    grow = conn.execute(
                        "SELECT parent_id FROM categorias WHERE id = %s", (grandparent_id,)
                    ).fetchone()
                    if grow and grow["parent_id"] is not None:
                        raise HTTPException(400, "Solo se permiten 3 niveles de categorías")
            cur = conn.execute("""
                INSERT INTO categorias (nombre, prioridad, parent_id)
                VALUES (%s, %s, %s)
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
    if patch.visible is not None:
        sets.append("visible = ?"); vals.append(bool(patch.visible))
    if patch.nombre_publico_template is not None:
        # String vacío se guarda como NULL para distinguir "sin template".
        tpl = patch.nombre_publico_template.strip()
        sets.append("nombre_publico_template = ?"); vals.append(tpl or None)
    if patch.set_parent_null:
        sets.append("parent_id = NULL")
    elif patch.parent_id is not None:
        if patch.parent_id == cid:
            raise HTTPException(400, "Una categoría no puede ser su propio padre")
        with get_db() as conn0:
            prow = conn0.execute(
                "SELECT id, parent_id FROM categorias WHERE id = %s", (patch.parent_id,)
            ).fetchone()
            if not prow:
                raise HTTPException(400, "parent_id no existe")
            # Permitimos hasta 3 niveles (depth 0/1/2).
            # depth(new_parent) + 1 + max_descendant_depth(this) debe ser <= 2.
            def _depth_of(node_id: int) -> int:
                d = 0
                cur = node_id
                while True:
                    r = conn0.execute(
                        "SELECT parent_id FROM categorias WHERE id = %s", (cur,)
                    ).fetchone()
                    if not r or r["parent_id"] is None:
                        return d
                    d += 1
                    cur = r["parent_id"]
                    if d > 10:  # safety
                        return d

            def _max_descendant_depth(node_id: int) -> int:
                from collections import deque
                q = deque([(node_id, 0)])
                m = 0
                while q:
                    nid, d = q.popleft()
                    m = max(m, d)
                    children = conn0.execute(
                        "SELECT id FROM categorias WHERE parent_id = %s", (nid,)
                    ).fetchall()
                    for ch in children:
                        q.append((ch["id"], d + 1))
                return m

            new_parent_depth = _depth_of(patch.parent_id)
            own_max_depth = _max_descendant_depth(cid)
            if new_parent_depth + 1 + own_max_depth > 2:
                raise HTTPException(400, "Excede el máximo de 3 niveles")
            # Cycle check: el patch.parent_id no debe ser descendiente de cid.
            descendants = set()
            from collections import deque
            q = deque([cid])
            while q:
                nid = q.popleft()
                children = conn0.execute(
                    "SELECT id FROM categorias WHERE parent_id = %s", (nid,)
                ).fetchall()
                for ch in children:
                    descendants.add(ch["id"])
                    q.append(ch["id"])
            if patch.parent_id in descendants:
                raise HTTPException(400, "No se puede mover bajo un descendiente (ciclo)")
        sets.append("parent_id = ?"); vals.append(int(patch.parent_id))
    if not sets:
        raise HTTPException(400, "Sin cambios")

    # Pre-check: si hay rename, verificar que la categoría existe y que el
    # nuevo nombre no choca con otra. Mejor error de conflicto explícito que
    # 500 por UniqueViolation de psycopg2.
    if nuevo_nombre is not None:
        with get_db() as conn0:
            existe = conn0.execute(
                "SELECT id FROM categorias WHERE id = %s", (cid,)
            ).fetchone()
            if not existe:
                raise HTTPException(404, f"Categoría {cid} no existe")
            choca = conn0.execute(
                "SELECT id, nombre FROM categorias WHERE LOWER(nombre) = LOWER(%s) AND id != %s",
                (nuevo_nombre, cid),
            ).fetchone()
            if choca:
                raise HTTPException(409, f"Ya existe una categoría llamada '{choca['nombre']}'")

    with get_db() as conn:
        try:
            vals.append(cid)
            conn.execute(f"UPDATE categorias SET {', '.join(sets)} WHERE id = %s", tuple(vals))
            # Si renombró, regenerar auto-tags de los equipos afectados.
            if nuevo_nombre is not None:
                eq_rows = conn.execute(
                    "SELECT equipo_id FROM equipo_categorias WHERE categoria_id = %s", (cid,)
                ).fetchall()
                try:
                    regenerate_auto_tags_batch(conn, [r["equipo_id"] for r in eq_rows])
                except Exception:
                    # No abortar el rename si la regeneración de tags falla.
                    logger.warning("regenerate_auto_tags_batch falló tras rename de cat %s",
                                   cid, exc_info=True)
            # Si cambió el template del nombre público, regenerar el nombre de
            # cada equipo asignado a esta categoría (directa o como sub-cat).
            # Sin esto, el admin guarda el template pero los equipos siguen con
            # su nombre publico viejo hasta que alguien los toca individualmente.
            nombres_regen = 0
            if patch.nombre_publico_template is not None:
                eq_rows = conn.execute(
                    """
                    WITH RECURSIVE descendants AS (
                        SELECT id FROM categorias WHERE id = %s
                        UNION
                        SELECT c.id FROM categorias c
                        JOIN descendants d ON c.parent_id = d.id
                    )
                    SELECT DISTINCT ec.equipo_id
                    FROM equipo_categorias ec
                    JOIN descendants d ON d.id = ec.categoria_id
                    """,
                    (cid,),
                ).fetchall()
                for r in eq_rows:
                    try:
                        actualizar_nombres_de(conn, r["equipo_id"], commit=False)
                        nombres_regen += 1
                    except Exception:
                        logger.warning(
                            "actualizar_nombres_de falló para equipo %s tras cambio de template cat %s",
                            r["equipo_id"], cid, exc_info=True,
                        )
            conn.commit()
            return {"ok": True, "nombres_regenerados": nombres_regen}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            logger.error("Error en admin_update_categoria(cid=%s): %s", cid, e, exc_info=True)
            raise HTTPException(500, "Error al actualizar categoría — ver logs del servidor")


@router.delete("/admin/categorias/{cid}", status_code=204)
def admin_delete_categoria(cid: int, request: Request):
    require_admin(request)
    with get_db() as conn:
        eq_rows = conn.execute(
            "SELECT equipo_id FROM equipo_categorias WHERE categoria_id = %s", (cid,)
        ).fetchall()
        affected = [r["equipo_id"] for r in eq_rows]
        conn.execute("DELETE FROM categorias WHERE id = %s", (cid,))
        regenerate_auto_tags_batch(conn, affected)
        conn.commit()


@router.post("/admin/categorias/reorder")
def admin_reorder_categorias(payload: CategoriasReorder, request: Request):
    require_admin(request)
    with get_db() as conn:
        for idx, cid in enumerate(payload.ids):
            conn.execute(
                "UPDATE categorias SET prioridad = %s WHERE id = %s",
                ((idx + 1) * 10, cid),
            )
        conn.commit()
        return {"ok": True, "count": len(payload.ids)}


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

    with get_db() as conn:
        try:
            equipos = conn.execute(f"""
                SELECT e.id, e.nombre, {MARCA_SUBQUERY}, e.modelo
                FROM equipos e
                WHERE e.es_recurso_interno = FALSE
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
            aplicados_ids = []
            for eq in equipos:
                propuestas = _propose_tags(eq["nombre"], eq["marca"] or "", eq["modelo"] or "")
                propuestas = [p for p in propuestas if p in leaf_id]
                if propuestas:
                    matched += 1
                    if apply:
                        conn.execute(
                            "DELETE FROM equipo_categorias WHERE equipo_id = %s", (eq["id"],)
                        )
                        for orden, name in enumerate(propuestas):
                            conn.execute("""
                                INSERT INTO equipo_categorias (equipo_id, categoria_id, orden)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (equipo_id, categoria_id)
                                DO UPDATE SET orden = EXCLUDED.orden
                            """, (eq["id"], leaf_id[name], orden))
                        aplicados_ids.append(eq["id"])
                        applied += 1
                items.append({
                    "id":        eq["id"],
                    "nombre":    eq["nombre"],
                    "marca":     eq["marca"],
                    "propuestas": propuestas,
                    "actuales":  actuales.get(eq["id"], []),
                })

            if apply:
                # Regeneración batch de auto-tags para todos los reclasificados.
                regenerate_auto_tags_batch(conn, aplicados_ids)
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
