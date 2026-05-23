"""dataio/importers.py — list[dict] → upsert DB.

Cada función `import_<entidad>(conn, rows, resolver, dry_run)` valida cada
row con el modelo Pydantic correspondiente y aplica un upsert idempotente
contra la DB.

Política:
- Upsert por clave natural. Insertar si no existe, actualizar si existe.
- Campos del modelo siempre pisan (la fuente de verdad es el JSON).
- M2M (`equipo_categorias`, `equipo_etiquetas`): siempre inserta del JSON
  con `ON CONFLICT DO UPDATE` para mantener `orden`/`origen`. Si una fila
  está en la DB pero no en el JSON, se preserva (es custom local).
  El borrado de no-listadas se hace solo con `prune=True`.
- `dry_run=True` no ejecuta inserts; el orchestrator usa SAVEPOINT/ROLLBACK
  para garantizar atomicidad incluso en dry-run.

Devuelve siempre un dict con stats: `{"inserted", "updated", "skipped"}`.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from . import schema
from .natural_keys import KeyResolver


class ImportError_(Exception):
    """Error de importación con contexto de qué fila falló."""


def _validate_rows(rows: list[dict], model: type[schema._Base], entity: str) -> list:
    out = []
    for i, row in enumerate(rows):
        try:
            out.append(model(**row))
        except ValidationError as e:
            raise ImportError_(
                f"Validación falló en {entity}[{i}]: {e}"
            ) from e
    return out


# ─────────────────────────────────────────────────────────────────────────────
# marcas
# ─────────────────────────────────────────────────────────────────────────────


def import_marcas(
    conn, rows: list[dict], resolver: KeyResolver, dry_run: bool = False
) -> dict[str, int]:
    items = _validate_rows(rows, schema.Marca, "marcas")
    stats = {"inserted": 0, "updated": 0, "skipped": 0}
    if dry_run:
        return stats
    for m in items:
        cur = conn.execute(
            """
            INSERT INTO marcas (nombre, logo_url, visible, orden, destacada)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (nombre) DO UPDATE SET
                logo_url = EXCLUDED.logo_url,
                visible = EXCLUDED.visible,
                orden = EXCLUDED.orden,
                destacada = EXCLUDED.destacada,
                updated_at = CURRENT_TIMESTAMP
            RETURNING (xmax = 0) AS inserted
            """,
            (m.nombre, m.logo_url, m.visible, m.orden, m.destacada),
        )
        row = cur.fetchone()
        if row and row["inserted"]:
            stats["inserted"] += 1
        else:
            stats["updated"] += 1
    resolver.refresh_marcas()
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# categorias (con resolución de parent_path en pases por nivel)
# ─────────────────────────────────────────────────────────────────────────────


def import_categorias(
    conn, rows: list[dict], resolver: KeyResolver, dry_run: bool = False
) -> dict[str, int]:
    items = _validate_rows(rows, schema.Categoria, "categorias")
    stats = {"inserted": 0, "updated": 0, "skipped": 0}
    if dry_run:
        return stats

    # Pase 1: insertar raíces (parent_path IS None) y todas las categorías
    # con upsert simple, sin parent_id.
    pending: list[schema.Categoria] = []
    for c in items:
        cur = conn.execute(
            """
            INSERT INTO categorias (nombre, prioridad, parent_id, visible,
                                    grupo_visual, nombre_publico_template)
            VALUES (?, ?, NULL, ?, ?, ?)
            ON CONFLICT (nombre) DO UPDATE SET
                prioridad = EXCLUDED.prioridad,
                visible = EXCLUDED.visible,
                grupo_visual = EXCLUDED.grupo_visual,
                nombre_publico_template = EXCLUDED.nombre_publico_template
            RETURNING (xmax = 0) AS inserted
            """,
            (
                c.nombre,
                c.prioridad,
                c.visible,
                c.grupo_visual,
                c.nombre_publico_template,
            ),
        )
        row = cur.fetchone()
        if row and row["inserted"]:
            stats["inserted"] += 1
        else:
            stats["updated"] += 1
        if c.parent_path:
            pending.append(c)

    # Pase 2: resolver parent_id de los que tienen parent_path
    resolver.refresh_categorias()
    for c in pending:
        parent_id = resolver.categoria_id(c.parent_path)
        if parent_id is None:
            raise ImportError_(
                f"categorias: '{c.nombre}' referencia parent_path='{c.parent_path}' "
                f"que no existe (debe estar en el mismo JSON)"
            )
        conn.execute(
            "UPDATE categorias SET parent_id = ? WHERE nombre = ?",
            (parent_id, c.nombre),
        )
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# etiquetas
# ─────────────────────────────────────────────────────────────────────────────


def import_etiquetas(
    conn, rows: list[dict], resolver: KeyResolver, dry_run: bool = False
) -> dict[str, int]:
    items = _validate_rows(rows, schema.Etiqueta, "etiquetas")
    stats = {"inserted": 0, "updated": 0, "skipped": 0}
    if dry_run:
        return stats
    for e in items:
        cur = conn.execute(
            """
            INSERT INTO etiquetas (nombre, prioridad)
            VALUES (?, ?)
            ON CONFLICT (nombre) DO UPDATE SET prioridad = EXCLUDED.prioridad
            RETURNING (xmax = 0) AS inserted
            """,
            (e.nombre, e.prioridad),
        )
        row = cur.fetchone()
        if row and row["inserted"]:
            stats["inserted"] += 1
        else:
            stats["updated"] += 1
    resolver.refresh_etiquetas()
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# spec_definitions
# ─────────────────────────────────────────────────────────────────────────────


def import_spec_definitions(
    conn, rows: list[dict], resolver: KeyResolver, dry_run: bool = False
) -> dict[str, int]:
    items = _validate_rows(rows, schema.SpecDefinition, "spec_definitions")
    stats = {"inserted": 0, "updated": 0, "skipped": 0}
    if dry_run:
        return stats
    import json as _json

    for sd in items:
        cat_raiz_id = resolver.categoria_id(sd.categoria_raiz_nombre)
        if sd.categoria_raiz_nombre and cat_raiz_id is None:
            raise ImportError_(
                f"spec_definitions: spec_key='{sd.spec_key}' referencia "
                f"categoria_raiz_nombre='{sd.categoria_raiz_nombre}' que no existe"
            )

        enum_json = (
            _json.dumps(sd.enum_options, ensure_ascii=False)
            if sd.enum_options is not None
            else None
        )
        tabla_cols = (
            _json.dumps(sd.tabla_columnas, ensure_ascii=False)
            if sd.tabla_columnas is not None
            else None
        )
        output_cfg = (
            _json.dumps(sd.output_config, ensure_ascii=False)
            if sd.output_config is not None
            else None
        )

        # ON CONFLICT distinto según si tiene categoria_raiz_id o es global.
        # Las UNIQUEs son: (categoria_raiz_id, spec_key) para las con cat;
        # idx_spec_def_global_unique partial para las sin cat (WHERE categoria_raiz_id IS NULL).
        if cat_raiz_id is not None:
            cur = conn.execute(
                """
                INSERT INTO spec_definitions
                    (categoria_raiz_id, spec_key, label, tipo, unidad, enum_options,
                     ayuda, es_compatibilidad, compatibilidad_modo, rol_compatibilidad,
                     validado, tabla_columnas, output_config, favorito, en_nombre,
                     en_filtros, prioridad)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (categoria_raiz_id, spec_key) DO UPDATE SET
                    label = EXCLUDED.label,
                    tipo = EXCLUDED.tipo,
                    unidad = EXCLUDED.unidad,
                    enum_options = EXCLUDED.enum_options,
                    ayuda = EXCLUDED.ayuda,
                    es_compatibilidad = EXCLUDED.es_compatibilidad,
                    compatibilidad_modo = EXCLUDED.compatibilidad_modo,
                    rol_compatibilidad = EXCLUDED.rol_compatibilidad,
                    validado = EXCLUDED.validado,
                    tabla_columnas = EXCLUDED.tabla_columnas,
                    output_config = EXCLUDED.output_config,
                    favorito = EXCLUDED.favorito,
                    en_nombre = EXCLUDED.en_nombre,
                    en_filtros = EXCLUDED.en_filtros,
                    prioridad = EXCLUDED.prioridad,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING (xmax = 0) AS inserted
                """,
                (
                    cat_raiz_id, sd.spec_key, sd.label, sd.tipo, sd.unidad,
                    enum_json, sd.ayuda, sd.es_compatibilidad,
                    sd.compatibilidad_modo, sd.rol_compatibilidad, sd.validado,
                    tabla_cols, output_cfg, sd.favorito, sd.en_nombre,
                    sd.en_filtros, sd.prioridad,
                ),
            )
        else:
            # Global spec (sin categoria_raiz): manual lookup + insert/update,
            # porque el ON CONFLICT no aplica al partial index.
            existing = conn.execute(
                "SELECT id FROM spec_definitions "
                "WHERE categoria_raiz_id IS NULL AND spec_key = ?",
                (sd.spec_key,),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE spec_definitions SET
                        label = ?, tipo = ?, unidad = ?, enum_options = ?,
                        ayuda = ?, es_compatibilidad = ?, compatibilidad_modo = ?,
                        rol_compatibilidad = ?, validado = ?, tabla_columnas = ?,
                        output_config = ?, favorito = ?, en_nombre = ?,
                        en_filtros = ?, prioridad = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        sd.label, sd.tipo, sd.unidad, enum_json, sd.ayuda,
                        sd.es_compatibilidad, sd.compatibilidad_modo,
                        sd.rol_compatibilidad, sd.validado, tabla_cols, output_cfg,
                        sd.favorito, sd.en_nombre, sd.en_filtros, sd.prioridad,
                        existing["id"],
                    ),
                )
                cur = None
            else:
                cur = conn.execute(
                    """
                    INSERT INTO spec_definitions
                        (categoria_raiz_id, spec_key, label, tipo, unidad, enum_options,
                         ayuda, es_compatibilidad, compatibilidad_modo, rol_compatibilidad,
                         validado, tabla_columnas, output_config, favorito, en_nombre,
                         en_filtros, prioridad)
                    VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sd.spec_key, sd.label, sd.tipo, sd.unidad, enum_json,
                        sd.ayuda, sd.es_compatibilidad, sd.compatibilidad_modo,
                        sd.rol_compatibilidad, sd.validado, tabla_cols, output_cfg,
                        sd.favorito, sd.en_nombre, sd.en_filtros, sd.prioridad,
                    ),
                )

        if cur is not None:
            row = cur.fetchone()
            if row and row["inserted"]:
                stats["inserted"] += 1
            else:
                stats["updated"] += 1
        else:
            stats["updated"] += 1

    resolver.refresh_spec_defs()
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# categoria_spec_templates
# ─────────────────────────────────────────────────────────────────────────────


