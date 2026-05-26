"""seeds/registry_seeder.py — Persiste el registry de specs a la DB.

Lee `backend/specs/categorias/*.py` (via specs.REGISTRY) y escribe a la
DB en un solo pase idempotente:
  1. Categoría raíz (la crea si falta)
  2. Sub-categorías declaradas (Foto/Video/Acción, Zoom/Fijo/..., etc.)
  3. spec_definitions (composite key: categoria_raiz_id + spec_key)
  4. categoria_spec_templates (asignaciones a la categoría raíz)

Las sub-cats "on-the-fly" (monturas en Lentes/Adaptadores, diámetros en
Filtros) NO se crean acá — se crean al cargar equipos del dataset
(porque dependen del stock real).

Llamado desde `main._seed_registry()` en cada boot. La función
`serialize_spec_value` se reusa también en `tools/specs_import_preview.py`
para serializar valores con la misma semántica que el seeding.

Históricamente había seeders por categoría (`seeds/{cat}.py`) que cargaban
equipos junto con sus specs. Eliminados en Fase C — hoy ese flujo se hace
vía `tools/specs_import_preview.py` + `dataio.cli import`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

try:
    from specs import REGISTRY, CategoriaRegistry, SpecDef
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from specs import REGISTRY, CategoriaRegistry, SpecDef  # type: ignore

if TYPE_CHECKING:
    from psycopg.cursor import Cursor


def _ensure_categoria_raiz(
    conn,
    nombre: str,
    prioridad: int,
    grupo_visual: str | None = None,
    dry_run: bool = False,
) -> int | None:
    """Asegura que la categoría raíz EXISTA (para que las specs cuelguen de
    ella). Devuelve su id.

    No-destructivo: si ya existe, NO la toca (ni parent_id ni grupo_visual).
    El catálogo es web-managed — el registry solo bootstrapea lo que falta,
    así las ediciones hechas en la web persisten entre deploys.
    """
    row = conn.execute(
        "SELECT id FROM categorias WHERE nombre = %s", (nombre,)
    ).fetchone()
    if row:
        return row["id"]
    if dry_run:
        return None
    cur = conn.execute(
        """
        INSERT INTO categorias (nombre, prioridad, parent_id, grupo_visual)
        VALUES (%s, %s, NULL, %s)
        ON CONFLICT (nombre) DO NOTHING
        RETURNING id
        """,
        (nombre, prioridad, grupo_visual),
    )
    new = cur.fetchone()
    if new:
        return new[0] if isinstance(new, tuple) else new["id"]
    # Carrera: alguien la insertó entre el SELECT y el INSERT.
    again = conn.execute("SELECT id FROM categorias WHERE nombre = %s", (nombre,)).fetchone()
    return again["id"] if again else None


def _ensure_subcategoria(
    conn, nombre: str, prioridad: int, parent_id: int, dry_run: bool = False
) -> int | None:
    """Crea una sub-categoría si falta. Devuelve id.

    No-destructivo: si ya existe, NO la toca (ni parent_id ni prioridad). El
    árbol del catálogo es web-managed; el registry solo bootstrapea lo que
    falta, así las ediciones de la web persisten entre deploys.
    """
    row = conn.execute("SELECT id FROM categorias WHERE nombre = %s", (nombre,)).fetchone()
    if row:
        return row["id"]
    if dry_run:
        return None
    cur = conn.execute(
        """
        INSERT INTO categorias (nombre, prioridad, parent_id)
        VALUES (%s, %s, %s)
        ON CONFLICT (nombre) DO NOTHING
        RETURNING id
        """,
        (nombre, prioridad, parent_id),
    )
    new = cur.fetchone()
    if new:
        return new[0] if isinstance(new, tuple) else new["id"]
    # Carrera: alguien la insertó entre el SELECT y el INSERT.
    again = conn.execute("SELECT id FROM categorias WHERE nombre = %s", (nombre,)).fetchone()
    return again["id"] if again else None


def _upsert_spec_definition(
    conn, spec: SpecDef, categoria_raiz_id: int, dry_run: bool = False
) -> int | None:
    """Upsert spec_definitions con composite key (categoria_raiz_id, spec_key).

    Si ya existe, actualiza la metadata (label, enum_options, ayuda, etc.).
    El flag `validado=true` lo respeta — el admin lo marca a mano.
    """
    enum_json = json.dumps(spec.enum_options) if spec.enum_options else None
    aliases_json = json.dumps(spec.aliases) if spec.aliases else "[]"

    if dry_run:
        # Buscar si existe para devolver id real, sino placeholder
        row = conn.execute(
            "SELECT id FROM spec_definitions WHERE categoria_raiz_id = %s AND spec_key = %s",
            (categoria_raiz_id, spec.key),
        ).fetchone()
        return row["id"] if row else -1

    # Flags iniciales desde registry. En ON CONFLICT NO se sobreescriben — el
    # admin los puede haber tocado desde /admin/specs y queremos respetar eso.
    # Si querés re-bootstrappear, hay que truncate manual.
    favorito_inicial = bool(spec.en_card or spec.destacado)

    cur = conn.execute(
        """
        INSERT INTO spec_definitions
          (categoria_raiz_id, spec_key, label, tipo, unidad, enum_options,
           ayuda, es_compatibilidad, compatibilidad_modo, rol_compatibilidad,
           favorito, en_nombre, en_filtros, prioridad, aliases)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (categoria_raiz_id, spec_key) DO UPDATE SET
            label               = EXCLUDED.label,
            tipo                = EXCLUDED.tipo,
            unidad              = EXCLUDED.unidad,
            enum_options        = EXCLUDED.enum_options,
            ayuda               = EXCLUDED.ayuda,
            es_compatibilidad   = EXCLUDED.es_compatibilidad,
            compatibilidad_modo = EXCLUDED.compatibilidad_modo,
            rol_compatibilidad  = EXCLUDED.rol_compatibilidad,
            aliases             = EXCLUDED.aliases,
            updated_at          = CURRENT_TIMESTAMP
        RETURNING id
        """,
        (
            categoria_raiz_id, spec.key, spec.label, spec.tipo, spec.unidad,
            enum_json, spec.ayuda, spec.es_compatibilidad,
            spec.compatibilidad_modo or "exacta",
            spec.rol_compatibilidad,
            favorito_inicial, bool(spec.en_nombre), bool(spec.en_filtros),
            int(spec.prioridad), aliases_json,
        ),
    )
    new = cur.fetchone()
    return new[0] if isinstance(new, tuple) else (new["id"] if new else None)


def _upsert_template(
    conn, categoria_id: int, spec_def_id: int, spec: SpecDef, dry_run: bool = False
) -> bool:
    """Asigna spec_def a una categoría con sus flags. Idempotente."""
    if dry_run:
        return True
    cur = conn.execute(
        """
        INSERT INTO categoria_spec_templates
          (categoria_id, spec_def_id, prioridad, destacado, obligatorio,
           visible_en_card, visible_en_filtros, visible_en_nombre, ayuda)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (categoria_id, spec_def_id) DO UPDATE SET
            prioridad          = EXCLUDED.prioridad,
            destacado          = EXCLUDED.destacado,
            obligatorio        = EXCLUDED.obligatorio,
            visible_en_card    = EXCLUDED.visible_en_card,
            visible_en_filtros = EXCLUDED.visible_en_filtros,
            visible_en_nombre  = EXCLUDED.visible_en_nombre,
            ayuda              = EXCLUDED.ayuda
        RETURNING id
        """,
        (
            categoria_id, spec_def_id, spec.prioridad, spec.destacado,
            spec.obligatorio, spec.en_card, spec.en_filtros, spec.en_nombre,
            spec.ayuda,
        ),
    )
    return cur.fetchone() is not None


def seed_categoria_from_registry(
    conn, categoria_raiz: str, dry_run: bool = False
) -> dict:
    """Sembrá una categoría desde el registry. Devuelve ids + stats.

    Returns:
        {
            "raiz_id": int,
            "subcat_ids": {nombre: id, ...},
            "spec_def_ids": {spec_key: id, ...},
            "stats": {"specs_creadas": N, "subcategorias_creadas": M, ...}
        }
    """
    cat_reg: CategoriaRegistry | None = REGISTRY.get(categoria_raiz)
    if cat_reg is None:
        raise ValueError(f"Categoría '{categoria_raiz}' no está en el registry")

    stats = {
        "specs_creadas": 0,
        "subcategorias_creadas": 0,
        "asignaciones_creadas": 0,
        "dry_run": dry_run,
    }

    # 1) Raíz
    raiz_id = _ensure_categoria_raiz(
        conn,
        cat_reg.nombre,
        cat_reg.prioridad,
        grupo_visual=cat_reg.grupo_visual,
        dry_run=dry_run,
    )
    if raiz_id is None and not dry_run:
        raise RuntimeError(f"No se pudo crear categoría raíz '{cat_reg.nombre}'")

    # 2) Sub-categorías (con soporte de niveles vía `parent`)
    subcat_ids: dict[str, int] = {}
    # Primer pase: sin parent (van bajo raíz)
    for sub in cat_reg.sub_categorias:
        if sub.parent is None:
            sid = _ensure_subcategoria(conn, sub.nombre, sub.prioridad, raiz_id, dry_run)
            if sid is not None:
                subcat_ids[sub.nombre] = sid
                stats["subcategorias_creadas"] += 1
    # Segundo pase: con parent (van bajo sub-cat existente)
    for sub in cat_reg.sub_categorias:
        if sub.parent is not None:
            parent_sid = subcat_ids.get(sub.parent)
            if parent_sid is None and not dry_run:
                raise RuntimeError(
                    f"Sub-categoría '{sub.nombre}' referencia parent '{sub.parent}' "
                    "que no está en el registry"
                )
            sid = _ensure_subcategoria(conn, sub.nombre, sub.prioridad, parent_sid or raiz_id, dry_run)
            if sid is not None:
                subcat_ids[sub.nombre] = sid
                stats["subcategorias_creadas"] += 1

    # 3) spec_definitions
    spec_def_ids: dict[str, int] = {}
    if raiz_id is not None:
        for spec in cat_reg.specs:
            sid = _upsert_spec_definition(conn, spec, raiz_id, dry_run)
            if sid is not None:
                spec_def_ids[spec.key] = sid
                stats["specs_creadas"] += 1

        # 4) categoria_spec_templates — asignación a la categoría raíz.
        # Las sub-cats heredan via UI (queries que walk parent → cat).
        for spec in cat_reg.specs:
            sdid = spec_def_ids.get(spec.key)
            if sdid and sdid > 0:
                if _upsert_template(conn, raiz_id, sdid, spec, dry_run):
                    stats["asignaciones_creadas"] += 1

    # 5) Purgar specs que ya no están en el registry (CASCADE limpia equipo_specs).
    purge = purge_stale_specs(conn, categoria_raiz, dry_run=dry_run)
    stats["specs_purgadas"] = purge["deleted"]

    return {
        "raiz_id": raiz_id,
        "subcat_ids": subcat_ids,
        "spec_def_ids": spec_def_ids,
        "stats": stats,
        "purge": purge,
    }


def purge_stale_specs(conn, categoria_raiz: str, dry_run: bool = True) -> dict:
    """Borra spec_definitions cuya (categoria_raiz_id, spec_key) ya no está en
    el registry de esa categoría.

    CASCADE en la DB limpia equipo_specs + categoria_spec_templates automáticamente.
    dry_run=True (default): solo reporta las filas que borraría, sin borrar.

    Returns:
        {"to_delete": [spec_keys], "kept": N, "deleted": N, "dry_run": bool}
    """
    import logging
    logger = logging.getLogger(__name__)

    cat_reg: CategoriaRegistry | None = REGISTRY.get(categoria_raiz)
    if cat_reg is None:
        raise ValueError(f"Categoría '{categoria_raiz}' no está en el registry")

    raiz_row = conn.execute(
        "SELECT id FROM categorias WHERE nombre = %s", (categoria_raiz,)
    ).fetchone()
    if raiz_row is None:
        return {"to_delete": [], "kept": 0, "deleted": 0, "dry_run": dry_run}

    raiz_id = raiz_row["id"] if isinstance(raiz_row, dict) else raiz_row[0]

    registry_keys = {s.key for s in cat_reg.specs}

    db_rows = conn.execute(
        "SELECT id, spec_key FROM spec_definitions WHERE categoria_raiz_id = %s",
        (raiz_id,),
    ).fetchall()

    stale = [
        (r["id"] if isinstance(r, dict) else r[0],
         r["spec_key"] if isinstance(r, dict) else r[1])
        for r in db_rows
        if (r["spec_key"] if isinstance(r, dict) else r[1]) not in registry_keys
    ]
    kept = len(db_rows) - len(stale)

    for sid, key in stale:
        logger.info("purge_stale_specs [%s] %s '%s' (id=%s)", "DRY-RUN" if dry_run else "DELETE", categoria_raiz, key, sid)

    if not dry_run and stale:
        ids = [sid for sid, _ in stale]
        conn.execute(
            "DELETE FROM spec_definitions WHERE id = ANY(%s)", (ids,)
        )

    return {
        "to_delete": [key for _, key in stale],
        "kept": kept,
        "deleted": 0 if dry_run else len(stale),
        "dry_run": dry_run,
    }


def seed_all_categorias(conn, dry_run: bool = False) -> dict:
    """Pasada completa: siembra todas las categorías del registry."""
    result: dict = {"categorias": {}}
    for nombre in REGISTRY.categorias:
        result["categorias"][nombre] = seed_categoria_from_registry(conn, nombre, dry_run)
    return result


# ── Serialización de valores spec → equipo_specs.value (TEXT) ────────────

def serialize_spec_value(spec: SpecDef, value) -> str | None:
    """Convierte el valor del dataset al formato TEXT que va en equipo_specs.

    Reglas según `spec.tipo`:
      bool       → "true" | "false"
      number     → "{n}"
      string     → str(value)
      enum       → str(value) (debe estar en enum_options; eso lo valida el parser/seed)
      multi_enum → JSON array
      rango      → JSON array (siempre lista; [v] fijo, [min, max] variable)
    """
    if value is None:
        return None

    if spec.tipo == "bool":
        return "true" if value else "false"

    if spec.tipo == "rango":
        if not isinstance(value, list):
            value = [value]
        return json.dumps(value, ensure_ascii=False)

    if spec.tipo == "multi_enum":
        if not isinstance(value, list):
            value = [value]
        return json.dumps(value, ensure_ascii=False)

    if spec.tipo == "number":
        if isinstance(value, bool):
            return None  # type confusion guard
        return str(value)

    # enum, string
    return str(value)
