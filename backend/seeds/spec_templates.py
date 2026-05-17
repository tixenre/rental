"""
seeds/spec_templates.py — Templates iniciales de specs por categoría.

Post refactor unificar_specs_definitions:
  - El seed genera dos cosas en dos pasadas:
    1. `spec_definitions` — catálogo global. Cada `spec_key` único en TEMPLATES
       se inserta una sola vez. Si el mismo spec_key aparece en varias
       categorías (ej. montura, formato), su tipo/unidad se toman de la
       primera ocurrencia y los `enum_options` se UNEN.
    2. `categoria_spec_templates` — asigna cada categoría a sus specs con sus
       flags propios (prioridad, destacado, visible_en_*, obligatorio).

Comportamiento idempotente y respeto al back-office:
  - `spec_definitions`: ON CONFLICT (spec_key) DO NOTHING. Una vez creada,
    no se pisa por seed. El admin puede editarla desde el catálogo global.
  - `categoria_spec_templates`: SOLO se pobla si la categoría no tiene ninguna
    asignación. Si el admin ya configuró algo, el seed no toca nada.

Para forzar reseed de una categoría: borrar TODAS sus asignaciones desde la
UI y reiniciar el backend; el seed la repuebla.

Convenciones del campo `tipo`:
    string     → texto libre (ej. "Full-frame CMOS 12.1MP")
    number     → numérico, con `unidad` opcional
    enum       → valor único de lista cerrada (enum_options)
    multi_enum → varios valores de lista cerrada
    bool       → sí/no
    rango      → un valor o dos separados por `-` (ej. "24-70"), unidad requerida
    wxh        → dos medidas separadas por `×` (ej. "6144×3240"), unidad requerida
    wxhxd      → tres medidas separadas por `×` (ej. "129.7×84.5×77.8"), unidad requerida
"""

import json
import sys
from pathlib import Path

try:
    from .compat_config import FORMATO_ENUM  # single source para enum jerárquico
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from compat_config import FORMATO_ENUM  # type: ignore


# ── Definición de templates por categoría raíz ──────────────────────────
#
# Estructura: { "<nombre_categoria_raiz>": [<lista de specs>, ...] }
# Cada spec es un dict con las keys de la tabla categoria_spec_templates.