def import_categoria_spec_templates(
    conn, rows: list[dict], resolver: KeyResolver, dry_run: bool = False
) -> dict[str, int]:
    items = _validate_rows(
        rows, schema.CategoriaSpecTemplate, "categoria_spec_templates"
    )
    stats = {"inserted": 0, "updated": 0, "skipped": 0}
    if dry_run:
        return stats
    for t in items:
        cat_id = resolver.categoria_id(t.categoria_nombre)
        if cat_id is None:
            raise ImportError_(
                f"categoria_spec_templates: categoria_nombre='{t.categoria_nombre}' "
                "no existe"
            )
        spec_id = resolver.spec_def_id(
            t.spec_ref.categoria_raiz_nombre, t.spec_ref.spec_key
        )
        if spec_id is None:
            raise ImportError_(
                f"categoria_spec_templates: spec_ref={t.spec_ref!r} no existe"
            )
        cur = conn.execute(
            """
            INSERT INTO categoria_spec_templates
                (categoria_id, spec_def_id, prioridad, destacado, obligatorio,
                 visible_en_card, visible_en_filtros, visible_en_nombre, ayuda)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (categoria_id, spec_def_id) DO UPDATE SET
                prioridad = EXCLUDED.prioridad,
                destacado = EXCLUDED.destacado,
                obligatorio = EXCLUDED.obligatorio,
                visible_en_card = EXCLUDED.visible_en_card,
                visible_en_filtros = EXCLUDED.visible_en_filtros,
                visible_en_nombre = EXCLUDED.visible_en_nombre,
                ayuda = EXCLUDED.ayuda
            RETURNING (xmax = 0) AS inserted
            """,
            (
                cat_id, spec_id, t.prioridad, t.destacado, t.obligatorio,
                t.visible_en_card, t.visible_en_filtros, t.visible_en_nombre,
                t.ayuda,
            ),
        )
        row = cur.fetchone()
        if row and row["inserted"]:
            stats["inserted"] += 1
        else:
            stats["updated"] += 1
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# equipos (con M2M categorias/etiquetas)
# ─────────────────────────────────────────────────────────────────────────────


