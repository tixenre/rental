"""Compatibilidad entre equipos (#501 — extraído del god-module `routes/specs.py`).

CRUD de compat manuales + el motor de cómputo (`_compute_compat` sobre specs y
familias de valores) + la compat asistida por IA en bulk (skill gear-compatibility)
+ pendientes/contexto. Registra sus rutas en el router compartido del paquete
`routes.specs`. `_require_admin` (guard) vive en `core`.
"""
import json
from typing import Optional

from fastapi import HTTPException, Request
from pydantic import BaseModel

from database import get_db, row_to_dict, MARCA_SUBQUERY
from routes.specs.core import router, _require_admin


class CompatibilidadInput(BaseModel):
    equipo_b_id: int
    tipo: str   # "compatible" | "incompatible" | "requiere_adaptador"
    nota: Optional[str] = None
    adaptador_id: Optional[int] = None


# ── Compatibilidad asistida por IA ─────────────────────────────────────
# Modelos para el skill `/compat` que escribe compat auto-generadas en
# bulk. Las manuales (auto_generado=false) nunca se tocan; las auto se
# reemplazan en cada pasada.

class CompatBulkItem(BaseModel):
    equipo_a_id: int
    equipo_b_id: int
    tipo: str   # "compatible" | "incompatible" | "requiere_adaptador"
    nota: Optional[str] = None
    adaptador_id: Optional[int] = None
    razon_ia: Optional[str] = None
    confianza: Optional[float] = None   # 0..1


class CompatBulkInput(BaseModel):
    # Equipos cuyo lado A se está procesando. Las auto previas de estos
    # equipos se borran antes de insertar las nuevas.
    equipos_procesados: list[int]
    items: list[CompatBulkItem]


# ── Compatibilidades entre equipos ──────────────────────────────────────

