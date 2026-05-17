"""
seeds/compat_config.py — Configuración central del sistema de compatibilidad
+ helpers compartidos para los seeds de equipo.

Declara qué specs participan en el motor de compat (`_compute_compat`):

- COMPAT_SPECS: spec_key → flags globales (es_compatibilidad, compatibilidad_modo,
  enum_options para 'jerarquia').
- ROL_POR_CATEGORIA: (categoria, spec_key) → rol ("contenedor" | "contenido").
  Solo aplica para specs con modo "jerarquia".

Cada seed importa de acá y ejecuta `apply_compat_config(conn, spec_def_ids)`
después de crear sus spec_definitions, y `apply_rol_compat(conn, ...)` después
de los categoria_spec_templates.

Modelo (de specs.py):
- modo="exacta": match si A.value == B.value (tipo, lens_mount, diametro_filtro)
- modo="jerarquia": usa enum_options como escala ordenada (chico → grande).
  Si A y B tienen roles distintos (contenedor proyecta, contenido recibe):
    - contenedor.pos >= contenido.pos → "match_con_crop" (FF en APS-C: usa crop)
    - contenedor.pos <  contenido.pos → "partial_vignette" (APS-C en FF: viñetea)
"""

# spec_key → {es_compatibilidad, compatibilidad_modo, [enum_order para jerarquia]}
COMPAT_SPECS: dict[str, dict] = {
    # Match exacto: la rosca de la montura es la rosca. No hay "casi compatible".
    "lens_mount": {
        "es_compatibilidad": True,
        "compatibilidad_modo": "exacta",
    },
    # Match exacto: 82mm filter rosquea solo en lente con frente 82mm.
    "diametro_filtro": {
        "es_compatibilidad": True,
        "compatibilidad_modo": "exacta",
    },
    # Jerarquía: el orden define qué es "más grande". Un lente Full-frame
    # proyecta sobre sensor APS-C (crop usable). Un lente APS-C en sensor FF
    # viñetea. El motor resuelve esto vía rol contenedor/contenido.
    "formato": {
        "es_compatibilidad": True,
        "compatibilidad_modo": "jerarquia",
        # Orden de chico → grande. Quien quiera agregar valores, pongalo en su
        # posición correcta en la escala.
        "enum_order": ["1\"", "MFT", "M4/3", "APS-C", "Super 35", "Full-frame", "Medium Format"],
    },
}

# Enum canónico de `formato` — usado tanto por spec_templates.py (Cámaras, Lentes)
# como por el motor de compat. Single source of truth para evitar drift.
FORMATO_ENUM: list[str] = COMPAT_SPECS["formato"]["enum_order"]

# Roles por categoría: quién PROYECTA la imagen (contenedor) vs quién la
# RECIBE (contenido). Solo aplica a specs con modo "jerarquia".
ROL_POR_CATEGORIA: dict[tuple[str, str], str] = {
    # Lentes proyectan un círculo de imagen → contenedor
    ("Lentes", "formato"): "contenedor",
    # Cámaras tienen un sensor que recibe → contenido
    ("Cámaras", "formato"): "contenido",
}


def ensure_categoria_raiz(conn, nombre: str, prioridad: int = 100, dry_run: bool = False) -> int | None:
    """Garantiza que una categoría raíz exista. Si existe pero como sub-cat
    (parent_id != NULL), la promueve a raíz. Si no existe, la crea.

    Devuelve el id de la raíz, o None en dry_run cuando no había nada previo.
    """
    row = conn.execute(
        "SELECT id, parent_id FROM categorias WHERE nombre = %s", (nombre,)
    ).fetchone()
    if row:
        if row["parent_id"] is not None and not dry_run:
            # Existía como sub-cat (drift legacy) — promover a raíz.
            conn.execute(
                "UPDATE categorias SET parent_id = NULL WHERE id = %s", (row["id"],)
            )
        return row["id"]
    if dry_run:
        return None
    cur = conn.execute(
        """
        INSERT INTO categorias (nombre, prioridad, parent_id) VALUES (%s, %s, NULL)
        ON CONFLICT (nombre) DO UPDATE SET parent_id = NULL
        RETURNING id
        """,
        (nombre, prioridad),
    )
    new = cur.fetchone()
    return new[0] if isinstance(new, tuple) else (new["id"] if new else None)