def import_equipos(
    conn,
    rows: list[dict],
    resolver: KeyResolver,
    dry_run: bool = False,
    prune_m2m: bool = False,
) -> dict[str, int]:
    """Upsert de equipos por slug + sync de M2M categorias/etiquetas.

    Args:
        prune_m2m: si True, borra las relaciones M2M existentes que no
            estén en el JSON. Default False (preserva custom).
    """
    items = _validate_rows(rows, schema.Equipo, "equipos")
    stats = {"inserted": 0, "updated": 0, "skipped": 0}
    if dry_run:
        return stats

    for eq in items:
        brand_id = resolver.marca_id(eq.marca_nombre)
        # marca legacy: si marca_nombre viene seteada, lo usamos como `marca` TEXT.
        # Esto mantiene compat con código que lee `equipos.marca` directo.
        marca_text = eq.marca or eq.marca_nombre

        cur = conn.execute(
            """
            INSERT INTO equipos (
                slug, nombre, marca, modelo, brand_id, cantidad,
                precio_jornada, precio_jornada_manual, precio_usd, roi_pct,
                valor_reposicion, foto_url, fecha_compra, serie, bh_url,
                dueno, visible_catalogo, estado, ficha_completa, eliminado_at,
                nombre_publico_override, nombre_publico_revisado, relevancia_manual
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (slug) DO UPDATE SET
                nombre = EXCLUDED.nombre,
                marca = EXCLUDED.marca,
                modelo = EXCLUDED.modelo,
                brand_id = EXCLUDED.brand_id,
                cantidad = EXCLUDED.cantidad,
                precio_jornada = EXCLUDED.precio_jornada,
                precio_jornada_manual = EXCLUDED.precio_jornada_manual,
                precio_usd = EXCLUDED.precio_usd,
                roi_pct = EXCLUDED.roi_pct,
                valor_reposicion = EXCLUDED.valor_reposicion,
                foto_url = EXCLUDED.foto_url,
                fecha_compra = EXCLUDED.fecha_compra,
                serie = EXCLUDED.serie,
                bh_url = EXCLUDED.bh_url,
                dueno = EXCLUDED.dueno,
                visible_catalogo = EXCLUDED.visible_catalogo,
                estado = EXCLUDED.estado,
                ficha_completa = EXCLUDED.ficha_completa,
                eliminado_at = EXCLUDED.eliminado_at,
                nombre_publico_override = EXCLUDED.nombre_publico_override,
                nombre_publico_revisado = EXCLUDED.nombre_publico_revisado,
                relevancia_manual = EXCLUDED.relevancia_manual,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id, (xmax = 0) AS inserted
            """,
            (
                eq.slug, eq.nombre, marca_text, eq.modelo, brand_id, eq.cantidad,
                eq.precio_jornada, eq.precio_jornada_manual, eq.precio_usd,
                eq.roi_pct, eq.valor_reposicion, eq.foto_url, eq.fecha_compra,
                eq.serie, eq.bh_url, eq.dueno, eq.visible_catalogo, eq.estado,
                eq.ficha_completa, eq.eliminado_at, eq.nombre_publico_override,
                eq.nombre_publico_revisado, eq.relevancia_manual,
            ),
        )
        row = cur.fetchone()
        equipo_id = row["id"]
        if row["inserted"]:
            stats["inserted"] += 1
        else:
            stats["updated"] += 1

        # Refresh equipo cache para el resto del batch
        if resolver._equipos is not None:
            resolver._equipos[eq.slug] = equipo_id

        # ── M2M: categorias ──────────────────────────────────────────────
        if prune_m2m:
            conn.execute(
                "DELETE FROM equipo_categorias WHERE equipo_id = ?", (equipo_id,)
            )
        for cat_ref in eq.categorias:
            cat_id = resolver.categoria_id(cat_ref.nombre)
            if cat_id is None:
                raise ImportError_(
                    f"equipos[{eq.slug}].categorias: '{cat_ref.nombre}' no existe"
                )
            conn.execute(
                """
                INSERT INTO equipo_categorias (equipo_id, categoria_id, orden)
                VALUES (?, ?, ?)
                ON CONFLICT (equipo_id, categoria_id) DO UPDATE SET
                    orden = EXCLUDED.orden
                """,
                (equipo_id, cat_id, cat_ref.orden),
            )

        # ── M2M: etiquetas ───────────────────────────────────────────────
        if prune_m2m:
            conn.execute(
                "DELETE FROM equipo_etiquetas WHERE equipo_id = ?", (equipo_id,)
            )
        for et_ref in eq.etiquetas:
            et_id = resolver.etiqueta_id(et_ref.nombre)
            if et_id is None:
                # Auto-crear etiqueta si no existe (más permisivo)
                conn.execute(
                    """
                    INSERT INTO etiquetas (nombre, prioridad)
                    VALUES (?, 100)
                    ON CONFLICT (nombre) DO NOTHING
                    """,
                    (et_ref.nombre,),
                )
                resolver.refresh_etiquetas()
                et_id = resolver.etiqueta_id(et_ref.nombre)
                if et_id is None:
                    raise ImportError_(
                        f"equipos[{eq.slug}].etiquetas: no se pudo crear '{et_ref.nombre}'"
                    )
            conn.execute(
                """
                INSERT INTO equipo_etiquetas (equipo_id, etiqueta_id, origen, orden)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (equipo_id, etiqueta_id) DO UPDATE SET
                    origen = EXCLUDED.origen,
                    orden = EXCLUDED.orden
                """,
                (equipo_id, et_id, et_ref.origen, et_ref.orden),
            )
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# equipo_specs
# ─────────────────────────────────────────────────────────────────────────────


