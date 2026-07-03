"""services/specs/commands/seed.py — Persiste el registry de specs a la DB.

Lee `services/specs/registry/catalogo/*.py` (via REGISTRY) y escribe a la
DB en un solo pase idempotente:
  1. Categoría raíz (se RESUELVE por nombre, nunca se crea — ver
     `_ensure_categoria_raiz`)
  2. spec_definitions (composite key: categoria_raiz_id + spec_key)
  3. categoria_spec_templates (asignaciones a la categoría raíz)

El registry no declara navegación ni jerarquía visual (#1163 F6, desenredo
categorías↔specs) — el árbol del catálogo (prioridad, grupo_visual,
sub-categorías) lo maneja el dueño 100% a mano desde /admin/categorias.
Las sub-cats "on-the-fly" (monturas en Lentes/Adaptadores, diámetros en
Filtros) tampoco las crea este seeder — se crean al cargar equipos del
dataset (porque dependen del stock real).

Llamado desde `main._seed_registry()` en cada boot. La función
`serialize_spec_value` se reusa también en `tools/specs_import_preview.py`
para serializar valores con la misma semántica que el seeding.

Históricamente había seeders por categoría (`seeds/{cat}.py`) que cargaban
equipos junto con sus specs. Eliminados en Fase C — hoy ese flujo se hace
vía `tools/specs_import_preview.py` + `dataio.cli import`.
"""

from __future__ import annotations

import json

from ..registry import REGISTRY, CategoriaRegistry, SpecDef
from services.categorias.queries.ancestry import buscar_id_por_nombre


def _ensure_categoria_raiz(conn, nombre: str, dry_run: bool = False) -> int | None:
    """Busca la categoría raíz EXISTENTE (para que las specs cuelguen de ella).
    Devuelve su id, o None si no existe.

    Ya NO crea la categoría: el árbol del catálogo (lo que ve el usuario) lo
    maneja el dueño 100% a mano — no se siembran categorías. Si la raíz no
    existe, esta categoría del registry se saltea en el seeding de specs (ver
    `seed_categoria_from_registry`). Las specs son un sistema aparte que se
    mantiene solo; las categorías no.
    """
    return buscar_id_por_nombre(conn, nombre)


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


def _sync_value_aliases(conn, spec_def_id: int, spec: SpecDef, dry_run: bool = False) -> int:
    """Vuelca spec.value_aliases a spec_value_aliases. Idempotente (upsert por
    fila); no purga alias retirados del registry (todavía sin consumidor real
    — Fase 2, embudo apagado; se agrega purga cuando haga falta de verdad).
    Devuelve cuántas filas se escribieron."""
    if dry_run or not spec.value_aliases:
        return 0
    n = 0
    for canonico, alias_list in spec.value_aliases.items():
        for alias in alias_list:
            conn.execute(
                """
                INSERT INTO spec_value_aliases (spec_def_id, alias, valor_canonico)
                VALUES (%s, %s, %s)
                ON CONFLICT (spec_def_id, alias) DO UPDATE SET
                    valor_canonico = EXCLUDED.valor_canonico
                """,
                (spec_def_id, alias, canonico),
            )
            n += 1
    return n


def seed_categoria_from_registry(
    conn, categoria_raiz: str, dry_run: bool = False
) -> dict:
    """Sembrá una categoría desde el registry. Devuelve ids + stats.

    Returns:
        {
            "raiz_id": int,
            "spec_def_ids": {spec_key: id, ...},
            "stats": {"specs_creadas": N, "asignaciones_creadas": M, ...}
        }
    """
    cat_reg: CategoriaRegistry | None = REGISTRY.get(categoria_raiz)
    if cat_reg is None:
        raise ValueError(f"Categoría '{categoria_raiz}' no está en el registry")

    stats = {
        "specs_creadas": 0,
        "asignaciones_creadas": 0,
        "value_aliases_creados": 0,
        "dry_run": dry_run,
    }

    # 1) Raíz — solo se BUSCA, ya no se crea. Si el dueño la borró (o nunca
    #    existió), se saltea esta categoría: no se siembra nada que el usuario ve.
    raiz_id = _ensure_categoria_raiz(conn, cat_reg.nombre, dry_run=dry_run)
    if raiz_id is None:
        stats["categoria_ausente"] = True
        return {
            "raiz_id": None,
            "spec_def_ids": {},
            "stats": stats,
        }

    # 2) spec_definitions
    spec_def_ids: dict[str, int] = {}
    if raiz_id is not None:
        for spec in cat_reg.specs:
            sid = _upsert_spec_definition(conn, spec, raiz_id, dry_run)
            if sid is not None:
                spec_def_ids[spec.key] = sid
                stats["specs_creadas"] += 1
                if sid > 0:
                    stats["value_aliases_creados"] += _sync_value_aliases(
                        conn, sid, spec, dry_run
                    )

        # 3) categoria_spec_templates — asignación a la categoría raíz.
        # Las sub-cats heredan via UI (queries que walk parent → cat).
        for spec in cat_reg.specs:
            sdid = spec_def_ids.get(spec.key)
            if sdid and sdid > 0:
                if _upsert_template(conn, raiz_id, sdid, spec, dry_run):
                    stats["asignaciones_creadas"] += 1

    # 4) Purgar specs que ya no están en el registry (CASCADE limpia equipo_specs).
    purge = purge_stale_specs(conn, categoria_raiz, dry_run=dry_run)
    stats["specs_purgadas"] = purge["deleted"]

    return {
        "raiz_id": raiz_id,
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

    raiz_id = buscar_id_por_nombre(conn, categoria_raiz)
    if raiz_id is None:
        return {"to_delete": [], "kept": 0, "deleted": 0, "dry_run": dry_run}

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
    """Pasada completa: siembra todas las categorías del registry.

    Cada categoría corre en su propio SAVEPOINT para que un fallo en una no
    revierta las demás. Si una categoría falla, loguea el traceback completo
    (exc_info=True) y continúa con las siguientes.
    """
    import logging
    logger = logging.getLogger(__name__)

    result: dict = {"categorias": {}}
    for nombre in REGISTRY.categorias:
        sp = "cat_" + nombre.replace(" ", "_").replace("/", "_")
        try:
            if not dry_run:
                conn.execute(f"SAVEPOINT {sp}")
            cat_result = seed_categoria_from_registry(conn, nombre, dry_run)
            if not dry_run:
                conn.execute(f"RELEASE SAVEPOINT {sp}")
            stats = cat_result["stats"]
            logger.info(
                "Seeder [%s]: specs_creadas=%d specs_purgadas=%d",
                nombre,
                stats.get("specs_creadas", 0),
                stats.get("specs_purgadas", 0),
            )
            result["categorias"][nombre] = cat_result
        except Exception:
            logger.error(
                "Seeder falló en categoría '%s' — resto continúa",
                nombre,
                exc_info=True,
            )
            if not dry_run:
                try:
                    conn.execute(f"ROLLBACK TO SAVEPOINT {sp}")
                except Exception:
                    pass
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
