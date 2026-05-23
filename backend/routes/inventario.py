"""
routes/inventario.py — Calidad y completitud del inventario.

Parte del epic #93. Incluye:
- #349 Dashboard de calidad (read-only, métricas de completitud).
- #352 Sugerencias automáticas (detectores + apply para inconsistencias).
"""

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database import get_db
from admin_guard import require_admin

router = APIRouter()


@router.get("/inventario/calidad")
def get_calidad_inventario(_admin: dict = Depends(require_admin)):
    """
    Devuelve métricas de completitud del inventario.

    Solo cuenta equipos activos (eliminado_at IS NULL). Un equipo se considera
    "faltante" en un campo si está NULL o vacío.
    """
    conn = get_db()
    try:
        # Total de equipos activos.
        total = conn.execute(
            "SELECT COUNT(*) FROM equipos WHERE eliminado_at IS NULL"
        ).fetchone()[0]

        # Campos faltantes — una query con COUNT FILTER por cada campo.
        # NULLIF + COALESCE para tratar string vacío y NULL igual.
        row = conn.execute("""
            SELECT
              COUNT(*) FILTER (WHERE NULLIF(TRIM(COALESCE(e.serie, '')), '') IS NULL)        AS sin_serie,
              COUNT(*) FILTER (WHERE e.valor_reposicion IS NULL OR e.valor_reposicion = 0)   AS sin_valor_reposicion,
              COUNT(*) FILTER (WHERE NULLIF(TRIM(COALESCE(e.foto_url, '')), '') IS NULL)     AS sin_foto,
              COUNT(*) FILTER (WHERE NULLIF(TRIM(COALESCE(f.descripcion, '')), '') IS NULL)  AS sin_descripcion,
              COUNT(*) FILTER (WHERE NULLIF(TRIM(COALESCE(e.nombre_publico, '')), '') IS NULL) AS sin_nombre_publico
            FROM equipos e
            LEFT JOIN equipo_fichas f ON f.equipo_id = e.id
            WHERE e.eliminado_at IS NULL
        """).fetchone()

        # Equipos sin categoría: no aparecen en equipo_categorias.
        sin_categoria = conn.execute("""
            SELECT COUNT(*)
            FROM equipos e
            WHERE e.eliminado_at IS NULL
              AND NOT EXISTS (
                SELECT 1 FROM equipo_categorias ec WHERE ec.equipo_id = e.id
              )
        """).fetchone()[0]

        faltantes = {
            "serie":              row["sin_serie"],
            "valor_reposicion":   row["sin_valor_reposicion"],
            "foto":               row["sin_foto"],
            "descripcion":        row["sin_descripcion"],
            "nombre_publico":     row["sin_nombre_publico"],
            "categoria":          sin_categoria,
        }

        # Score de completitud: cada equipo tiene 6 "slots" (serie, valor,
        # foto, descripción, nombre público, categoría). Slot lleno = +1.
        # Total posible = total * 6. Porcentaje = slots llenos / total posible.
        if total == 0:
            completos_pct = 100
        else:
            slots_totales = total * len(faltantes)
            slots_faltantes = sum(faltantes.values())
            completos_pct = round(100 * (slots_totales - slots_faltantes) / slots_totales)

        return {
            "total": total,
            "completos_pct": completos_pct,
            "faltantes": faltantes,
        }
    finally:
        conn.close()


# ── Sugerencias automáticas (#352) ───────────────────────────────────────────
#
# Detectores que comparan datos y proponen fix sin auto-aplicar. El admin
# revisa y decide. MVP con 2 detectores: marcas duplicadas case-insensitive
# y precio AR sin USD. Más detectores landean en iteraciones siguientes.


class AplicarSugerenciaBody(BaseModel):
    tipo: str
    ref: str


def _detect_marcas_duplicadas(conn) -> list[dict]:
    """Detecta marcas con mismo nombre normalizado (lowercase + trim) pero
    distinto registro en la tabla. Ej. 'Sony', 'sony', 'SONY' — fragmentan
    reportes y carruseles. Apply = fusionar al canonical (el más usado)."""
    rows = conn.execute("""
        SELECT
          LOWER(TRIM(nombre)) AS clave,
          json_agg(json_build_object(
            'id', id,
            'nombre', nombre,
            'cant_pedidos', cant_pedidos,
            'equipos', (SELECT COUNT(*) FROM equipos WHERE brand_id = m.id AND eliminado_at IS NULL)
          ) ORDER BY cant_pedidos DESC, id ASC) AS marcas
        FROM marcas m
        GROUP BY LOWER(TRIM(nombre))
        HAVING COUNT(*) > 1
    """).fetchall()
    out = []
    for r in rows:
        marcas = r["marcas"]
        # Canonical = primer item (orden por cant_pedidos DESC).
        out.append({
            "tipo": "marcas_duplicadas",
            "ref": r["clave"],
            "titulo": f"Marca duplicada: {marcas[0]['nombre']}",
            "detalle": (
                f"Hay {len(marcas)} variantes con el mismo nombre normalizado. "
                f"Canonical sugerida: '{marcas[0]['nombre']}' "
                f"({marcas[0]['cant_pedidos']} pedidos · {marcas[0]['equipos']} equipos)"
            ),
            "marcas": marcas,
            "accion": "fusionar",
            "accion_label": "Fusionar todas",
        })
    return out