def import_equipo_specs(
    conn, rows: list[dict], resolver: KeyResolver, dry_run: bool = False
) -> dict[str, int]:
    items = _validate_rows(rows, schema.EquipoSpec, "equipo_specs")
    stats = {"inserted": 0, "updated": 0, "skipped": 0}
    if dry_run:
        return stats
    for es in items:
        equipo_id = resolver.equipo_id(es.equipo_slug)
        if equipo_id is None:
            raise ImportError_(
                f"equipo_specs: equipo_slug='{es.equipo_slug}' no existe"
            )
        spec_id = resolver.spec_def_id(
            es.spec_ref.categoria_raiz_nombre, es.spec_ref.spec_key
        )
        if spec_id is None:
            raise ImportError_(
                f"equipo_specs: spec_ref={es.spec_ref!r} no existe "
                f"(equipo_slug={es.equipo_slug})"
            )
        cur = conn.execute(
            """
            INSERT INTO equipo_specs (equipo_id, spec_def_id, value)
            VALUES (?, ?, ?)
            ON CONFLICT (equipo_id, spec_def_id) DO UPDATE SET
                value = EXCLUDED.value
            RETURNING (xmax = 0) AS inserted
            """,
            (equipo_id, spec_id, es.value),
        )
        row = cur.fetchone()
        if row and row["inserted"]:
            stats["inserted"] += 1
        else:
            stats["updated"] += 1
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# equipo_fichas
# ─────────────────────────────────────────────────────────────────────────────


