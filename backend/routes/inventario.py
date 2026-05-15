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


def _detect_categoria_sospechosa(conn) -> list[dict]:
    """Detecta equipos donde el nombre contiene un keyword fuerte que sugiere
    una categoría pero la categoría asignada no matchea. Conservador para
    minimizar falsos positivos."""
    rows = conn.execute("""
        SELECT
          e.id, e.nombre, e.marca,
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
        cats_lower = (r["categorias_actuales"] or "").lower()
        for cat_expected, kws in _CATEGORIA_KEYWORDS.items():
            if not any(_matches_keyword(nombre_lower, kw) for kw in kws):
                continue
            # ¿La categoría actual ya cubre esto? (chequeo laxo intencional
            # para no flaggear cuando el equipo está en una categoría con
            # nombre relacionado, aunque no exacto).
            if cat_expected in cats_lower:
                continue
            if any(_matches_keyword(cats_lower, kw) for kw in kws):
                continue
            out.append({
                "tipo": "categoria_sospechosa",
                "ref": str(r["id"]),
                "titulo": f"'{r['marca'] or ''} {r['nombre']}' parece {cat_expected} pero no lo tiene",
                "detalle": (
                    f"Categoría actual: {r['categorias_actuales']}. "
                    f"El nombre contiene un keyword que sugiere '{cat_expected}'."
                ),
                "equipo_id": r["id"],
                "categoria_sugerida": cat_expected,
                "accion": "asignar_categoria",
                "accion_label": f"Asignar '{cat_expected}'",
            })
            break  # 1 sospecha por equipo es suficiente
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
            return _apply_asignar_categoria(conn, equipo_id=int(body.ref))
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


def _apply_asignar_categoria(conn, equipo_id: int) -> dict:
    """Re-detecta la categoría sugerida para `equipo_id` y la asigna. La
    re-detección es por consistencia: el frontend manda solo el equipo_id,
    el match al expected se computa server-side desde el nombre actual del
    equipo (en caso de que haya cambiado entre detect y apply)."""
    eq = conn.execute(
        "SELECT id, nombre FROM equipos WHERE id = ? AND eliminado_at IS NULL",
        (equipo_id,),
    ).fetchone()
    if not eq:
        raise HTTPException(404, "Equipo no encontrado.")
    nombre_lower = (eq["nombre"] or "").lower()
    cat_expected: str | None = None
    for cat_key, kws in _CATEGORIA_KEYWORDS.items():
        if any(_matches_keyword(nombre_lower, kw) for kw in kws):
            cat_expected = cat_key
            break
    if not cat_expected:
        raise HTTPException(
            400,
            "Ya no se detecta categoría sospechosa — el nombre del equipo cambió.",
        )
    # Buscar la categoría existente cuyo nombre matchee el bucket. Preferimos
    # match exacto (LOWER(nombre) = keyword), después un LIKE laxo.
    row = conn.execute(
        "SELECT id, nombre FROM categorias WHERE LOWER(nombre) = LOWER(?) LIMIT 1",
        (cat_expected,),
    ).fetchone()
    if not row:
        row = conn.execute(
            "SELECT id, nombre FROM categorias WHERE LOWER(nombre) LIKE ? OR LOWER(nombre) LIKE ? ORDER BY id LIMIT 1",
            (f"%{cat_expected.lower()}%", f"{cat_expected.lower()}%"),
        ).fetchone()
    if not row:
        raise HTTPException(
            400,
            f"No existe una categoría llamada '{cat_expected}'. Creala primero o usá 'Editar equipo' para elegir manualmente.",
        )
    categoria_id = row["id"]
    conn.execute(
        """
        INSERT INTO equipo_categorias (equipo_id, categoria_id, orden)
        VALUES (?, ?, 0)
        ON CONFLICT (equipo_id, categoria_id) DO NOTHING
        """,
        (equipo_id, categoria_id),
    )
    conn.commit()
    return {"ok": True, "message": f"Categoría '{row['nombre']}' asignada al equipo."}


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