TEMPLATES: dict[str, list[dict]] = {
    # 1. Cámaras — alineado a seeds/camaras.py::SPECS_CAMARAS (fuente de verdad
    # canónica). Las extras descriptivas (sensor, af_puntos, memoria_tipo, etc.)
    # viven en `equipo_specs.extras` JSON, no como spec_definitions canónicas.
    "Cámaras": [
        {"key": "tipo", "label": "Tipo", "tipo": "enum",
         "enum_options": ["Cinema Camera", "Mirrorless", "DSLR", "Vlogging",
                          "Action Camera", "Compact", "Medium Format", "Camera"],
         "prioridad": 10, "en_card": True, "en_filtros": True, "en_nombre": True,
         "destacado": True, "ayuda": "Form factor de la cámara"},
        {"key": "lens_mount", "label": "Lens mount", "tipo": "enum",
         "enum_options": ["E", "RF", "EF", "L", "Z", "X", "MFT", "PL", "BMD", "B4", "M42"],
         "prioridad": 15, "en_card": True, "en_filtros": True, "en_nombre": True,
         "destacado": True,
         "ayuda": "Null para cámaras con lente fijo (action cams, smartphones)"},
        {"key": "formato", "label": "Formato", "tipo": "enum",
         "enum_options": FORMATO_ENUM,  # ← single source en compat_config.py
         "prioridad": 20, "en_card": True, "en_filtros": True, "en_nombre": True,
         "destacado": True},
        {"key": "resolucion_max", "label": "Resolución máxima", "tipo": "enum",
         "enum_options": ["FHD", "2K", "4K", "5K", "5.7K", "6K", "8K", "12K"],
         "prioridad": 30, "en_card": True, "en_filtros": True, "en_nombre": True,
         "destacado": True},
        {"key": "fps_max", "label": "FPS máx", "tipo": "number", "unidad": "fps",
         "prioridad": 40, "en_filtros": True, "destacado": True,
         "ayuda": "Frame rate máximo en cualquier resolución"},
        {"key": "megapixels", "label": "Megapixels", "tipo": "number", "unidad": "MP",
         "prioridad": 45, "en_filtros": True},
        {"key": "codecs", "label": "Codecs principales", "tipo": "string",
         "prioridad": 60,
         "ayuda": "Ej: ProRes, REDCODE, XAVC S-I 4:2:2, XF-AVC"},
        {"key": "iso_nativo", "label": "ISO nativo", "tipo": "rango", "unidad": "ISO",
         "prioridad": 65, "en_filtros": True,
         "ayuda": "Rango nativo. Ej: 80-102400"},
        {"key": "iso_extendido", "label": "ISO extendido", "tipo": "rango", "unidad": "ISO",
         "prioridad": 67, "ayuda": "Con boost. Ej: 80-409600"},
        {"key": "rango_dinamico_stops", "label": "Rango dinámico", "tipo": "number",
         "unidad": "stops", "prioridad": 70, "en_filtros": True},
        {"key": "estabilizacion", "label": "Estabilización óptica", "tipo": "bool",
         "prioridad": 75, "en_filtros": True},
        {"key": "autofocus", "label": "Autofocus", "tipo": "bool",
         "prioridad": 80, "en_filtros": True},
        {"key": "continuous_shooting_fps", "label": "Ráfaga (stills)", "tipo": "number",
         "unidad": "fps", "prioridad": 85,
         "ayuda": "Burst rate para fotografía"},
        {"key": "fast_slow_motion", "label": "Fast/Slow motion", "tipo": "bool",
         "prioridad": 88, "ayuda": "Soporta variable frame rate / S&Q"},
        {"key": "lens_communication", "label": "Comunicación electrónica lente", "tipo": "bool",
         "prioridad": 90},
        {"key": "gps", "label": "GPS", "tipo": "bool", "prioridad": 92},
        {"key": "ip_streaming", "label": "IP Streaming", "tipo": "bool",
         "prioridad": 94, "ayuda": "Para broadcast / live streaming"},
        {"key": "netflix_approved", "label": "Netflix approved", "tipo": "bool",
         "prioridad": 96, "en_card": True, "en_filtros": True},
        {"key": "max_aperture", "label": "Apertura máxima (fixed-lens)", "tipo": "string",
         "prioridad": 97, "ayuda": "Solo para cámaras con lente fijo (GoPro, etc.)"},
        {"key": "sensor_crop", "label": "Sensor crop (35mm eq.)", "tipo": "string",
         "prioridad": 98},
        {"key": "recording_limit_min", "label": "Límite de grabación", "tipo": "number",
         "unidad": "min", "prioridad": 99,
         "ayuda": "Algunos modelos tienen tope 29min59s"},
        {"key": "peso_g", "label": "Peso", "tipo": "number", "unidad": "g",
         "prioridad": 100, "ayuda": "Cuerpo solo (sin batería ni media)"},
    ],

    # 2. Lentes — alineado a la tabla de specs de B&H (lo más rico para
    # cinematografía y foto). Las destacadas (★) marcan lo que aparece como
    # quick fact en la fila del catálogo.
    #
    # NOTA: focal_min/focal_max/apertura_max/apertura_min se SACARON del seed
    # — quedaron reemplazados por distancia_focal y apertura (ambos tipo rango)
    # que cubren fijo y zoom en un solo campo. Si tu DB ya tiene los legacy,
    # podés borrarlos desde /admin/equipos/specs sin que el seed los reinserte.
    "Lentes": [
        {"key": "lens_mount", "label": "Lens mount", "tipo": "enum",
         "enum_options": ["E", "RF", "EF", "L", "Z", "X", "MFT", "PL", "BMD", "B4", "M42"],
         "prioridad": 10, "en_card": True, "en_filtros": True, "en_nombre": True,
         "destacado": True},
        {"key": "distancia_focal", "label": "Distancia focal", "tipo": "rango",
         "unidad": "mm", "prioridad": 15, "en_card": True, "en_nombre": True,
         "destacado": True,
         "ayuda": "Un valor (ej. 50) si es fijo, dos (ej. 24-70) si es zoom"},
        {"key": "apertura", "label": "Apertura", "tipo": "rango",
         "unidad": "f/", "prioridad": 20, "en_card": True, "en_nombre": True,
         "destacado": True,
         "ayuda": "Un valor (ej. 2.8) si es fija, dos (ej. 2.8-4) si es variable"},
        {"key": "formato", "label": "Formato", "tipo": "enum",
         "enum_options": FORMATO_ENUM,  # ← single source en compat_config.py
         "prioridad": 50, "en_filtros": True, "destacado": True},
        {"key": "diametro_filtro", "label": "Diámetro de filtro", "tipo": "number",
         "unidad": "mm", "prioridad": 55,
         "ayuda": "Diámetro de la rosca del filtro frontal (ej. 67, 77, 82)"},
        {"key": "linea", "label": "Línea", "tipo": "string",
         "prioridad": 60, "ayuda": "Ej: Art, GM, Cinema, Master Prime"},
        {"key": "angulo_vision", "label": "Ángulo de visión", "tipo": "rango",
         "unidad": "°", "prioridad": 65,
         "ayuda": "Un valor si es fijo (ej. 75), dos si es zoom (ej. 84-34)"},
        {"key": "distancia_minima_m", "label": "Distancia mínima de foco", "tipo": "number",
         "unidad": "cm", "prioridad": 70},
        {"key": "magnificacion", "label": "Magnificación máxima", "tipo": "string",
         "prioridad": 75, "ayuda": "Ej: 0.32x"},
        {"key": "hojas_diafragma", "label": "Hojas de diafragma", "tipo": "number",
         "prioridad": 78},
        {"key": "estabilizacion", "label": "Estabilización óptica", "tipo": "bool",
         "prioridad": 80},
        {"key": "autofocus", "label": "Autofocus", "tipo": "bool",
         "prioridad": 90},
        {"key": "construccion_optica", "label": "Construcción óptica", "tipo": "string",
         "prioridad": 95, "ayuda": "Ej: 20 elementos / 15 grupos"},
        {"key": "peso_g", "label": "Peso", "tipo": "number", "unidad": "g",
         "prioridad": 100, "ayuda": "Ej: 695"},
        {"key": "dimensiones", "label": "Dimensiones", "tipo": "string",
         "prioridad": 105, "ayuda": "Ej: Ø87.8 × 119.9 mm"},
    ],

    # 3. Iluminación
    "Iluminación": [
        {"key": "potencia_w", "label": "Potencia", "tipo": "number", "unidad": "W",
         "prioridad": 10, "en_card": True, "en_filtros": True, "en_nombre": True},
        {"key": "lumens", "label": "Lúmenes", "tipo": "number", "unidad": "lm",
         "prioridad": 20},
        {"key": "cri", "label": "CRI", "tipo": "number",
         "prioridad": 30, "en_filtros": True,
         "ayuda": "Color Rendering Index (0-100)"},
        {"key": "temperatura_k", "label": "Temperatura color", "tipo": "string",
         "prioridad": 40, "ayuda": "Ej: 3200K-5600K o 5600K"},
        {"key": "bicolor", "label": "Bicolor", "tipo": "bool",
         "prioridad": 50, "en_filtros": True},
        {"key": "rgb", "label": "RGB", "tipo": "bool",
         "prioridad": 60, "en_filtros": True},
        {"key": "dimming", "label": "Dimmer", "tipo": "bool", "prioridad": 70},
        {"key": "control_inalambrico", "label": "Control inalámbrico", "tipo": "string",
         "prioridad": 80, "ayuda": "Ej: DMX, Lumenradio, app"},
        {"key": "alimentacion", "label": "Alimentación", "tipo": "enum",
         "enum_options": ["V-mount", "Gold Mount", "NP-F", "D-Tap", "AC", "USB-C", "Batería integrada"],
         "prioridad": 90, "en_filtros": True},
        {"key": "montaje", "label": "Montaje", "tipo": "string",
         "prioridad": 100, "ayuda": "Ej: Bowens, Profoto, fija"},
        {"key": "peso_g", "label": "Peso", "tipo": "number", "unidad": "g",
         "prioridad": 110},
    ],

    # Modificadores / Soportes / Grip / Sonido / Monitores y Video / Energía /
    # Media y Datos / Estudio y Producción → categorías reservadas en el árbol
    # (ver SEED_TREE en database.py) pero sin specs definidos hasta tener
    # productos reales. Cuando se arme cada dataset, se agregan acá según los
    # campos que aparezcan en B&H (mismo workflow que Lentes/Cámaras/Filtros).

    # Adaptadores — se vinculan a la CÁMARA (lens_mount body)
    "Adaptadores": [
        {"key": "tipo", "label": "Tipo", "tipo": "enum",
         "enum_options": ["Adaptador montura", "Speedbooster", "Macro tube"],
         "prioridad": 10, "obligatorio": True, "en_card": True, "en_nombre": True},
        {"key": "lens_mount", "label": "Lens mount", "tipo": "enum",
         "enum_options": ["E", "RF", "EF", "L", "Z", "X", "MFT", "PL", "BMD", "B4", "M42"],
         "prioridad": 20, "obligatorio": True, "en_card": True, "en_filtros": True, "en_nombre": True,
         "destacado": True,
         "ayuda": "Lado body (la rosca que se enchufa a la cámara)"},
        {"key": "lens_mount_out", "label": "Lens mount — lado lente", "tipo": "enum",
         "enum_options": ["E", "RF", "EF", "L", "Z", "X", "MFT", "PL", "BMD", "B4", "M42"],
         "prioridad": 30, "en_card": True, "en_filtros": True, "en_nombre": True,
         "destacado": True,
         "ayuda": "Rosca que recibe el lente del otro sistema"},
        {"key": "electronica", "label": "Comunicación electrónica", "tipo": "bool",
         "prioridad": 40, "en_filtros": True,
         "ayuda": "Transmite AF/aperture del lente al body"},
        {"key": "incluye_iris", "label": "Iris incluido", "tipo": "bool",
         "prioridad": 50,
         "ayuda": "Drop-in adapters con filtro ND variable incorporado (Canon EF→RF)"},
        {"key": "magnificacion", "label": "Magnificación", "tipo": "string",
         "prioridad": 60,
         "ayuda": "Solo speedboosters (ej. 0.71x — reduce focal y gana 1 stop)"},
        {"key": "peso_g", "label": "Peso", "tipo": "number", "unidad": "g",
         "prioridad": 70},
    ],

    # 9b. Filtros — se vinculan al FRENTE del lente (diametro_filtro, MISMA spec
    # que en Lentes — match automático: filtro 82mm ↔ lente con diametro_filtro=82).
    "Filtros": [
        {"key": "tipo", "label": "Tipo", "tipo": "enum",
         "enum_options": ["Filtro ND", "Filtro polarizador", "Filtro UV",
                          "Filtro variable", "Filtro difusión"],
         "prioridad": 10, "obligatorio": True, "en_card": True, "en_nombre": True,
         "destacado": True},
        {"key": "diametro_filtro", "label": "Diámetro de filtro", "tipo": "number", "unidad": "mm",
         "prioridad": 20, "obligatorio": True, "en_card": True, "en_filtros": True, "en_nombre": True,
         "destacado": True,
         "ayuda": "Rosca del filter thread (67, 77, 82, etc.). Compartido con Lentes — habilita match automático."},
        {"key": "densidad", "label": "Densidad ND", "tipo": "string",
         "prioridad": 30, "en_filtros": True,
         "ayuda": "Ej: 1.2-Stop, 2-8 Stop (variable)"},
        {"key": "material", "label": "Material", "tipo": "enum",
         "enum_options": ["Vidrio", "Resina", "Polímero"],
         "prioridad": 40,
         "ayuda": "Vidrio óptico es estándar; resina es más barato pero menos calidad"},
        {"key": "grade", "label": "Grado", "tipo": "string",
         "prioridad": 50,
         "ayuda": "Solo difusión: 1/8, 1/4, 1/2, 1, 2 (más alto = más difusión)"},
        {"key": "peso_g", "label": "Peso", "tipo": "number", "unidad": "g",
         "prioridad": 60},
    ],

    # Energía / Media y Datos / Estudio y Producción → categorías reservadas
    # en SEED_TREE, sin specs hasta tener productos reales.
}