def import_equipo_fichas(
    conn, rows: list[dict], resolver: KeyResolver, dry_run: bool = False
) -> dict[str, int]:
    items = _validate_rows(rows, schema.EquipoFicha, "equipo_fichas")
    stats = {"inserted": 0, "updated": 0, "skipped": 0}
    if dry_run:
        return stats
    for f in items:
        equipo_id = resolver.equipo_id(f.equipo_slug)
        if equipo_id is None:
            raise ImportError_(
                f"equipo_fichas: equipo_slug='{f.equipo_slug}' no existe"
            )
        cur = conn.execute(
            """
            INSERT INTO equipo_fichas (
                equipo_id, descripcion, notas, specs_json, montura, formato,
                resolucion, keywords_json, nombre_publico_template, peso,
                dimensiones, alimentacion, incluye_json, conectividad_json,
                compatible_con_json, video_url, precio_bh_usd, fuente_url,
                fuente_titulo, raw_json, enriquecido_at, enriquecido_fuente
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (equipo_id) DO UPDATE SET
                descripcion = EXCLUDED.descripcion,
                notas = EXCLUDED.notas,
                specs_json = EXCLUDED.specs_json,
                montura = EXCLUDED.montura,
                formato = EXCLUDED.formato,
                resolucion = EXCLUDED.resolucion,
                keywords_json = EXCLUDED.keywords_json,
                nombre_publico_template = EXCLUDED.nombre_publico_template,
                peso = EXCLUDED.peso,
                dimensiones = EXCLUDED.dimensiones,
                alimentacion = EXCLUDED.alimentacion,
                incluye_json = EXCLUDED.incluye_json,
                conectividad_json = EXCLUDED.conectividad_json,
                compatible_con_json = EXCLUDED.compatible_con_json,
                video_url = EXCLUDED.video_url,
                precio_bh_usd = EXCLUDED.precio_bh_usd,
                fuente_url = EXCLUDED.fuente_url,
                fuente_titulo = EXCLUDED.fuente_titulo,
                raw_json = EXCLUDED.raw_json,
                enriquecido_at = EXCLUDED.enriquecido_at,
                enriquecido_fuente = EXCLUDED.enriquecido_fuente,
                updated_at = CURRENT_TIMESTAMP
            RETURNING (xmax = 0) AS inserted
            """,
            (
                equipo_id, f.descripcion, f.notas, f.specs_json, f.montura,
                f.formato, f.resolucion, f.keywords_json,
                f.nombre_publico_template, f.peso, f.dimensiones,
                f.alimentacion, f.incluye_json, f.conectividad_json,
                f.compatible_con_json, f.video_url, f.precio_bh_usd,
                f.fuente_url, f.fuente_titulo, f.raw_json, f.enriquecido_at,
                f.enriquecido_fuente,
            ),
        )
        row = cur.fetchone()
        if row and row["inserted"]:
            stats["inserted"] += 1
        else:
            stats["updated"] += 1
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch
# ─────────────────────────────────────────────────────────────────────────────

IMPORTERS = {
    "marcas": import_marcas,
    "categorias": import_categorias,
    "etiquetas": import_etiquetas,
    "spec_definitions": import_spec_definitions,
    "categoria_spec_templates": import_categoria_spec_templates,
    "equipos": import_equipos,
    "equipo_specs": import_equipo_specs,
    "equipo_fichas": import_equipo_fichas,
}