# Heurística de categoría sospechosa: keywords de equipo → categoría esperada.
# Conservador en los keywords — sólo tokens claros, con detección por palabra
# completa (no substring) para evitar falsos positivos como "Black" matcheando
# "ac" (batería).
_CATEGORIA_KEYWORDS: dict[str, tuple[str, ...]] = {
    "cámara":     ("cam", "cámara", "camara", "camera"),
    "lente":      ("lens", "lente"),
    "luz":        ("led", "luz", "light", "softbox", "reflector"),
    "micrófono":  ("mic", "micrófono", "microfono", "microphone"),
    "audio":      ("recorder", "grabador", "preamp", "mixer", "mezcladora"),
    "trípode":    ("tripod", "trípode", "tripode", "monopod"),
    "estabilizador": ("gimbal", "estabilizador", "ronin", "stabilizer"),
    "batería":    ("v-mount", "vmount", "battery", "batería", "bateria"),
    "monitor":    ("monitor", "feelworld", "atomos"),
    "almacenamiento": ("ssd", "memoria"),
}


def _matches_keyword(text: str, kw: str) -> bool:
    """True si `kw` aparece como palabra completa en `text` (lower). Usa
    lookarounds en ASCII para evitar que "ac" matchee "black"."""
    pattern = r"(?<![a-z0-9])" + re.escape(kw.lower()) + r"(?![a-z0-9])"
    return bool(re.search(pattern, text))


def _build_keyword_to_cats(conn) -> dict[str, list[dict]]:
    """Para cada bucket de _CATEGORIA_KEYWORDS, encuentra qué categorías
    reales de la BD matchean (por palabra completa en su nombre). Devuelve
    map bucket → [{id, nombre, depth, ancestors: set[int]}], ordenadas por
    depth desc (las más específicas primero)."""
    cats = conn.execute("SELECT id, nombre, parent_id FROM categorias").fetchall()
    by_id: dict[int, dict] = {c["id"]: dict(c) for c in cats}

    def ancestors_of(cat: dict) -> set[int]:
        out: set[int] = set()
        cur = cat
        while cur.get("parent_id"):
            pid = cur["parent_id"]
            if pid in out:
                break  # protección contra ciclos
            out.add(pid)
            cur = by_id.get(pid) or {}
        return out

    def depth_of(cat: dict) -> int:
        return len(ancestors_of(cat))

    result: dict[str, list[dict]] = {}
    for bucket, kws in _CATEGORIA_KEYWORDS.items():
        matches = []
        for cid, c in by_id.items():
            nombre_lower = (c["nombre"] or "").lower()
            if any(_matches_keyword(nombre_lower, kw) for kw in kws):
                matches.append({
                    "id": cid,
                    "nombre": c["nombre"],
                    "depth": depth_of(c),
                    "ancestors": ancestors_of(c),
                })
        # Más profundas primero (más específicas).
        matches.sort(key=lambda m: (-m["depth"], m["nombre"]))
        result[bucket] = matches
    return result