@router.get("/admin/equipos/{equipo_id}/compatibilidades")
def listar_compatibilidades(equipo_id: int, request: Request):
    """Devuelve las compatibilidades del equipo (tanto donde es A como B)
    para presentación bidireccional. Cada item viene con el OTRO equipo
    expandido (nombre + foto + ids)."""
    _require_admin(request)
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT
                ec.id, ec.equipo_a_id, ec.equipo_b_id, ec.tipo, ec.nota,
                ec.adaptador_id, ec.created_at,
                ec.auto_generado, ec.razon_ia, ec.confianza,
                CASE WHEN ec.equipo_a_id = ? THEN ec.equipo_b_id ELSE ec.equipo_a_id END AS otro_id,
                eb.nombre AS otro_nombre, eb.foto_url AS otro_foto,
                ea.nombre AS adaptador_nombre
            FROM equipo_compatibilidad ec
            LEFT JOIN equipos eb ON eb.id = CASE
                WHEN ec.equipo_a_id = ? THEN ec.equipo_b_id ELSE ec.equipo_a_id END
            LEFT JOIN equipos ea ON ea.id = ec.adaptador_id
            WHERE ec.equipo_a_id = ? OR ec.equipo_b_id = ?
            ORDER BY ec.auto_generado ASC, ec.tipo, eb.nombre
            """,
            (equipo_id, equipo_id, equipo_id, equipo_id),
        ).fetchall()
        items = []
        for r in rows:
            items.append({
                "id": r["id"],
                "otro_id": r["otro_id"],
                "otro_nombre": r["otro_nombre"],
                "otro_foto": r["otro_foto"],
                "tipo": r["tipo"],
                "nota": r["nota"],
                "adaptador_id": r["adaptador_id"],
                "adaptador_nombre": r["adaptador_nombre"],
                "auto_generado": bool(r["auto_generado"]),
                "razon_ia": r["razon_ia"],
                "confianza": r["confianza"],
            })
        return {"items": items}


@router.post("/admin/equipos/{equipo_id}/compatibilidades", status_code=201)
def crear_compatibilidad(equipo_id: int, payload: CompatibilidadInput, request: Request):
    """Crea una relación de compatibilidad. `equipo_id` es A, `equipo_b_id`
    el otro. La tabla tiene CHECK que evita duplicados (a,b,tipo)."""
    _require_admin(request)
    if payload.tipo not in ("compatible", "incompatible", "requiere_adaptador"):
        raise HTTPException(400, f"tipo inválido: {payload.tipo}")
    if payload.equipo_b_id == equipo_id:
        raise HTTPException(400, "No se puede relacionar un equipo consigo mismo")
    with get_db() as conn:
        # Verificar que ambos existen
        a_exists = conn.execute("SELECT id FROM equipos WHERE id = ?", (equipo_id,)).fetchone()
        b_exists = conn.execute("SELECT id FROM equipos WHERE id = ?", (payload.equipo_b_id,)).fetchone()
        if not a_exists or not b_exists:
            raise HTTPException(404, "Equipo no encontrado")
        if payload.adaptador_id:
            ad = conn.execute("SELECT id FROM equipos WHERE id = ?", (payload.adaptador_id,)).fetchone()
            if not ad:
                raise HTTPException(404, "Adaptador no encontrado")
        try:
            cur = conn.execute(
                """
                INSERT INTO equipo_compatibilidad
                  (equipo_a_id, equipo_b_id, tipo, nota, adaptador_id)
                VALUES (?, ?, ?, ?, ?)
                RETURNING id
                """,
                (equipo_id, payload.equipo_b_id, payload.tipo, payload.nota, payload.adaptador_id),
            )
            new_id = cur.fetchone()[0]
            conn.commit()
            return {"id": new_id, "equipo_a_id": equipo_id, **payload.model_dump()}
        except Exception as e:
            conn.rollback()
            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                raise HTTPException(409, "Esa compatibilidad ya existe")
            raise


@router.delete("/admin/compatibilidades/{compat_id}", status_code=204)
def borrar_compatibilidad(compat_id: int, request: Request):
    _require_admin(request)
    with get_db() as conn:
        conn.execute("DELETE FROM equipo_compatibilidad WHERE id = ?", (compat_id,))
        conn.commit()


# ── Compatibilidad automática (#F4) ─────────────────────────────────────
# Algoritmo: encuentra equipos que comparten al menos una spec marcada
# es_compatibilidad=true con el equipo base, calcula el match para cada spec
# (exacta o jerarquia), agrega overrides manuales de equipo_compatibilidad y
# devuelve un overall + razones.

# Familias jerárquicas dentro de specs multi_enum. La lógica de compat aplica
# "mínimo común" por familia cuando dos equipos comparten familia pero no
# versión exacta (ej. cámara HDMI 2.1 + monitor HDMI 2.0 → ambos hablan 2.0).
#
# Las familias viven en la tabla `spec_familia_jerarquia` (editable desde
# `/admin/specs/familias`). Este dict queda como FALLBACK para cuando la
# tabla está vacía (pre-migration o BD nueva sin seed).
_FAMILIES_FALLBACK: dict[str, list[str]] = {
    "HDMI": ["HDMI 1.4", "HDMI 2.0", "HDMI 2.1"],
    "SDI":  ["SDI 3G", "SDI 6G", "SDI 12G"],
}


def _load_families_from_db() -> dict[str, list[str]]:
    """Lee la tabla `spec_familia_jerarquia` y devuelve `{familia: [valores ordenados por posicion]}`.
    El nombre de familia en el dict mantiene el casing del display
    (HDMI/SDI). Si la tabla está vacía o falla, devuelve `_FAMILIES_FALLBACK`."""
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT familia, valor, posicion FROM spec_familia_jerarquia "
                "ORDER BY familia, posicion"
            ).fetchall()
    except Exception:
        return dict(_FAMILIES_FALLBACK)

    if not rows:
        return dict(_FAMILIES_FALLBACK)

    out: dict[str, list[str]] = {}
    for r in rows:
        d = row_to_dict(r) if not isinstance(r, dict) else r
        fam_norm = (d.get("familia") or "").strip()
        # Display name = uppercase si todo el valor empieza con el familia
        # (HDMI/SDI casos). Sino, capitalize.
        fam_display = fam_norm.upper() if len(fam_norm) <= 4 else fam_norm.capitalize()
        out.setdefault(fam_display, []).append(d.get("valor"))
    return out


# Alias retro-compat: el código existente usa `_MULTI_ENUM_FAMILIES` como
# un dict. Lo hacemos `property-like` consultando DB on demand.
class _FamiliesProxy:
    """Compatibilidad: actúa como dict pero hidrata de DB cada vez que
    se itera/lee. Caché de 60s para no martillar la BD en el motor de
    compat que itera por cada par de equipos."""
    _cache: dict[str, list[str]] = {}
    _cache_at: float = 0.0
    _ttl = 60.0

    def _refresh_if_needed(self) -> dict[str, list[str]]:
        import time
        now = time.time()
        if now - self._cache_at > self._ttl:
            self._cache = _load_families_from_db()
            self._cache_at = now
        return self._cache

    def items(self):
        return self._refresh_if_needed().items()

    def __iter__(self):
        return iter(self._refresh_if_needed())

    def __getitem__(self, key):
        return self._refresh_if_needed()[key]

    def __contains__(self, key):
        return key in self._refresh_if_needed()

    def get(self, key, default=None):
        return self._refresh_if_needed().get(key, default)

    def invalidate(self):
        """Borrar cache. Llamar después de CRUD a `spec_familia_jerarquia`."""
        self._cache_at = 0.0


_MULTI_ENUM_FAMILIES = _FamiliesProxy()


def _parse_multi_enum_value(value: str) -> list[str]:
    """Parsea un value de multi_enum desde su storage TEXT. El frontend lo
    guarda como string CSV-ish: 'HDMI 2.0, SDI 12G'. Aceptamos también JSON
    array por si vino del autocompletar IA."""
    if not value:
        return []
    v = value.strip()
    if v.startswith("["):
        try:
            arr = json.loads(v)
            return [str(x).strip() for x in arr if x]
        except Exception:
            pass
    return [p.strip() for p in v.split(",") if p.strip()]


def _compute_multi_enum_compat(label: str, a_val: str, b_val: str) -> dict:
    """Lógica de compat para multi_enum (ej. video_out).

    Orden de prioridad:
      1. Match exacto: comparten al menos un valor idéntico → status='match'.
      2. Match jerárquico intra-familia: comparten familia pero distintas
         versiones → status='match' con mensaje "limitado a versión mínima común".
      3. Sin overlap: distintas familias o sin valores comunes → status='mismatch'.
    """
    a_set = set(_parse_multi_enum_value(a_val))
    b_set = set(_parse_multi_enum_value(b_val))
    if not a_set or not b_set:
        return {"spec": label, "status": "mismatch",
                "mensaje": f"{label}: uno de los dos no tiene valores cargados"}

    # 1. Intersection directa
    common = a_set & b_set
    if common:
        return {"spec": label, "status": "match",
                "mensaje": f"{label}: comparten {', '.join(sorted(common))}"}

    # 2. Match jerárquico intra-familia
    common_versions = []
    for family_name, order in _MULTI_ENUM_FAMILIES.items():
        a_in_fam = [v for v in a_set if v in order]
        b_in_fam = [v for v in b_set if v in order]
        if not (a_in_fam and b_in_fam):
            continue
        # "El mejor que cada uno tiene" en esa familia
        a_best = max(a_in_fam, key=lambda v: order.index(v))
        b_best = max(b_in_fam, key=lambda v: order.index(v))
        # Versión común = el menor de los dos máximos
        min_idx = min(order.index(a_best), order.index(b_best))
        common_versions.append({
            "family": family_name,
            "version": order[min_idx],
            "a_best": a_best, "b_best": b_best,
        })

    if common_versions:
        partes = [
            f"{cv['family']} a {cv['version']}"
            + (f" (A: {cv['a_best']}, B: {cv['b_best']})"
               if cv["a_best"] != cv["b_best"] else "")
            for cv in common_versions
        ]
        return {"spec": label, "status": "match",
                "mensaje": f"{label}: compatible vía {', '.join(partes)} (versión mínima común)"}

    # 3. Sin overlap
    return {"spec": label, "status": "mismatch",
            "mensaje": f"{label}: sin conectores en común (A: {', '.join(sorted(a_set))} · B: {', '.join(sorted(b_set))})"}


def _compute_compat(conn, equipo_a_id: int, equipo_b_id: int) -> dict:
    """Devuelve {overall, razones, adaptador?} para el par (A, B).

    overall ∈ {compatible, compatible_con_crop, parcial, incompatible,
               requiere_adaptador, sin_relacion}
    razones: lista de {spec, status, mensaje}
    """
    # 1. Manual override (gana).
    manual = conn.execute(
        """
        SELECT ec.tipo, ec.nota, ec.adaptador_id,
               a.nombre AS adaptador_nombre
        FROM equipo_compatibilidad ec
        LEFT JOIN equipos a ON a.id = ec.adaptador_id
        WHERE (ec.equipo_a_id = ? AND ec.equipo_b_id = ?)
           OR (ec.equipo_a_id = ? AND ec.equipo_b_id = ?)
        LIMIT 1
        """,
        (equipo_a_id, equipo_b_id, equipo_b_id, equipo_a_id),
    ).fetchone()

    if manual and manual["tipo"] == "incompatible":
        return {
            "overall": "incompatible",
            "razones": [],
            "razon": manual["nota"] or "Marcado como incompatible manualmente",
        }
    if manual and manual["tipo"] == "requiere_adaptador":
        return {
            "overall": "requiere_adaptador",
            "razones": [],
            "razon": manual["nota"] or "",
            "adaptador": (
                {"id": manual["adaptador_id"], "nombre": manual["adaptador_nombre"]}
                if manual["adaptador_id"]
                else None
            ),
        }

    # 2. Auto-match por specs compartidas con es_compatibilidad=TRUE.
    spec_rows = conn.execute(
        """
        SELECT
          esa.spec_def_id, esa.value AS a_value, esb.value AS b_value,
          sd.spec_key, sd.label, sd.tipo,
          COALESCE(sd.compatibilidad_modo, 'exacta') AS modo,
          sd.enum_options,
          (SELECT rol_compatibilidad FROM categoria_spec_templates t
            JOIN equipo_categorias ec ON ec.categoria_id = t.categoria_id
            WHERE ec.equipo_id = ? AND t.spec_def_id = sd.id
            LIMIT 1) AS a_rol,
          (SELECT rol_compatibilidad FROM categoria_spec_templates t
            JOIN equipo_categorias ec ON ec.categoria_id = t.categoria_id
            WHERE ec.equipo_id = ? AND t.spec_def_id = sd.id
            LIMIT 1) AS b_rol
        FROM equipo_specs esa
        JOIN equipo_specs esb ON esb.spec_def_id = esa.spec_def_id
        JOIN spec_definitions sd ON sd.id = esa.spec_def_id
        WHERE esa.equipo_id = ? AND esb.equipo_id = ?
          AND sd.es_compatibilidad = TRUE
        """,
        (equipo_a_id, equipo_b_id, equipo_a_id, equipo_b_id),
    ).fetchall()

    razones: list[dict] = []
    for r in spec_rows:
        modo = r["modo"]
        tipo = r["tipo"]
        a_val, b_val = r["a_value"], r["b_value"]
        label = r["label"]
        if modo == "exacta":
            # multi_enum tiene su propia lógica: intersection + jerarquía
            # intra-familia (HDMI 2.1/2.0, SDI 12G/6G/3G).
            if tipo == "multi_enum":
                razones.append(_compute_multi_enum_compat(label, a_val, b_val))
            elif a_val == b_val:
                razones.append({"spec": label, "status": "match", "mensaje": f"{label}: {a_val}"})
            else:
                razones.append({"spec": label, "status": "mismatch",
                                "mensaje": f"{label}: {a_val} ≠ {b_val}"})
        elif modo == "jerarquia":
            enum_opts = r["enum_options"]
            if isinstance(enum_opts, str):
                try:
                    enum_opts = json.loads(enum_opts)
                except Exception:
                    enum_opts = []
            if not enum_opts:
                razones.append({"spec": label, "status": "match",
                                "mensaje": f"{label}: {a_val} (sin escala definida)"})
                continue
            try:
                a_pos = enum_opts.index(a_val)
                b_pos = enum_opts.index(b_val)
            except ValueError:
                razones.append({"spec": label, "status": "mismatch",
                                "mensaje": f"{label}: valor fuera de la escala definida"})
                continue
            a_rol = r["a_rol"]
            b_rol = r["b_rol"]
            if a_pos == b_pos:
                razones.append({"spec": label, "status": "match",
                                "mensaje": f"{label}: {a_val}"})
            elif {a_rol, b_rol} == {"contenedor", "contenido"}:
                if a_rol == "contenedor":
                    cont_val, conf_val, cont_pos, conf_pos = a_val, b_val, a_pos, b_pos
                else:
                    cont_val, conf_val, cont_pos, conf_pos = b_val, a_val, b_pos, a_pos
                if cont_pos >= conf_pos:
                    razones.append({
                        "spec": label, "status": "match_con_crop",
                        "mensaje": f"{label}: {cont_val} más grande que {conf_val} — usa solo el crop central",
                    })
                else:
                    razones.append({
                        "spec": label, "status": "partial_vignette",
                        "mensaje": f"{label}: {cont_val} más chico que {conf_val} → viñetea",
                    })
            else:
                razones.append({"spec": label, "status": "partial",
                                "mensaje": f"{label}: {a_val} vs {b_val} — tamaños difieren"})

    # 2.b. Cross-spec match: video_out (A) ↔ video_in (B), y video_in (A) ↔ video_out (B).
    # Permite detectar conexiones direccionales sin necesidad de que ambos equipos
    # tengan la misma spec. La cámara tiene solo video_out, el monitor solo video_in
    # — el sistema debe match cross y entender "A puede salir hacia B".
    cross_rows = conn.execute(
        """
        SELECT
          sd_a.spec_key AS a_key, sd_a.label AS a_label, esa.value AS a_value,
          sd_b.spec_key AS b_key, sd_b.label AS b_label, esb.value AS b_value
        FROM equipo_specs esa
        JOIN spec_definitions sd_a ON sd_a.id = esa.spec_def_id
        JOIN equipo_specs esb ON esb.equipo_id = ?
        JOIN spec_definitions sd_b ON sd_b.id = esb.spec_def_id
        WHERE esa.equipo_id = ?
          AND (
            (sd_a.spec_key = 'video_out' AND sd_b.spec_key = 'video_in')
            OR (sd_a.spec_key = 'video_in' AND sd_b.spec_key = 'video_out')
          )
        """,
        (equipo_b_id, equipo_a_id),
    ).fetchall()
    cross_pairs_seen: set[tuple[str, str]] = set()
    for cr in cross_rows:
        # Procesamos ambas direcciones (out→in y in→out) porque ambos son
        # conexiones reales. Dedup por par ordenado.
        key = tuple(sorted([cr["a_key"], cr["b_key"]]))
        if key in cross_pairs_seen:
            continue
        cross_pairs_seen.add(key)
        # Determinar quién es out y quién es in para el mensaje direccional
        if cr["a_key"] == "video_out":
            out_val, in_val = cr["a_value"], cr["b_value"]
            dir_label = "A→B"
        else:
            out_val, in_val = cr["b_value"], cr["a_value"]
            dir_label = "B→A"
        result = _compute_multi_enum_compat("Conexión video", out_val, in_val)
        # Reescribimos el mensaje para reflejar la direccionalidad
        if result["status"] == "match":
            result["mensaje"] = result["mensaje"].replace(
                "Conexión video: ", f"Conexión video: {dir_label} "
            )
        elif result["status"] == "mismatch":
            result["mensaje"] = (
                f"Conexión video: el out de {dir_label[0]} no matchea con "
                f"el in de {dir_label[-1]} (posiblemente requiere adaptador/converter)"
            )
        razones.append(result)

    # 3. Aggregate.
    statuses = {r["status"] for r in razones}
    if "mismatch" in statuses:
        overall = "incompatible"
    elif "partial_vignette" in statuses or "partial" in statuses:
        overall = "parcial"
    elif "match_con_crop" in statuses:
        overall = "compatible_con_crop"
    elif razones:
        overall = "compatible"
    else:
        overall = "sin_relacion"

    # Manual 'compatible' positivo: overrides parcial/incompatible.
    if manual and manual["tipo"] == "compatible" and overall in ("parcial", "incompatible"):
        overall = "compatible"

    return {"overall": overall, "razones": razones}


@router.get("/admin/equipos/{equipo_id}/compatibles")
def listar_compatibles(
    equipo_id: int,
    request: Request,
    categoria_id: Optional[int] = None,
    overall_min: Optional[str] = None,
):
    """Devuelve equipos que tienen alguna relación de compatibilidad con
    el equipo base (manual o derivada de specs).

    Filtros:
    - categoria_id: restringe los candidatos a esa categoría (recursiva).
    - overall_min: solo devuelve equipos con overall ≥ este (compatible,
      compatible_con_crop, parcial, requiere_adaptador). Default: todos
      menos sin_relacion e incompatible.
    """
    _require_admin(request)
    with get_db() as conn:
        eq = conn.execute(
            "SELECT id FROM equipos WHERE id = ? AND eliminado_at IS NULL",
            (equipo_id,),
        ).fetchone()
        if not eq:
            raise HTTPException(404, "Equipo no existe")

        # Candidatos = equipos que (a) comparten al menos una spec con es_compat
        # OR (b) tienen una entrada manual en equipo_compatibilidad.
        spec_candidatos_sql = """
            SELECT DISTINCT esb.equipo_id AS id
            FROM equipo_specs esa
            JOIN equipo_specs esb ON esb.spec_def_id = esa.spec_def_id
            JOIN spec_definitions sd ON sd.id = esa.spec_def_id
            WHERE esa.equipo_id = ?
              AND esb.equipo_id != ?
              AND sd.es_compatibilidad = TRUE
        """
        manual_candidatos_sql = """
            SELECT DISTINCT
              CASE WHEN ec.equipo_a_id = ? THEN ec.equipo_b_id ELSE ec.equipo_a_id END AS id
            FROM equipo_compatibilidad ec
            WHERE ec.equipo_a_id = ? OR ec.equipo_b_id = ?
        """
        candidates_sql = f"""
            SELECT e.id, e.nombre, {MARCA_SUBQUERY}, e.foto_url
            FROM equipos e
            WHERE e.eliminado_at IS NULL AND e.id IN (
              {spec_candidatos_sql}
              UNION
              {manual_candidatos_sql}
            )
        """
        params = [equipo_id, equipo_id, equipo_id, equipo_id, equipo_id]
        if categoria_id:
            candidates_sql += """
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
              )
            """
            params.append(categoria_id)
        candidates_sql += " ORDER BY e.nombre"

        candidates = conn.execute(candidates_sql, params).fetchall()

        items = []
        for c in candidates:
            result = _compute_compat(conn, equipo_id, c["id"])
            items.append({
                "equipo_id": c["id"],
                "nombre": c["nombre"],
                "marca": c["marca"],
                "foto_url": c["foto_url"],
                **result,
            })

        # Filtro overall_min: default = excluir sin_relacion e incompatible.
        if overall_min is None:
            items = [i for i in items if i["overall"] not in ("sin_relacion", "incompatible")]
        else:
            order = ["sin_relacion", "incompatible", "parcial", "compatible_con_crop",
                     "requiere_adaptador", "compatible"]
            if overall_min in order:
                threshold = order.index(overall_min)
                items = [i for i in items if i["overall"] in order
                         and order.index(i["overall"]) >= threshold]

        return {"items": items, "total": len(items)}


# ── Compat asistida por IA (F6: skill gear-compatibility) ───────────────
# Endpoints consumidos por el skill .claude/skills/gear-compatibility/SKILL.md
# para escribir compat auto-generadas y propuestas de specs.

@router.post("/admin/compat/bulk")
def compat_bulk(payload: CompatBulkInput, request: Request):
    """Escribe múltiples compat auto-generadas. Para cada equipo en
    equipos_procesados:
      1. Borra TODAS sus compat con auto_generado=true (regen limpia).
      2. Inserta los items con auto_generado=true.
      3. Marca compat_analizado_at = now().
    Las compat manuales (auto_generado=false) NUNCA se tocan.
    """
    _require_admin(request)
    if not payload.equipos_procesados:
        raise HTTPException(400, "equipos_procesados no puede estar vacío")

    valid_tipos = {"compatible", "incompatible", "requiere_adaptador"}
    for it in payload.items:
        if it.tipo not in valid_tipos:
            raise HTTPException(400, f"tipo inválido: {it.tipo}")
        if it.equipo_a_id == it.equipo_b_id:
            raise HTTPException(400, "equipo_a_id y equipo_b_id no pueden ser iguales")
        if it.confianza is not None and not (0.0 <= it.confianza <= 1.0):
            raise HTTPException(400, "confianza debe estar entre 0 y 1")

    with get_db() as conn:
        try:
            # 1. Verificar que todos los equipos existen.
            ids_referenciados = set(payload.equipos_procesados)
            for it in payload.items:
                ids_referenciados.add(it.equipo_a_id)
                ids_referenciados.add(it.equipo_b_id)
                if it.adaptador_id:
                    ids_referenciados.add(it.adaptador_id)
            rows = conn.execute(
                "SELECT id FROM equipos WHERE id = ANY(%s) AND eliminado_at IS NULL",
                (list(ids_referenciados),),
            ).fetchall()
            existentes = {r["id"] for r in rows}
            faltantes = ids_referenciados - existentes
            if faltantes:
                raise HTTPException(404, f"Equipos no encontrados: {sorted(faltantes)}")

            # 2. Borrar auto previas de los equipos procesados.
            for eq_id in payload.equipos_procesados:
                conn.execute(
                    """
                    DELETE FROM equipo_compatibilidad
                    WHERE auto_generado = TRUE
                      AND (equipo_a_id = ? OR equipo_b_id = ?)
                    """,
                    (eq_id, eq_id),
                )

            # 3. Insertar los nuevos.
            inserted = 0
            skipped_manual = 0
            for it in payload.items:
                # Si ya existe una manual entre este par + tipo, no la pisamos.
                manual_exists = conn.execute(
                    """
                    SELECT id FROM equipo_compatibilidad
                    WHERE auto_generado = FALSE
                      AND tipo = ?
                      AND ((equipo_a_id = ? AND equipo_b_id = ?)
                        OR (equipo_a_id = ? AND equipo_b_id = ?))
                    LIMIT 1
                    """,
                    (it.tipo, it.equipo_a_id, it.equipo_b_id,
                     it.equipo_b_id, it.equipo_a_id),
                ).fetchone()
                if manual_exists:
                    skipped_manual += 1
                    continue
                try:
                    conn.execute(
                        """
                        INSERT INTO equipo_compatibilidad
                          (equipo_a_id, equipo_b_id, tipo, nota, adaptador_id,
                           auto_generado, razon_ia, confianza)
                        VALUES (?, ?, ?, ?, ?, TRUE, ?, ?)
                        """,
                        (it.equipo_a_id, it.equipo_b_id, it.tipo, it.nota,
                         it.adaptador_id, it.razon_ia, it.confianza),
                    )
                    inserted += 1
                except Exception as e:
                    # Duplicate (a,b,tipo): ignorar — ya está
                    if "duplicate" not in str(e).lower() and "unique" not in str(e).lower():
                        conn.rollback()
                        raise

            # 4. Marcar timestamp de análisis.
            conn.execute(
                "UPDATE equipos SET compat_analizado_at = CURRENT_TIMESTAMP "
                "WHERE id = ANY(%s)",
                (payload.equipos_procesados,),
            )
            conn.commit()
            return {
                "ok": True,
                "equipos_procesados": len(payload.equipos_procesados),
                "compat_inserted": inserted,
                "skipped_manual_override": skipped_manual,
            }
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise


@router.get("/admin/equipos/pendientes-compat")
def listar_pendientes_compat(request: Request, limit: int = 50):
    """Equipos que necesitan análisis de compat: nunca analizados o
    modificados después del último análisis. Lo consume el skill cuando
    se invoca `/gear-compat new`.
    """
    _require_admin(request)
    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT
                e.id, e.nombre, {MARCA_SUBQUERY}, e.modelo,
                e.compat_analizado_at,
                e.updated_at,
                CASE
                  WHEN e.compat_analizado_at IS NULL THEN 'nunca_analizado'
                  WHEN e.updated_at > e.compat_analizado_at THEN 'modificado'
                  ELSE 'al_dia'
                END AS motivo,
                COALESCE(
                  (SELECT json_agg(c.nombre)
                   FROM equipo_categorias ec
                   JOIN categorias c ON c.id = ec.categoria_id
                   WHERE ec.equipo_id = e.id),
                  '[]'::json
                ) AS categorias
            FROM equipos e
            WHERE e.eliminado_at IS NULL
              AND (e.compat_analizado_at IS NULL
                   OR e.updated_at > e.compat_analizado_at)
            ORDER BY e.compat_analizado_at NULLS FIRST, e.updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return {
            "total": len(rows),
            "items": [
                {
                    "id": r["id"],
                    "nombre": r["nombre"],
                    "marca": r["marca"],
                    "modelo": r["modelo"],
                    "categorias": r["categorias"] or [],
                    "compat_analizado_at": str(r["compat_analizado_at"]) if r["compat_analizado_at"] else None,
                    "motivo": r["motivo"],
                }
                for r in rows
            ],
        }


@router.get("/admin/equipos/{equipo_id}/contexto-compat")
def contexto_compat(equipo_id: int, request: Request):
    """Payload completo que el skill necesita para razonar sobre un equipo:
    datos base + specs cargadas con metadata de spec_definitions + raw_json
    del autocompletar + compat manuales existentes.
    """
    _require_admin(request)
    with get_db() as conn:
        eq = conn.execute(
            f"""
            SELECT e.id, e.nombre, {MARCA_SUBQUERY}, e.modelo, e.dueno
            FROM equipos e
            WHERE e.id = ? AND e.eliminado_at IS NULL
            """,
            (equipo_id,),
        ).fetchone()
        if not eq:
            raise HTTPException(404, "Equipo no existe")

        # Categorías
        cat_rows = conn.execute(
            """
            SELECT c.id, c.nombre, c.parent_id
            FROM equipo_categorias ec
            JOIN categorias c ON c.id = ec.categoria_id
            WHERE ec.equipo_id = ?
            ORDER BY c.nombre
            """,
            (equipo_id,),
        ).fetchall()

        # Specs cargadas con metadata completa
        spec_rows = conn.execute(
            """
            SELECT
                es.spec_def_id, es.value,
                sd.spec_key, sd.label, sd.tipo, sd.unidad,
                sd.enum_options, sd.es_compatibilidad,
                COALESCE(sd.compatibilidad_modo, 'exacta') AS compatibilidad_modo,
                (SELECT rol_compatibilidad FROM categoria_spec_templates t
                  JOIN equipo_categorias ec2 ON ec2.categoria_id = t.categoria_id
                  WHERE ec2.equipo_id = ? AND t.spec_def_id = sd.id
                  LIMIT 1) AS rol_compatibilidad
            FROM equipo_specs es
            JOIN spec_definitions sd ON sd.id = es.spec_def_id
            WHERE es.equipo_id = ?
            ORDER BY sd.label
            """,
            (equipo_id, equipo_id),
        ).fetchall()

        # Ficha del equipo. Tabla canónica: `equipo_fichas` (definida en
        # database.py:397). Antes acá apuntaba a `fichas_tecnicas` (que
        # nunca existió) y leía `raw_json` (dropeado en Fase E por la
        # migración d7e9b3c5a8f2) → 500. Ver #504.
        ficha = conn.execute(
            """
            SELECT descripcion, notas
            FROM equipo_fichas
            WHERE equipo_id = ?
            """,
            (equipo_id,),
        ).fetchone()

        # Compat manuales existentes (para que el skill no las contradiga)
        manuales = conn.execute(
            """
            SELECT
                ec.id, ec.equipo_a_id, ec.equipo_b_id, ec.tipo, ec.nota,
                ec.adaptador_id,
                CASE WHEN ec.equipo_a_id = ? THEN ec.equipo_b_id ELSE ec.equipo_a_id END AS otro_id,
                eb.nombre AS otro_nombre
            FROM equipo_compatibilidad ec
            LEFT JOIN equipos eb ON eb.id = CASE
                WHEN ec.equipo_a_id = ? THEN ec.equipo_b_id ELSE ec.equipo_a_id END
            WHERE (ec.equipo_a_id = ? OR ec.equipo_b_id = ?)
              AND ec.auto_generado = FALSE
            """,
            (equipo_id, equipo_id, equipo_id, equipo_id),
        ).fetchall()

        return {
            "equipo": {
                "id": eq["id"],
                "nombre": eq["nombre"],
                "marca": eq["marca"],
                "modelo": eq["modelo"],
                "dueno": eq["dueno"],
            },
            "categorias": [
                {"id": c["id"], "nombre": c["nombre"], "parent_id": c["parent_id"]}
                for c in cat_rows
            ],
            "specs": [
                {
                    "spec_def_id": s["spec_def_id"],
                    "spec_key": s["spec_key"],
                    "label": s["label"],
                    "tipo": s["tipo"],
                    "unidad": s["unidad"],
                    "enum_options": s["enum_options"],
                    "value": s["value"],
                    "es_compatibilidad": s["es_compatibilidad"],
                    "compatibilidad_modo": s["compatibilidad_modo"],
                    "rol_compatibilidad": s["rol_compatibilidad"],
                }
                for s in spec_rows
            ],
            "ficha": {
                "descripcion": ficha["descripcion"] if ficha else None,
                "notas": ficha["notas"] if ficha else None,
            },
            "compat_manuales": [
                {
                    "id": m["id"],
                    "otro_id": m["otro_id"],
                    "otro_nombre": m["otro_nombre"],
                    "tipo": m["tipo"],
                    "nota": m["nota"],
                    "adaptador_id": m["adaptador_id"],
                }
                for m in manuales
            ],
        }