def load_match_file(categoria_raiz: str) -> dict:
    """Carga `docs/equipos_match.json` si existe y devuelve el sub-dict para
    esta categoría raíz (con resoluciones manuales del usuario tras correr
    `tools/equipos_match_preview.py`).

    Estructura: { prod_id_dataset: {action, equipo_id, ...} }.

    Si el archivo no existe o no hay entry para esta categoría → {}.
    Los seeds que no encuentren mapeo caen al matching legacy por
    (marca, modelo) — preservando comportamiento anterior.
    """
    from pathlib import Path
    p = Path(__file__).parent.parent.parent / "docs" / "equipos_match.json"
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data.get(categoria_raiz, {})


def resolve_equipo_id(
    conn,
    prod_id: str,
    marca: str,
    modelo: str,
    match_map: dict,
) -> tuple[int | None, str]:
    """Resuelve a qué equipo.id corresponde un producto del dataset.

    Prioridad:
      1. `docs/equipos_match.json` entry con action=skip → devolver
         (None, "skip") — el seed NO crea ni actualiza.
      2. entry con action=update/review y equipo_id → preserva ese id
         (FKs de pedidos intactas).
      3. Match exacto en DB por (marca, modelo) — comportamiento legacy.
      4. None — el seed creará un equipo nuevo.

    Devuelve `(equipo_id_o_None, fuente)` donde fuente ∈
    {"match_file", "skip", "marca_modelo", "none"}.
    """
    m = match_map.get(prod_id)
    if m:
        action = m.get("action")
        if action == "skip":
            return None, "skip"
        if action in ("update", "review") and m.get("equipo_id"):
            return int(m["equipo_id"]), "match_file"

    existing = conn.execute(
        "SELECT id FROM equipos WHERE marca = %s AND modelo = %s LIMIT 1",
        (marca, modelo),
    ).fetchone()
    if existing:
        return existing["id"], "marca_modelo"

    return None, "none"


def write_keywords(conn, equipo_id: int, specs: dict, dry_run: bool = False) -> int:
    """Genera keywords derivadas de specs y las escribe a `equipo_fichas.keywords_json`.

    Usa `services.nombre_builder.compute_keywords()` para la generación canónica.
    Idempotente: pisa cualquier keywords_json existente con la versión derivada
    (que es el objetivo — reemplazar el LLM-output legacy).

    Devuelve cantidad de keywords escritas (0 si ninguna).
    """
    import json as _json
    import sys
    from pathlib import Path
    # Asegurar import de nombre_builder funciona tanto en backend.seeds.X como en standalone
    backend_path = Path(__file__).parent.parent
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    from services.nombre_builder import compute_keywords  # type: ignore

    keywords = compute_keywords(specs)
    if not keywords:
        return 0
    if dry_run:
        return len(keywords)

    kw_json = _json.dumps(keywords, ensure_ascii=False)
    conn.execute(
        """
        INSERT INTO equipo_fichas (equipo_id, keywords_json)
        VALUES (%s, %s)
        ON CONFLICT (equipo_id) DO UPDATE SET keywords_json = EXCLUDED.keywords_json
        """,
        (equipo_id, kw_json),
    )
    return len(keywords)


def apply_overrides(conn, prod_id: str, equipo_id: int, match_map: dict, dry_run: bool = False) -> dict[str, str]:
    """Si el match_map tiene `override_marca` / `override_modelo` para este
    producto, los aplica al equipo en DB. Útil para corregir equipos
    mal-etiquetados (ej. 'Canon Speedboster' que en realidad es Meike).

    Devuelve dict con los campos que se pisaron.
    """
    m = match_map.get(prod_id)
    if not m:
        return {}
    overrides: dict[str, str] = {}
    if m.get("override_marca"):
        overrides["marca"] = m["override_marca"]
    if m.get("override_modelo"):
        overrides["modelo"] = m["override_modelo"]
    if not overrides or dry_run:
        return overrides
    # UPDATE explícito de los campos que indica el match_file
    sets = ", ".join(f"{k} = %s" for k in overrides)
    params = list(overrides.values()) + [equipo_id]
    conn.execute(f"UPDATE equipos SET {sets} WHERE id = %s", params)
    return overrides