def _detect_categoria_sospechosa(conn) -> list[dict]:
    """Detecta equipos donde el nombre tiene un keyword que sugiere una
    categoría existente en la BD que el equipo no tiene. Usa el árbol de
    categorías: sugiere la más profunda (específica) disponible, y no
    flaggea si el equipo ya tiene una categoría del mismo bucket o un
    descendiente de la sugerida."""
    keyword_to_cats = _build_keyword_to_cats(conn)
    if not any(keyword_to_cats.values()):
        return []  # no hay categorías matcheables en la BD

    rows = conn.execute("""
        SELECT
          e.id, e.nombre, (SELECT nombre FROM marcas WHERE id = e.brand_id) AS marca,
          COALESCE(
            (SELECT array_agg(ec.categoria_id) FROM equipo_categorias ec WHERE ec.equipo_id = e.id),
            ARRAY[]::int[]
          ) AS categoria_ids,
          (SELECT COALESCE(string_agg(c.nombre, ', '), '(sin categoría)')
             FROM equipo_categorias ec
             JOIN categorias c ON c.id = ec.categoria_id
             WHERE ec.equipo_id = e.id) AS categorias_actuales
        FROM equipos e
        WHERE e.eliminado_at IS NULL
        ORDER BY e.id
    """).fetchall()

    out = []
    for r in rows:
        nombre_lower = (r["nombre"] or "").lower()
        equipo_cat_ids: set[int] = set(r["categoria_ids"] or [])

        for bucket, kws in _CATEGORIA_KEYWORDS.items():
            if not any(_matches_keyword(nombre_lower, kw) for kw in kws):
                continue
            candidates = keyword_to_cats.get(bucket, [])
            if not candidates:
                continue
            # ¿El equipo ya tiene alguna categoría de este bucket? Saltamos.
            already_in_bucket = any(c["id"] in equipo_cat_ids for c in candidates)
            if already_in_bucket:
                continue
            # ¿Tiene un descendiente de alguna candidata? También saltamos
            # (no queremos sugerir un padre cuando el hijo ya está).
            best = None
            for c in candidates:
                if equipo_cat_ids & {c["id"], *c.get("ancestors", set())}:
                    continue
                best = c
                break
            if not best:
                continue
            out.append({
                "tipo": "categoria_sospechosa",
                "ref": f"{r['id']}:{best['id']}",  # equipo_id:categoria_id
                "titulo": f"'{r['marca'] or ''} {r['nombre']}' no tiene la categoría '{best['nombre']}'",
                "detalle": (
                    f"Categoría actual: {r['categorias_actuales']}. "
                    f"El nombre sugiere '{bucket}' — match real en la BD: '{best['nombre']}'."
                ),
                "equipo_id": r["id"],
                "categoria_sugerida": best["nombre"],
                "accion": "asignar_categoria",
                "accion_label": f"Asignar '{best['nombre']}'",
            })
            break  # una sospecha por equipo
    return out


def _detect_precio_sin_usd(conn) -> list[dict]:
    """Detecta equipos con precio_jornada cargado pero precio_usd vacío.
    Apply = computar precio_usd usando usd_rate de app_settings."""
    rows = conn.execute("""
        SELECT id, nombre, marca, precio_jornada
        FROM equipos
        WHERE eliminado_at IS NULL
          AND precio_jornada IS NOT NULL
          AND precio_jornada > 0
          AND (precio_usd IS NULL OR precio_usd = 0)
        ORDER BY precio_jornada DESC
        LIMIT 50
    """).fetchall()
    if not rows:
        return []
    return [{
        "tipo": "precio_sin_usd",
        "ref": "all",
        "titulo": f"{len(rows)} equipos con precio AR pero sin USD",
        "detalle": (
            "Estos equipos tienen precio_jornada cargado pero precio_usd vacío. "
            "El catálogo en USD muestra '—' para ellos. "
            "Apply = computar precio_usd usando la cotización actual."
        ),
        "equipos": [
            {"id": r["id"], "nombre": r["nombre"], "marca": r["marca"], "precio_jornada": r["precio_jornada"]}
            for r in rows
        ],
        "accion": "calcular_usd",
        "accion_label": "Calcular USD con cotización del día",
    }]


def _load_ignoradas(conn) -> set[tuple[str, str]]:
    """Devuelve el set de (tipo, ref) descartados por el admin."""
    rows = conn.execute("SELECT tipo, ref FROM sugerencias_ignoradas").fetchall()
    return {(r["tipo"], r["ref"]) for r in rows}


@router.get("/inventario/sugerencias")
def get_sugerencias(_admin: dict = Depends(require_admin)):
    """Devuelve la lista de sugerencias detectadas, filtrando las ignoradas
    persistidas en sugerencias_ignoradas. No muta nada."""
    conn = get_db()
    try:
        items: list[dict] = []
        items += _detect_marcas_duplicadas(conn)
        items += _detect_precio_sin_usd(conn)
        items += _detect_categoria_sospechosa(conn)
        ignoradas = _load_ignoradas(conn)
        items = [s for s in items if (s["tipo"], s["ref"]) not in ignoradas]
        return {"items": items, "total": len(items)}
    finally:
        conn.close()


