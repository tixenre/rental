"""dataio/orchestrator.py — Coordina export/import respetando dependencias FK.

Funciones principales:
    export_all(conn, out_dir)
    import_all(conn, in_dir, dry_run=False, prune_m2m=False, only=None)
    diff_all(conn, baseline_dir) → dict de cambios por entidad

Los archivos JSON se escriben con indent=2, sort_keys=False (el orden ya
está dado por el exporter, que ordena por clave natural).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .exporters import EXPORTERS
from .importers import IMPORTERS, ImportError_
from .natural_keys import KeyResolver
from .paths import (
    CATALOG_ENTITIES,
    DATA_DIR,
    ENTITY_ORDER,
    OPERATIONAL_ENTITIES,
    entity_path,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# EXPORT
# ─────────────────────────────────────────────────────────────────────────────


def export_entity(conn, entity: str) -> list[dict]:
    """Exporta una entidad de la DB → list de dicts."""
    if entity not in EXPORTERS:
        raise ValueError(f"Entidad desconocida: {entity!r}")
    return EXPORTERS[entity](conn)


def export_all(
    conn,
    out_dir: Path | None = None,
    only: list[str] | None = None,
) -> dict[str, int]:
    """Exporta todas las entidades a `out_dir` (default DATA_DIR).

    Devuelve dict {entidad: count} con la cantidad de filas escritas.
    Crea el directorio si no existe.
    """
    out = out_dir or DATA_DIR
    out.mkdir(parents=True, exist_ok=True)
    # Default: SOLO catálogo. Operacional requiere `only=[...]` explícito
    # para evitar dumpear clientes/pedidos accidentalmente a /data/catalog/.
    entities = only if only is not None else list(CATALOG_ENTITIES)
    counts: dict[str, int] = {}
    for entity in entities:
        if entity not in EXPORTERS:
            logger.warning("Saltando entidad desconocida: %s", entity)
            continue
        rows = export_entity(conn, entity)
        path = entity_path(entity, out)
        path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        counts[entity] = len(rows)
        logger.info("Export %s: %d filas → %s", entity, len(rows), path)
    return counts


# ─────────────────────────────────────────────────────────────────────────────
# IMPORT
# ─────────────────────────────────────────────────────────────────────────────


def _read_entity_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ImportError_(f"JSON inválido en {path}: {e}") from e
    if not isinstance(data, list):
        raise ImportError_(f"{path} no contiene una lista (got {type(data).__name__})")
    return data


def import_all(
    conn,
    in_dir: Path | None = None,
    dry_run: bool = False,
    prune_m2m: bool = False,
    only: list[str] | None = None,
) -> dict[str, dict[str, int]]:
    """Importa todas las entidades en orden FK desde `in_dir`.

    Una sola transacción para todo. `dry_run=True` hace ROLLBACK al final
    aunque todo haya funcionado.

    Args:
        in_dir: directorio con los JSONs. Default DATA_DIR.
        dry_run: simula sin commitear.
        prune_m2m: borra M2M existentes antes de re-insertar (peligroso).
        only: lista de entidades a procesar (default todas en orden).

    Returns:
        {entidad: {"inserted": N, "updated": M, "skipped": K}, ...}
    """
    src = in_dir or DATA_DIR
    if not src.exists():
        raise ImportError_(f"Directorio no existe: {src}")

    # Default: SOLO catálogo. Operacional requiere `only=[...]` explícito
    # para que el startup nunca importe accidentalmente clientes/pedidos
    # desde un dump suelto.
    entities = only if only is not None else list(CATALOG_ENTITIES)
    resolver = KeyResolver(conn)
    stats: dict[str, dict[str, int]] = {}

    # Si vamos a hacer dry_run, usamos SAVEPOINT para garantizar rollback
    # incluso si la conexión está en autocommit.
    if dry_run:
        conn.execute("SAVEPOINT dataio_dry_run")

    try:
        for entity in entities:
            if entity not in IMPORTERS:
                logger.warning("Saltando entidad desconocida: %s", entity)
                continue
            path = entity_path(entity, src)
            rows = _read_entity_json(path)
            if not rows:
                stats[entity] = {"inserted": 0, "updated": 0, "skipped": 0}
                logger.info("Import %s: archivo vacío o ausente (%s)", entity, path)
                continue

            kwargs: dict[str, Any] = {}
            if entity == "equipos":
                kwargs["prune_m2m"] = prune_m2m

            entity_stats = IMPORTERS[entity](conn, rows, resolver, **kwargs)
            stats[entity] = entity_stats
            logger.info(
                "Import %s: +%d ins, ~%d upd, %d skip (%s)",
                entity,
                entity_stats.get("inserted", 0),
                entity_stats.get("updated", 0),
                entity_stats.get("skipped", 0),
                "dry-run" if dry_run else "live",
            )

        if dry_run:
            conn.execute("ROLLBACK TO SAVEPOINT dataio_dry_run")
        # commit/rollback final lo decide el caller (CLI o endpoint)
    except Exception:
        if dry_run:
            try:
                conn.execute("ROLLBACK TO SAVEPOINT dataio_dry_run")
            except Exception:
                pass
        raise

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# DIFF (compara DB vs baseline)
# ─────────────────────────────────────────────────────────────────────────────


def diff_all(
    conn, baseline_dir: Path | None = None
) -> dict[str, dict[str, list[Any]]]:
    """Compara el estado actual de la DB vs los JSONs baseline.

    Útil para responder "¿qué hay en la DB que no esté en el repo?".

    Returns:
        {entidad: {"only_in_db": [keys], "only_in_json": [keys], "modified": [keys]}}
    """
    src = baseline_dir or DATA_DIR
    out: dict[str, dict[str, list[Any]]] = {}

    # Solo comparamos catálogo. Operacional no está versionado en /data/
    # y el diff no aplica (todo estaría en "solo_en_db").
    for entity in CATALOG_ENTITIES:
        db_rows = export_entity(conn, entity)
        json_rows = _read_entity_json(entity_path(entity, src))

        # Identificar cada fila por una "key" derivada del modelo
        def _key(row: dict, entity: str = entity) -> str:
            if entity == "marcas":
                return f"marca:{row['nombre']}"
            if entity == "categorias":
                return f"cat:{row['nombre']}"
            if entity == "etiquetas":
                return f"et:{row['nombre']}"
            if entity == "spec_definitions":
                cat = row.get("categoria_raiz_nombre") or ""
                return f"sd:{cat}::{row['spec_key']}"
            if entity == "categoria_spec_templates":
                ref = row.get("spec_ref") or {}
                cat = ref.get("categoria_raiz_nombre") or ""
                return f"cst:{row['categoria_nombre']}::{cat}::{ref.get('spec_key', '')}"
            if entity == "equipos":
                return f"eq:{row['slug']}"
            if entity == "equipo_specs":
                ref = row.get("spec_ref") or {}
                cat = ref.get("categoria_raiz_nombre") or ""
                return f"es:{row['equipo_slug']}::{cat}::{ref.get('spec_key', '')}"
            if entity == "equipo_fichas":
                return f"ef:{row['equipo_slug']}"
            return json.dumps(row, sort_keys=True)

        db_by_key = {_key(r): r for r in db_rows}
        json_by_key = {_key(r): r for r in json_rows}
        only_db = [k for k in db_by_key if k not in json_by_key]
        only_json = [k for k in json_by_key if k not in db_by_key]
        modified = [
            k for k in db_by_key
            if k in json_by_key and db_by_key[k] != json_by_key[k]
        ]
        out[entity] = {
            "only_in_db": only_db,
            "only_in_json": only_json,
            "modified": modified,
        }
    return out


def init_slugs(conn, dry_run: bool = False) -> dict[str, int]:
    """Puebla `equipos.slug` para filas existentes que tengan slug NULL.

    Idempotente: si todos los equipos ya tienen slug, no hace nada.
    Genera slug a partir de `slugify(marca + modelo)` con fallback a
    `nombre` y desambiguación con sufijos (-2, -3, -id<id>).

    Returns: {"updated": N, "disambiguated": M, "already_had": K}
    """
    from .slug import equipo_slug

    stats = {"updated": 0, "disambiguated": 0, "already_had": 0}

    # Defensive check: si la columna `slug` no existe (la migración
    # e4a7c1f8d6b2 falló silenciosamente), devolvemos un stat especial
    # con `skipped=True` para que el caller pueda loguearlo claramente
    # en lugar de cascadear con un UndefinedColumn críptico.
    col_exists = conn.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'equipos' AND column_name = 'slug' LIMIT 1"
    ).fetchone()
    if not col_exists:
        stats["skipped_no_column"] = True
        return stats

    from database import marca_subquery  # type: ignore
    rows = conn.execute(
        f"SELECT id, nombre, {marca_subquery('equipos')}, modelo FROM equipos WHERE slug IS NULL"
    ).fetchall()
    if not rows:
        r = conn.execute(
            "SELECT COUNT(*) AS n FROM equipos WHERE slug IS NOT NULL"
        ).fetchone()
        stats["already_had"] = int(r["n"] or 0)
        return stats

    used_slugs = {
        r["slug"]
        for r in conn.execute(
            "SELECT slug FROM equipos WHERE slug IS NOT NULL"
        ).fetchall()
    }
    stats["already_had"] = len(used_slugs)

    for r in rows:
        base = equipo_slug(r["marca"], r["modelo"], r["nombre"])
        if not base:
            base = f"equipo-{r['id']}"
        slug = base
        i = 2
        disamb = False
        while slug in used_slugs:
            slug = f"{base}-{i}"
            i += 1
            disamb = True
            if i > 100:
                # Último recurso: sufijo con ID. También puede colisionar
                # si una corrida previa ya lo asignó, así que iteramos.
                fallback_base = f"{base}-id{r['id']}"
                slug = fallback_base
                j = 2
                while slug in used_slugs:
                    slug = f"{fallback_base}-{j}"
                    j += 1
                break
        if not dry_run:
            conn.execute(
                "UPDATE equipos SET slug = ? WHERE id = ?", (slug, r["id"])
            )
        used_slugs.add(slug)
        stats["updated"] += 1
        if disamb:
            stats["disambiguated"] += 1
    return stats


def has_catalog_data(in_dir: Path | None = None) -> bool:
    """Devuelve True si /data/catalog/ existe y tiene al menos un equipo.

    Usado por el startup para decidir si correr `dataio.import_all()` o
    fallback a los seeds viejos durante la transición.
    """
    src = in_dir or DATA_DIR
    if not src.exists():
        return False
    eq_path = entity_path("equipos", src)
    if not eq_path.exists():
        return False
    try:
        rows = _read_entity_json(eq_path)
        return len(rows) > 0
    except Exception:
        return False


def export_to_zip_bytes(conn, entities: list[str]) -> bytes:
    """Exporta `entities` a un ZIP en memoria. Útil para endpoints HTTP.

    Cada entidad va a `{entity}.json` dentro del ZIP. Devuelve los bytes
    del ZIP listos para servir como `application/zip`.
    """
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for entity in entities:
            if entity not in EXPORTERS:
                logger.warning("Saltando entidad desconocida: %s", entity)
                continue
            rows = export_entity(conn, entity)
            zf.writestr(
                f"{entity}.json",
                json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
            )
    buf.seek(0)
    return buf.read()


def import_from_zip_bytes(
    conn,
    zip_bytes: bytes,
    only: list[str],
    dry_run: bool = False,
    prune_m2m: bool = False,
) -> dict[str, dict[str, int]]:
    """Importa desde un ZIP en memoria. Útil para endpoints HTTP.

    Extrae el ZIP a un directorio temporal y delega en `import_all` con
    las mismas garantías (transacción, dry_run via SAVEPOINT).
    """
    import io
    import tempfile
    import zipfile

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            with tempfile.TemporaryDirectory(prefix="dataio_import_") as tmp:
                tmp_path = Path(tmp)
                # Extraer solo los .json esperados (no aceptamos rutas raras
                # tipo ../ por seguridad — zipfile.extract es seguro pero
                # validamos los nombres explícitamente).
                for name in zf.namelist():
                    base = Path(name).name  # quita cualquier directorio
                    if not base.endswith(".json"):
                        continue
                    entity = base[:-5]
                    if entity not in only:
                        continue
                    (tmp_path / base).write_bytes(zf.read(name))
                return import_all(
                    conn,
                    in_dir=tmp_path,
                    dry_run=dry_run,
                    prune_m2m=prune_m2m,
                    only=only,
                )
    except zipfile.BadZipFile as e:
        raise ImportError_(f"Archivo ZIP inválido: {e}") from e


def validate_dir(in_dir: Path | None = None) -> dict[str, int]:
    """Solo valida que los JSONs parseen y matcheen el schema. No toca DB.

    Returns: {entidad: count_valid_rows}
    """
    src = in_dir or DATA_DIR
    from . import schema as schema_mod

    counts: dict[str, int] = {}
    for entity in ENTITY_ORDER:
        rows = _read_entity_json(entity_path(entity, src))
        model = schema_mod.ENTITY_MODELS.get(entity)
        if not model:
            continue
        for i, row in enumerate(rows):
            try:
                model(**row)
            except Exception as e:
                raise ImportError_(f"{entity}[{i}] inválido: {e}") from e
        counts[entity] = len(rows)
    return counts