def _collect_spec_definitions() -> dict[str, dict]:
    """Itera TEMPLATES y agrupa por spec_key, unificando metadata.

    Si el mismo spec_key aparece en varias categorías:
      - tipo / unidad / ayuda: se toma de la PRIMERA ocurrencia.
      - enum_options: UNION (preservando orden) de todas las variantes.
      - destacado / flags per-categoría: NO se mergean acá — esos quedan
        en categoria_spec_templates.
    """
    by_key: dict[str, dict] = {}
    for cat_specs in TEMPLATES.values():
        for spec in cat_specs:
            key = spec["key"]
            if key not in by_key:
                by_key[key] = {
                    "label": spec["label"],
                    "tipo": spec["tipo"],
                    "unidad": spec.get("unidad"),
                    "enum_options": list(spec.get("enum_options") or []),
                    "ayuda": spec.get("ayuda"),
                }
            elif spec.get("enum_options"):
                existing = by_key[key]
                seen = set(existing["enum_options"])
                for opt in spec["enum_options"]:
                    if opt not in seen:
                        existing["enum_options"].append(opt)
                        seen.add(opt)
    return by_key


def seed_spec_templates(conn) -> int:
    """Pasada 1: upsert spec_definitions desde TEMPLATES.
    Pasada 2: asignar a categorías SOLO si la categoría no tiene asignaciones
              configuradas (respeta el back-office como source of truth).

    Devuelve la cantidad de asignaciones nuevas insertadas."""
    inserted = 0

    # Pasada 1 — catálogo global. Idempotente vía ON CONFLICT.
    defs = _collect_spec_definitions()
    spec_def_ids: dict[str, int] = {}
    for key, info in defs.items():
        # ¿Ya existe la definición? Si sí, traemos su id sin pisar.
        row = conn.execute(
            "SELECT id FROM spec_definitions WHERE spec_key = ?", (key,)
        ).fetchone()
        if row:
            spec_def_ids[key] = row["id"]
            continue
        enum_opts_json = (
            json.dumps(info["enum_options"]) if info["enum_options"] else None
        )
        cur = conn.execute(
            """
            INSERT INTO spec_definitions
              (spec_key, label, tipo, unidad, enum_options, ayuda)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (spec_key) DO NOTHING
            RETURNING id
            """,
            (
                key,
                info["label"],
                info["tipo"],
                info["unidad"],
                enum_opts_json,
                info["ayuda"],
            ),
        )
        new_row = cur.fetchone()
        if new_row:
            spec_def_ids[key] = new_row[0]
        else:
            # Race: alguien la insertó en paralelo. Re-fetch.
            row = conn.execute(
                "SELECT id FROM spec_definitions WHERE spec_key = ?", (key,)
            ).fetchone()
            if row:
                spec_def_ids[key] = row["id"]

    # Pasada 2 — asignaciones por categoría. Solo en categorías vírgenes.
    for cat_nombre, specs in TEMPLATES.items():
        row = conn.execute(
            "SELECT id FROM categorias WHERE nombre = %s AND parent_id IS NULL",
            (cat_nombre,),
        ).fetchone()
        if not row:
            continue
        cat_id = row["id"]

        # Si la categoría ya tiene CUALQUIER asignación, el dueño la administra
        # desde el back-office — no inyectamos más.
        existing = conn.execute(
            "SELECT COUNT(*) AS n FROM categoria_spec_templates WHERE categoria_id = %s",
            (cat_id,),
        ).fetchone()
        if existing and existing["n"] > 0:
            continue

        for spec in specs:
            spec_def_id = spec_def_ids.get(spec["key"])
            if not spec_def_id:
                continue
            cur = conn.execute(
                """
                INSERT INTO categoria_spec_templates
                  (categoria_id, spec_def_id, prioridad, destacado, obligatorio,
                   visible_en_card, visible_en_filtros, visible_en_nombre, ayuda)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (categoria_id, spec_def_id) DO NOTHING
                RETURNING id
                """,
                (
                    cat_id,
                    spec_def_id,
                    spec.get("prioridad", 100),
                    spec.get("destacado", False),
                    spec.get("obligatorio", False),
                    spec.get("en_card", False),
                    spec.get("en_filtros", False),
                    spec.get("en_nombre", False),
                    spec.get("ayuda"),
                ),
            )
            if cur.fetchone() is not None:
                inserted += 1
    return inserted