@router.post("/inventario/sugerencias/ignorar")
def ignorar_sugerencia(body: AplicarSugerenciaBody, _admin: dict = Depends(require_admin)):
    """Persiste un (tipo, ref) en sugerencias_ignoradas para que no
    vuelva a aparecer en GET /sugerencias."""
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO sugerencias_ignoradas (tipo, ref)
            VALUES (?, ?)
            ON CONFLICT (tipo, ref) DO NOTHING
        """, (body.tipo, body.ref))
        conn.commit()
        return {"ok": True, "message": "Sugerencia ignorada."}
    finally:
        conn.close()


@router.post("/inventario/sugerencias/aplicar")
def aplicar_sugerencia(body: AplicarSugerenciaBody, _admin: dict = Depends(require_admin)):
    """Aplica una sugerencia. Devuelve { ok: True, message: ... } o falla 400."""
    conn = get_db()
    try:
        if body.tipo == "marcas_duplicadas":
            return _apply_fusionar_marcas(conn, clave=body.ref)
        if body.tipo == "precio_sin_usd":
            return _apply_calcular_usd(conn)
        if body.tipo == "categoria_sospechosa":
            # ref viene como "equipo_id:categoria_id"
            try:
                equipo_id_str, categoria_id_str = body.ref.split(":")
                return _apply_asignar_categoria(
                    conn,
                    equipo_id=int(equipo_id_str),
                    categoria_id=int(categoria_id_str),
                )
            except (ValueError, AttributeError):
                raise HTTPException(400, "ref inválido para categoria_sospechosa.")
        raise HTTPException(400, f"Tipo de sugerencia desconocido: {body.tipo}")
    finally:
        conn.close()


def _apply_fusionar_marcas(conn, clave: str) -> dict:
    """Fusiona todas las marcas con LOWER(nombre) = clave en una sola.
    Canonical = la que tiene más pedidos. Las demás se eliminan después de
    reapuntar sus equipos al canonical."""
    rows = conn.execute("""
        SELECT id, nombre, cant_pedidos
        FROM marcas
        WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(?))
        ORDER BY cant_pedidos DESC, id ASC
    """, (clave,)).fetchall()
    if len(rows) <= 1:
        raise HTTPException(400, "Nada para fusionar en esa clave.")
    canonical_id = rows[0]["id"]
    canonical_nombre = rows[0]["nombre"]
    duplicados_ids = [r["id"] for r in rows[1:]]
    placeholders = ",".join(["%s"] * len(duplicados_ids))
    # Repuntar equipos: brand_id + marca TEXT (que está cacheado).
    conn.execute(
        f"UPDATE equipos SET brand_id = ?, marca = ? WHERE brand_id IN ({placeholders})",
        (canonical_id, canonical_nombre, *duplicados_ids),
    )
    conn.execute(
        f"DELETE FROM marcas WHERE id IN ({placeholders})",
        tuple(duplicados_ids),
    )
    conn.commit()
    return {
        "ok": True,
        "message": (
            f"Fusionadas {len(duplicados_ids)} marcas duplicadas en '{canonical_nombre}'."
        ),
    }


def _apply_asignar_categoria(conn, equipo_id: int, categoria_id: int) -> dict:
    """Asigna `categoria_id` al `equipo_id`. La categoría viene resuelta
    desde el detector (que ya elige la más específica disponible en la BD)
    así que acá solo verificamos que ambos existan e insertamos."""
    eq = conn.execute(
        "SELECT id FROM equipos WHERE id = ? AND eliminado_at IS NULL",
        (equipo_id,),
    ).fetchone()
    if not eq:
        raise HTTPException(404, "Equipo no encontrado.")
    cat = conn.execute(
        "SELECT id, nombre FROM categorias WHERE id = ?",
        (categoria_id,),
    ).fetchone()
    if not cat:
        raise HTTPException(404, "Categoría no encontrada.")
    conn.execute(
        """
        INSERT INTO equipo_categorias (equipo_id, categoria_id, orden)
        VALUES (?, ?, 0)
        ON CONFLICT (equipo_id, categoria_id) DO NOTHING
        """,
        (equipo_id, categoria_id),
    )
    conn.commit()
    return {"ok": True, "message": f"Categoría '{cat['nombre']}' asignada al equipo."}


def _apply_calcular_usd(conn) -> dict:
    """Computa precio_usd = precio_jornada / usd_rate para los equipos
    sin USD. Lee usd_rate de app_settings."""
    rate_row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?", ("usd_rate",)
    ).fetchone()
    if not rate_row:
        raise HTTPException(400, "usd_rate no configurado en settings.")
    try:
        rate = float(rate_row["value"])
    except (TypeError, ValueError):
        raise HTTPException(400, "usd_rate inválido en settings.")
    if rate <= 0:
        raise HTTPException(400, "usd_rate debe ser > 0.")
    # Tener en cuenta el roi_pct_default si está, igual que el cálculo de
    # precio_jornada hace inverso. Por ahora cálculo simple: USD = ARS / rate.
    result = conn.execute("""
        UPDATE equipos
        SET precio_usd = ROUND((precio_jornada / ?)::numeric, 2)
        WHERE eliminado_at IS NULL
          AND precio_jornada IS NOT NULL
          AND precio_jornada > 0
          AND (precio_usd IS NULL OR precio_usd = 0)
    """, (rate,))
    n = result.rowcount if hasattr(result, "rowcount") else 0
    conn.commit()
    return {"ok": True, "message": f"{n} equipos actualizados con precio_usd calculado."}
