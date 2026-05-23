"""dataio/exporters.py — DB → list[dict] por entidad.

Cada función `export_<entidad>(conn)` devuelve una lista de dicts validados
contra el modelo Pydantic correspondiente (definido en `schema.py`).

Convenciones:
- IDs SERIAL se reemplazan por la clave natural correspondiente.
- FKs se resuelven a nombres / paths legibles.
- Campos runtime (timestamps de auto-update, scores calculados,
  popularidad, etc.) se omiten — son estado local del ambiente, no
  configuración portable.
- Las filas se devuelven ordenadas por su clave natural para producir
  diffs estables en git.
"""

from __future__ import annotations

from typing import Any

from . import schema


def _to_iso(v: Any) -> str | None:
    """Convierte un datetime de psycopg2 a string ISO. None passthrough."""
    if v is None:
        return None
    if isinstance(v, str):
        return v
    iso = getattr(v, "isoformat", None)
    return iso() if callable(iso) else str(v)


# ─────────────────────────────────────────────────────────────────────────────
# marcas
# ─────────────────────────────────────────────────────────────────────────────


def export_marcas(conn) -> list[dict]:
    rows = conn.execute("""
        SELECT nombre, logo_url, visible, orden,
               COALESCE(destacada, FALSE) AS destacada
        FROM marcas
        ORDER BY nombre
    """).fetchall()
    return [
        schema.Marca(
            nombre=r["nombre"],
            logo_url=r["logo_url"],
            visible=bool(r["visible"]),
            orden=int(r["orden"]),
            destacada=bool(r["destacada"]),
        ).model_dump()
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# categorias (con parent_path resuelto a nombre del padre)
# ─────────────────────────────────────────────────────────────────────────────


def export_categorias(conn) -> list[dict]:
    rows = conn.execute("""
        SELECT c.nombre, c.prioridad, c.visible, c.grupo_visual,
               c.nombre_publico_template, p.nombre AS parent_nombre
        FROM categorias c
        LEFT JOIN categorias p ON p.id = c.parent_id
        ORDER BY c.nombre
    """).fetchall()
    return [
        schema.Categoria(
            nombre=r["nombre"],
            parent_path=r["parent_nombre"],
            prioridad=int(r["prioridad"]),
            visible=bool(r["visible"]),
            grupo_visual=r["grupo_visual"],
            nombre_publico_template=r["nombre_publico_template"],
        ).model_dump()
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# etiquetas
# ─────────────────────────────────────────────────────────────────────────────


def export_etiquetas(conn) -> list[dict]:
    rows = conn.execute("""
        SELECT nombre, prioridad
        FROM etiquetas
        ORDER BY nombre
    """).fetchall()
    return [
        schema.Etiqueta(
            nombre=r["nombre"],
            prioridad=int(r["prioridad"]),
        ).model_dump()
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# spec_definitions
# ─────────────────────────────────────────────────────────────────────────────


def export_spec_definitions(conn) -> list[dict]:
    rows = conn.execute("""
        SELECT sd.spec_key, sd.label, sd.tipo, sd.unidad, sd.enum_options,
               sd.ayuda, sd.es_compatibilidad, sd.compatibilidad_modo,
               sd.rol_compatibilidad, sd.validado, sd.tabla_columnas,
               sd.output_config, sd.favorito, sd.en_nombre, sd.en_filtros,
               sd.prioridad, c.nombre AS categoria_raiz_nombre
        FROM spec_definitions sd
        LEFT JOIN categorias c ON c.id = sd.categoria_raiz_id
        ORDER BY COALESCE(c.nombre, ''), sd.spec_key
    """).fetchall()
    return [
        schema.SpecDefinition(
            categoria_raiz_nombre=r["categoria_raiz_nombre"],
            spec_key=r["spec_key"],
            label=r["label"],
            tipo=r["tipo"],
            unidad=r["unidad"],
            enum_options=r["enum_options"],
            ayuda=r["ayuda"],
            es_compatibilidad=bool(r["es_compatibilidad"]),
            compatibilidad_modo=r["compatibilidad_modo"] or "exacta",
            rol_compatibilidad=r["rol_compatibilidad"],
            validado=bool(r["validado"]),
            tabla_columnas=r["tabla_columnas"],
            output_config=r["output_config"],
            favorito=bool(r["favorito"]),
            en_nombre=bool(r["en_nombre"]),
            en_filtros=bool(r["en_filtros"]),
            prioridad=int(r["prioridad"]),
        ).model_dump()
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# categoria_spec_templates
# ─────────────────────────────────────────────────────────────────────────────


def export_categoria_spec_templates(conn) -> list[dict]:
    rows = conn.execute("""
        SELECT cat.nombre AS categoria_nombre,
               sd.spec_key,
               raiz.nombre AS spec_categoria_raiz_nombre,
               cst.prioridad, cst.destacado, cst.obligatorio,
               cst.visible_en_card, cst.visible_en_filtros,
               cst.visible_en_nombre, cst.ayuda
        FROM categoria_spec_templates cst
        JOIN categorias cat ON cat.id = cst.categoria_id
        JOIN spec_definitions sd ON sd.id = cst.spec_def_id
        LEFT JOIN categorias raiz ON raiz.id = sd.categoria_raiz_id
        ORDER BY cat.nombre, sd.spec_key
    """).fetchall()
    return [
        schema.CategoriaSpecTemplate(
            categoria_nombre=r["categoria_nombre"],
            spec_ref=schema.SpecRef(
                categoria_raiz_nombre=r["spec_categoria_raiz_nombre"],
                spec_key=r["spec_key"],
            ),
            prioridad=int(r["prioridad"] or 100),
            destacado=bool(r["destacado"]),
            obligatorio=bool(r["obligatorio"]),
            visible_en_card=bool(r["visible_en_card"]),
            visible_en_filtros=bool(r["visible_en_filtros"]),
            visible_en_nombre=bool(r["visible_en_nombre"]),
            ayuda=r["ayuda"],
        ).model_dump()
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# equipos (con M2M categorias/etiquetas embebidas)
# ─────────────────────────────────────────────────────────────────────────────


def _ensure_equipos_slug(conn) -> None:
    """Self-heal: si la columna `equipos.slug` no existe (porque alembic
    upgrade falló o nunca corrió), la creamos y poblamos los slugs faltantes.

    Idempotente: no toca nada si la columna ya existe con todos los slugs.
    Esto es defensivo para deploys donde la migración e4a7c1f8d6b2 quedó
    sin aplicar — sin esto, todo el export y catálogo dataio queda roto.
    """
    has_slug = conn.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'equipos' AND column_name = 'slug'
        ) AS x
    """).fetchone()["x"]
    changed = False
    if not has_slug:
        conn.execute("ALTER TABLE equipos ADD COLUMN slug VARCHAR(80)")
        changed = True

    # Poblar slugs faltantes (también cubre el caso "columna existía pero
    # init-slugs nunca corrió").
    pending = conn.execute("""
        SELECT id, nombre, (SELECT nombre FROM marcas WHERE id = equipos.brand_id) AS marca, modelo FROM equipos
        WHERE slug IS NULL AND eliminado_at IS NULL
    """).fetchall()
    if pending:
        from .slug import equipo_slug
        existing = {
            r["slug"] for r in conn.execute(
                "SELECT slug FROM equipos WHERE slug IS NOT NULL"
            ).fetchall()
        }
        for r in pending:
            base = equipo_slug(r["marca"], r["modelo"], r["nombre"]) or f"equipo-{r['id']}"
            slug = base
            n = 1
            while slug in existing:
                n += 1
                slug = f"{base}-{n}"
            existing.add(slug)
            conn.execute("UPDATE equipos SET slug = ? WHERE id = ?", (slug, r["id"]))
        changed = True

    # Asegurar el UNIQUE constraint completo (consistente con migración
    # f5b8d2e4a9c1, no el partial index transicional). Idempotente.
    conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'equipos_slug_key' AND conrelid = 'equipos'::regclass
            ) AND NOT EXISTS (
                SELECT 1 FROM equipos WHERE slug IS NOT NULL
                GROUP BY slug HAVING COUNT(*) > 1
            ) THEN
                ALTER TABLE equipos ADD CONSTRAINT equipos_slug_key UNIQUE (slug);
                DROP INDEX IF EXISTS idx_equipos_slug_unique;
            END IF;
        END $$;
    """)
    changed = True

    if changed:
        conn.commit()


def export_equipos(conn) -> list[dict]:
    """Exporta equipos con slug como clave natural.

    Auto-cura el slug si falta (columna o valor). Esto es defensivo:
    en deploys donde la migración de Alembic no se aplicó, el export
    seguía roto hasta intervención manual.
    """
    _ensure_equipos_slug(conn)

    rows = conn.execute("""
        SELECT e.slug, e.nombre, (SELECT nombre FROM marcas WHERE id = e.brand_id) AS marca, e.modelo, e.cantidad,
               e.precio_jornada, e.precio_jornada_manual, e.precio_usd,
               e.roi_pct, e.valor_reposicion, e.foto_url, e.fecha_compra,
               e.serie, e.bh_url, e.dueno, e.visible_catalogo, e.estado,
               e.ficha_completa, e.eliminado_at, e.nombre_publico_override,
               e.nombre_publico_revisado, e.relevancia_manual,
               m.nombre AS marca_nombre
        FROM equipos e
        LEFT JOIN marcas m ON m.id = e.brand_id
        WHERE e.slug IS NOT NULL
        ORDER BY e.slug
    """).fetchall()
    if not rows:
        return []

    equipo_ids = [r["slug"] for r in rows]
    # Cargar M2M en batch para no hacer N+1 queries
    slug_by_id = {}
    id_rows = conn.execute("""
        SELECT id, slug FROM equipos WHERE slug IS NOT NULL
    """).fetchall()
    for ir in id_rows:
        slug_by_id[ir["id"]] = ir["slug"]

    cat_rows = conn.execute("""
        SELECT ec.equipo_id, c.nombre AS cat_nombre, ec.orden
        FROM equipo_categorias ec
        JOIN categorias c ON c.id = ec.categoria_id
        JOIN equipos e ON e.id = ec.equipo_id
        WHERE e.slug IS NOT NULL
        ORDER BY ec.equipo_id, ec.orden, c.nombre
    """).fetchall()
    cats_by_slug: dict[str, list[schema.EquipoCategoriaRef]] = {}
    for r in cat_rows:
        s = slug_by_id.get(r["equipo_id"])
        if not s:
            continue
        cats_by_slug.setdefault(s, []).append(
            schema.EquipoCategoriaRef(nombre=r["cat_nombre"], orden=int(r["orden"] or 0))
        )

    et_rows = conn.execute("""
        SELECT ee.equipo_id, et.nombre AS et_nombre, ee.origen, ee.orden
        FROM equipo_etiquetas ee
        JOIN etiquetas et ON et.id = ee.etiqueta_id
        JOIN equipos e ON e.id = ee.equipo_id
        WHERE e.slug IS NOT NULL
        ORDER BY ee.equipo_id, ee.orden, et.nombre
    """).fetchall()
    ets_by_slug: dict[str, list[schema.EquipoEtiquetaRef]] = {}
    for r in et_rows:
        s = slug_by_id.get(r["equipo_id"])
        if not s:
            continue
        origen = r["origen"] if r["origen"] in ("auto", "manual") else "manual"
        ets_by_slug.setdefault(s, []).append(
            schema.EquipoEtiquetaRef(
                nombre=r["et_nombre"],
                origen=origen,  # type: ignore[arg-type]
                orden=int(r["orden"] or 0),
            )
        )

    out: list[dict] = []
    for r in rows:
        slug = r["slug"]
        out.append(
            schema.Equipo(
                slug=slug,
                nombre=r["nombre"],
                marca=r["marca"],
                modelo=r["modelo"],
                marca_nombre=r["marca_nombre"],
                cantidad=int(r["cantidad"] or 1),
                precio_jornada=r["precio_jornada"],
                precio_jornada_manual=bool(r["precio_jornada_manual"]),
                precio_usd=r["precio_usd"],
                roi_pct=r["roi_pct"],
                valor_reposicion=r["valor_reposicion"],
                foto_url=r["foto_url"],
                fecha_compra=_to_iso(r["fecha_compra"]),
                serie=r["serie"],
                bh_url=r["bh_url"],
                dueno=r["dueno"],
                visible_catalogo=int(r["visible_catalogo"] or 0),
                estado=r["estado"] or "ok",
                ficha_completa=bool(r["ficha_completa"]),
                eliminado_at=_to_iso(r["eliminado_at"]),
                nombre_publico_override=r["nombre_publico_override"],
                nombre_publico_revisado=bool(r["nombre_publico_revisado"]),
                relevancia_manual=int(r["relevancia_manual"] or 100),
                categorias=cats_by_slug.get(slug, []),
                etiquetas=ets_by_slug.get(slug, []),
            ).model_dump()
        )
    return out


# ─────────────────────────────────────────────────────────────────────────────
# equipo_specs
# ─────────────────────────────────────────────────────────────────────────────


def export_equipo_specs(conn) -> list[dict]:
    rows = conn.execute("""
        SELECT e.slug AS equipo_slug,
               sd.spec_key,
               raiz.nombre AS spec_categoria_raiz_nombre,
               es.value
        FROM equipo_specs es
        JOIN equipos e ON e.id = es.equipo_id
        JOIN spec_definitions sd ON sd.id = es.spec_def_id
        LEFT JOIN categorias raiz ON raiz.id = sd.categoria_raiz_id
        WHERE e.slug IS NOT NULL
        ORDER BY e.slug, sd.spec_key
    """).fetchall()
    return [
        schema.EquipoSpec(
            equipo_slug=r["equipo_slug"],
            spec_ref=schema.SpecRef(
                categoria_raiz_nombre=r["spec_categoria_raiz_nombre"],
                spec_key=r["spec_key"],
            ),
            value=r["value"],
        ).model_dump()
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# equipo_fichas
# ─────────────────────────────────────────────────────────────────────────────


def export_equipo_fichas(conn) -> list[dict]:
    rows = conn.execute("""
        SELECT e.slug AS equipo_slug, ef.*
        FROM equipo_fichas ef
        JOIN equipos e ON e.id = ef.equipo_id
        WHERE e.slug IS NOT NULL
        ORDER BY e.slug
    """).fetchall()
    out: list[dict] = []
    for r in rows:
        out.append(
            schema.EquipoFicha(
                equipo_slug=r["equipo_slug"],
                descripcion=r["descripcion"],
                notas=r["notas"],
                specs_json=r["specs_json"],
                montura=r["montura"],
                formato=r["formato"],
                resolucion=r["resolucion"],
                keywords_json=r["keywords_json"],
                nombre_publico_template=r["nombre_publico_template"],
                peso=r["peso"],
                dimensiones=r["dimensiones"],
                alimentacion=r["alimentacion"],
                incluye_json=r["incluye_json"],
                conectividad_json=r["conectividad_json"],
                compatible_con_json=r["compatible_con_json"],
                video_url=r["video_url"],
                precio_bh_usd=r["precio_bh_usd"],
                fuente_url=r["fuente_url"],
                fuente_titulo=r["fuente_titulo"],
                raw_json=r["raw_json"],
                enriquecido_at=_to_iso(r["enriquecido_at"]),
                enriquecido_fuente=r["enriquecido_fuente"],
            ).model_dump()
        )
    return out


# ─────────────────────────────────────────────────────────────────────────────
# OPERATIONAL — clientes, alquileres (con items/pagos embebidos)
# ─────────────────────────────────────────────────────────────────────────────


def export_clientes(conn) -> list[dict]:
    rows = conn.execute("""
        SELECT email, nombre, apellido, telefono, direccion, direccion_maps_url,
               cuit, descuento, perfil_impuestos, razon_social, domicilio_fiscal,
               email_facturacion, notas, supabase_uid
        FROM clientes
        WHERE email IS NOT NULL
        ORDER BY LOWER(email)
    """).fetchall()
    out: list[dict] = []
    for r in rows:
        out.append(
            schema.Cliente(
                email=r["email"],
                nombre=r["nombre"],
                apellido=r["apellido"],
                telefono=r["telefono"],
                direccion=r["direccion"],
                direccion_maps_url=r["direccion_maps_url"],
                cuit=r["cuit"],
                descuento=float(r["descuento"] or 0.0),
                perfil_impuestos=r["perfil_impuestos"] or "consumidor_final",
                razon_social=r["razon_social"],
                domicilio_fiscal=r["domicilio_fiscal"],
                email_facturacion=r["email_facturacion"],
                notas=r["notas"],
                supabase_uid=str(r["supabase_uid"]) if r["supabase_uid"] else None,
            ).model_dump()
        )
    return out


def export_alquileres(conn) -> list[dict]:
    """Exporta alquileres con items y pagos embebidos.

    Filtra los que no tienen numero_pedido (legacy sin nro) — no son
    re-importables sin clave natural. Si los necesitás, generales un
    numero_pedido antes vía un script de mantenimiento.
    """
    rows = conn.execute("""
        SELECT a.numero_pedido, a.cliente_nombre, a.cliente_telefono,
               a.estado, a.fecha_desde, a.fecha_hasta, a.monto_total,
               a.monto_pagado, a.descuento_pct, a.notas, a.fuente,
               a.id AS alquiler_id,
               c.email AS cliente_email
        FROM alquileres a
        LEFT JOIN clientes c ON c.id = a.cliente_id
        WHERE a.numero_pedido IS NOT NULL
        ORDER BY a.numero_pedido
    """).fetchall()
    if not rows:
        return []

    alquiler_ids = [r["alquiler_id"] for r in rows]
    # Items con equipo_slug en batch
    items_by_alq: dict[int, list[schema.AlquilerItemRef]] = {}
    item_rows = conn.execute("""
        SELECT ai.pedido_id, e.slug AS equipo_slug, ai.cantidad,
               ai.precio_jornada, ai.subtotal
        FROM alquiler_items ai
        JOIN equipos e ON e.id = ai.equipo_id
        WHERE ai.pedido_id = ANY(%s) AND e.slug IS NOT NULL
        ORDER BY ai.pedido_id, ai.id
    """, (alquiler_ids,)).fetchall()
    for ir in item_rows:
        items_by_alq.setdefault(ir["pedido_id"], []).append(
            schema.AlquilerItemRef(
                equipo_slug=ir["equipo_slug"],
                cantidad=int(ir["cantidad"] or 1),
                precio_jornada=int(ir["precio_jornada"] or 0),
                subtotal=int(ir["subtotal"] or 0),
            )
        )

    # Pagos en batch
    pagos_by_alq: dict[int, list[schema.AlquilerPagoRef]] = {}
    pago_rows = conn.execute("""
        SELECT pedido_id, monto, concepto, fecha
        FROM alquiler_pagos
        WHERE pedido_id = ANY(%s)
        ORDER BY pedido_id, fecha, id
    """, (alquiler_ids,)).fetchall()
    for pr in pago_rows:
        pagos_by_alq.setdefault(pr["pedido_id"], []).append(
            schema.AlquilerPagoRef(
                monto=int(pr["monto"]),
                concepto=pr["concepto"],
                fecha=_to_iso(pr["fecha"]) or "",
            )
        )

    out: list[dict] = []
    for r in rows:
        alq_id = r["alquiler_id"]
        out.append(
            schema.Alquiler(
                numero_pedido=int(r["numero_pedido"]),
                cliente_email=r["cliente_email"],
                cliente_nombre=r["cliente_nombre"],
                cliente_telefono=r["cliente_telefono"],
                estado=r["estado"] or "presupuesto",
                fecha_desde=_to_iso(r["fecha_desde"]) or "",
                fecha_hasta=_to_iso(r["fecha_hasta"]) or "",
                monto_total=int(r["monto_total"] or 0),
                monto_pagado=int(r["monto_pagado"] or 0),
                descuento_pct=float(r["descuento_pct"] or 0.0),
                notas=r["notas"],
                fuente=r["fuente"] or "sistema",
                items=items_by_alq.get(alq_id, []),
                pagos=pagos_by_alq.get(alq_id, []),
            ).model_dump()
        )
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch
# ─────────────────────────────────────────────────────────────────────────────

EXPORTERS = {
    "marcas": export_marcas,
    "categorias": export_categorias,
    "etiquetas": export_etiquetas,
    "spec_definitions": export_spec_definitions,
    "categoria_spec_templates": export_categoria_spec_templates,
    "equipos": export_equipos,
    "equipo_specs": export_equipo_specs,
    "equipo_fichas": export_equipo_fichas,
    "clientes": export_clientes,
    "alquileres": export_alquileres,
}