def apply_compat_config(
    conn,
    spec_def_ids: dict[str, int],
    dry_run: bool = False,
    *,
    expected_keys: set[str] | None = None,
) -> int:
    """Marca las specs con flags de compatibilidad. Idempotente.

    Args:
        spec_def_ids: dict {spec_key: spec_def_id} de las specs ya creadas.
        dry_run: no escribe a la DB.
        expected_keys: opcional — set de spec_keys que esta categoría DECLARA
            como suyos y por lo tanto debería tener entrada. Si una spec de
            COMPAT_SPECS está en expected_keys pero no en spec_def_ids,
            imprime warning (data quality, no falla). Útil para detectar drift
            entre el seed y compat_config.

    Devuelve cantidad de specs actualizadas.
    """
    import json as _json
    updated = 0
    for spec_key, cfg in COMPAT_SPECS.items():
        sid = spec_def_ids.get(spec_key)
        if not sid or sid == -1:
            if expected_keys and spec_key in expected_keys:
                print(
                    f"  ⚠ compat_config: spec '{spec_key}' esperada pero no "
                    f"encontrada en spec_def_ids. Verificá el seed."
                )
            continue
        if dry_run:
            updated += 1
            continue

        # Para jerarquía: merge enum_order con cualquier enum_options legacy
        # en la DB. NO pisamos: agregamos valores nuevos y preservamos el orden
        # canónico de enum_order, anexando al final cualquier valor legacy
        # extra (típicamente data antigua que no entró en el orden canónico).
        if cfg.get("compatibilidad_modo") == "jerarquia" and cfg.get("enum_order"):
            row = conn.execute(
                "SELECT enum_options FROM spec_definitions WHERE id = %s", (sid,)
            ).fetchone()
            existing = row["enum_options"] if row else None
            if isinstance(existing, str):
                try:
                    existing = _json.loads(existing)
                except Exception:
                    existing = None
            canonical = list(cfg["enum_order"])
            if isinstance(existing, list):
                extras = [v for v in existing if v not in canonical]
                if extras:
                    print(
                        f"  ℹ compat_config: '{spec_key}' tenía valores legacy "
                        f"no en enum_order canónico: {extras}. Se anexan al final."
                    )
                canonical = canonical + extras
            conn.execute(
                """
                UPDATE spec_definitions
                SET es_compatibilidad   = %s,
                    compatibilidad_modo = %s,
                    enum_options        = %s
                WHERE id = %s
                """,
                (
                    cfg["es_compatibilidad"],
                    cfg["compatibilidad_modo"],
                    _json.dumps(canonical),
                    sid,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE spec_definitions
                SET es_compatibilidad   = %s,
                    compatibilidad_modo = %s
                WHERE id = %s
                """,
                (cfg["es_compatibilidad"], cfg["compatibilidad_modo"], sid),
            )
        updated += 1
    return updated


def apply_rol_compat(
    conn,
    categoria: str,
    spec_def_ids: dict[str, int],
    categoria_id: int,
    dry_run: bool = False,
) -> int:
    """Setea `rol_compatibilidad` en categoria_spec_templates para las specs
    jerárquicas de esta categoría. Idempotente.

    Warning si no se encontró ninguna entry — típicamente significa que la
    categoría fue renombrada desde admin y el mapping `ROL_POR_CATEGORIA`
    quedó desactualizado.
    """
    # ¿Hay alguna entry para esta categoría en el mapping?
    if not any(cat == categoria for (cat, _) in ROL_POR_CATEGORIA):
        return 0  # nada esperado para esta categoría — OK

    updated = 0
    matched_any = False
    for (cat, spec_key), rol in ROL_POR_CATEGORIA.items():
        if cat != categoria:
            continue
        sid = spec_def_ids.get(spec_key)
        if not sid or sid == -1:
            continue
        matched_any = True
        if dry_run:
            updated += 1
            continue
        cur = conn.execute(
            """
            UPDATE categoria_spec_templates
            SET rol_compatibilidad = %s
            WHERE categoria_id = %s AND spec_def_id = %s
            """,
            (rol, categoria_id, sid),
        )
        # En psycopg/sqlite-wrapper, fetch rowcount es opcional. Asumimos OK.
        updated += 1

    if not matched_any and not dry_run:
        print(
            f"  ⚠ compat_config: ROL_POR_CATEGORIA tiene entradas para "
            f"'{categoria}' pero ninguna matcheó specs reales. ¿Categoría "
            f"renombrada? Revisá compat_config.ROL_POR_CATEGORIA."
        )
    return updated
