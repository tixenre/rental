"""
seeds/spec_templates.py — Templates iniciales de specs por categoría.

Cada categoría raíz tiene un template que define qué specs van a tener
sus equipos. Cuando el admin asigna una categoría a un equipo, el form
muestra los inputs según este template.

Diseño completo en docs/DISEÑO_SPECS.md sección 3.

Convenciones del campo `tipo`:
    string  →  texto libre (ej. "Full-frame CMOS 12.1MP")
    number  →  numérico, con `unidad` opcional
    enum    →  valor de una lista cerrada en `enum_options`
    bool    →  sí/no

Flags:
    visible_en_card     → aparece en la card del catálogo
    visible_en_filtros  → genera filtro en el catálogo
    visible_en_nombre   → entra en el nombre público auto-generado
    obligatorio         → required al crear el equipo

`prioridad` ordena la spec en la ficha (más bajo = más arriba). Default 100.

El seed es idempotente: usa ON CONFLICT (categoria_id, spec_key) DO NOTHING.
Si ya existe el template, NO se pisa (permite que el admin lo edite sin
que el seed lo revierta en cada arranque).
"""

import json


# ── Definición de templates por categoría raíz ──────────────────────────
#
# Estructura: { "<nombre_categoria_raiz>": [<lista de specs>, ...] }
# Cada spec es un dict con las keys de la tabla categoria_spec_templates.

TEMPLATES: dict[str, list[dict]] = {
    # 1. Cámaras
    "Cámaras": [
        {"key": "sensor", "label": "Sensor", "tipo": "string",
         "prioridad": 10, "en_card": True, "en_nombre": True,
         "ayuda": "Ej: Full-frame CMOS 12.1MP"},
        {"key": "montura", "label": "Montura", "tipo": "enum",
         "enum_options": ["E", "RF", "EF", "L", "Z", "X", "MFT", "PL", "BMD"],
         "prioridad": 20, "en_card": True, "en_filtros": True, "en_nombre": True},
        {"key": "formato", "label": "Formato", "tipo": "enum",
         "enum_options": ["Full-frame", "Super 35", "APS-C", "MFT", "M4/3", "1\""],
         "prioridad": 30, "en_filtros": True},
        {"key": "video_max", "label": "Video máx", "tipo": "enum",
         "enum_options": ["4K", "6K", "8K", "12K", "FHD"],
         "prioridad": 40, "en_card": True, "en_filtros": True, "en_nombre": True},
        {"key": "fps_max", "label": "FPS máx", "tipo": "number", "unidad": "fps",
         "prioridad": 50},
        {"key": "iso_max", "label": "ISO máx", "tipo": "number", "unidad": "ISO",
         "prioridad": 60},
        {"key": "estabilizacion", "label": "Estabilización", "tipo": "bool",
         "prioridad": 70, "en_filtros": True},
        {"key": "autofocus", "label": "Autofocus", "tipo": "bool",
         "prioridad": 80},
        {"key": "peso", "label": "Peso", "tipo": "string",
         "prioridad": 90, "ayuda": "Ej: 640 g"},
        {"key": "incluye", "label": "Incluye", "tipo": "string",
         "prioridad": 100, "ayuda": "Ej: cuerpo, batería, cargador"},
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
        {"key": "montura", "label": "Montura", "tipo": "enum",
         "enum_options": ["E", "RF", "EF", "L", "Z", "X", "MFT", "PL", "M42"],
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
         "enum_options": ["Full-frame", "APS-C", "MFT", "Super 35", "Medium Format"],
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
        {"key": "peso", "label": "Peso", "tipo": "number", "unidad": "g",
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
         "enum_options": ["V-mount", "NP-F", "D-Tap", "AC", "USB-C", "Batería integrada"],
         "prioridad": 90, "en_filtros": True},
        {"key": "montaje", "label": "Montaje", "tipo": "string",
         "prioridad": 100, "ayuda": "Ej: Bowens, Profoto, fija"},
        {"key": "peso", "label": "Peso", "tipo": "string", "prioridad": 110},
    ],

    # 4. Modificadores
    "Modificadores": [
        {"key": "tipo", "label": "Tipo", "tipo": "enum",
         "enum_options": ["Softbox", "Frame de difusión", "Bandera", "Reflector",
                          "Octobox", "Strip", "Beauty Dish", "Fresnel", "Snoot"],
         "prioridad": 10, "obligatorio": True, "en_card": True, "en_nombre": True},
        {"key": "medidas", "label": "Medidas", "tipo": "string",
         "prioridad": 20, "obligatorio": True, "en_card": True,
         "ayuda": "Ej: 60x90 cm o 2x2 m"},
        {"key": "material", "label": "Material", "tipo": "enum",
         "enum_options": ["Difusor", "Negro", "Plata", "Oro", "Blanco", "Mixto"],
         "prioridad": 30},
        {"key": "montura", "label": "Montura", "tipo": "string",
         "prioridad": 40, "ayuda": "Ej: Bowens, varillas, libre"},
        {"key": "plegable", "label": "Plegable", "tipo": "bool", "prioridad": 50},
    ],

    # 5. Soportes
    "Soportes": [
        {"key": "tipo", "label": "Tipo", "tipo": "enum",
         "enum_options": ["Trípode video", "Trípode foto", "C-Stand", "Slider",
                          "Dolly", "Car Mount", "Camera Cage", "Gimbal"],
         "prioridad": 10, "obligatorio": True, "en_card": True, "en_nombre": True},
        {"key": "altura_max_m", "label": "Altura máx", "tipo": "number", "unidad": "m",
         "prioridad": 20},
        {"key": "altura_min_m", "label": "Altura mín", "tipo": "number", "unidad": "m",
         "prioridad": 30},
        {"key": "peso_max_kg", "label": "Carga máx", "tipo": "number", "unidad": "kg",
         "prioridad": 40, "en_filtros": True},
        {"key": "cabeza", "label": "Cabezal", "tipo": "string",
         "prioridad": 50, "ayuda": "Ej: 504HD, 502AH, fluida"},
        {"key": "nivel", "label": "Nivel", "tipo": "bool", "prioridad": 60},
        {"key": "material", "label": "Material", "tipo": "enum",
         "enum_options": ["Aluminio", "Acero", "Fibra de carbono", "Mixto"],
         "prioridad": 70},
        {"key": "peso", "label": "Peso", "tipo": "string", "prioridad": 80},
        # Específicas para gimbal (si tipo=Gimbal):
        {"key": "ejes", "label": "Ejes (gimbal)", "tipo": "enum",
         "enum_options": ["2", "3"], "prioridad": 90,
         "ayuda": "Solo para gimbals"},
        {"key": "autonomia_h", "label": "Autonomía (h)", "tipo": "number", "unidad": "h",
         "prioridad": 100, "ayuda": "Solo para gimbals con batería"},
    ],

    # 6. Grip
    "Grip": [
        {"key": "tipo", "label": "Tipo", "tipo": "enum",
         "enum_options": ["Brazo", "Clamp", "Wall plate", "Pinza", "Línea de seguridad",
                          "Sopapa", "Lastre", "Cage", "Plate", "Junior pin", "Apple box"],
         "prioridad": 10, "obligatorio": True, "en_card": True, "en_nombre": True},
        {"key": "material", "label": "Material", "tipo": "enum",
         "enum_options": ["Aluminio", "Acero", "Plástico", "Goma", "Madera", "Mixto"],
         "prioridad": 20},
        {"key": "peso_max_kg", "label": "Carga máx", "tipo": "number", "unidad": "kg",
         "prioridad": 30},
        {"key": "montaje", "label": "Montaje", "tipo": "string",
         "prioridad": 40, "ayuda": "Ej: 1/4-20, 3/8-16, baby pin"},
        {"key": "medidas", "label": "Medidas", "tipo": "string", "prioridad": 50},
        {"key": "peso", "label": "Peso", "tipo": "string", "prioridad": 60},
    ],

    # 7. Sonido
    "Sonido": [
        {"key": "tipo", "label": "Tipo", "tipo": "enum",
         "enum_options": ["Lavalier", "Shotgun", "On-camera", "Estudio",
                          "Inalámbrico", "Boom", "Intercom"],
         "prioridad": 10, "obligatorio": True, "en_card": True, "en_nombre": True},
        {"key": "patron", "label": "Patrón polar", "tipo": "enum",
         "enum_options": ["Cardioide", "Supercardioide", "Hipercardioide",
                          "Omnidireccional", "Bidireccional"],
         "prioridad": 20},
        {"key": "banda_freq", "label": "Banda", "tipo": "string",
         "prioridad": 30, "ayuda": "Ej: 2.4 GHz, UHF 470-608 MHz"},
        {"key": "canales", "label": "Canales", "tipo": "number", "prioridad": 40},
        {"key": "alimentacion", "label": "Alimentación", "tipo": "enum",
         "enum_options": ["Phantom 48V", "AA", "USB-C", "NP-F", "Batería integrada"],
         "prioridad": 50},
        {"key": "conexion", "label": "Conexión", "tipo": "enum",
         "enum_options": ["XLR", "3.5mm TRS", "3.5mm TRRS", "USB-C", "Inalámbrico"],
         "prioridad": 60, "en_filtros": True},
        {"key": "incluye", "label": "Incluye", "tipo": "string",
         "prioridad": 70, "ayuda": "Ej: Tx + Rx, deadcat, soporte de cámara"},
        {"key": "peso", "label": "Peso", "tipo": "string", "prioridad": 80},
    ],

    # 8. Monitores y Video
    "Monitores y Video": [
        {"key": "tipo", "label": "Tipo", "tipo": "enum",
         "enum_options": ["Monitor", "Grabador", "Tx wireless", "Rx wireless",
                          "Combo Tx/Rx", "Follow Focus", "Matebox"],
         "prioridad": 10, "obligatorio": True, "en_card": True, "en_nombre": True},
        {"key": "pulgadas", "label": "Pulgadas", "tipo": "number", "unidad": '"',
         "prioridad": 20, "en_card": True, "en_nombre": True},
        {"key": "resolucion", "label": "Resolución", "tipo": "string",
         "prioridad": 30, "ayuda": "Ej: 1920x1080, 2560x1600"},
        {"key": "brillo_nits", "label": "Brillo", "tipo": "number", "unidad": "nits",
         "prioridad": 40, "en_filtros": True},
        {"key": "entradas", "label": "Entradas", "tipo": "string",
         "prioridad": 50, "ayuda": "Ej: HDMI 2.0, SDI 12G, BNC"},
        {"key": "salidas", "label": "Salidas", "tipo": "string", "prioridad": 60},
        {"key": "graba_a", "label": "Graba a", "tipo": "enum",
         "enum_options": ["SD", "CFast", "NVMe", "SSD externo"],
         "prioridad": 70, "ayuda": "Solo grabadores"},
        {"key": "codecs", "label": "Codecs", "tipo": "string",
         "prioridad": 80, "ayuda": "Ej: ProRes, DNxHR"},
        {"key": "alimentacion", "label": "Alimentación", "tipo": "enum",
         "enum_options": ["NP-F", "V-mount", "USB-C", "AC"],
         "prioridad": 90},
        {"key": "peso", "label": "Peso", "tipo": "string", "prioridad": 100},
    ],

    # 9. Adaptadores y Filtros
    "Adaptadores y Filtros": [
        {"key": "tipo", "label": "Tipo", "tipo": "enum",
         "enum_options": ["Adaptador montura", "Speedbooster", "Filtro ND",
                          "Filtro polarizador", "Filtro UV", "Filtro variable",
                          "Macro tube"],
         "prioridad": 10, "obligatorio": True, "en_card": True, "en_nombre": True},
        {"key": "montura_in", "label": "Montura entrada", "tipo": "enum",
         "enum_options": ["E", "RF", "EF", "L", "Z", "X", "MFT", "PL", "M42"],
         "prioridad": 20, "en_card": True},
        {"key": "montura_out", "label": "Montura salida", "tipo": "enum",
         "enum_options": ["E", "RF", "EF", "L", "Z", "X", "MFT", "PL"],
         "prioridad": 30, "en_card": True},
        {"key": "diametro_mm", "label": "Diámetro", "tipo": "number", "unidad": "mm",
         "prioridad": 40, "ayuda": "Solo para filtros"},
        {"key": "densidad", "label": "Densidad ND", "tipo": "string",
         "prioridad": 50, "ayuda": "Ej: ND 0.6, ND variable 2-8"},
        {"key": "electronica", "label": "Comunicación electrónica", "tipo": "bool",
         "prioridad": 60},
        {"key": "incluye_iris", "label": "Iris incluido", "tipo": "bool",
         "prioridad": 70},
    ],

    # 10. Energía
    "Energía": [
        {"key": "tipo", "label": "Tipo", "tipo": "enum",
         "enum_options": ["V-mount", "NP-F", "LP-E6", "BP-U", "AA",
                          "Generador", "Distribución", "Cargador", "Alargue", "Zapatilla"],
         "prioridad": 10, "obligatorio": True, "en_card": True, "en_nombre": True},
        {"key": "capacidad_wh", "label": "Capacidad", "tipo": "number", "unidad": "Wh",
         "prioridad": 20, "en_card": True, "ayuda": "Solo baterías"},
        {"key": "voltaje", "label": "Voltaje", "tipo": "string",
         "prioridad": 30, "ayuda": "Ej: 14.8V, 220V"},
        {"key": "salidas", "label": "Salidas", "tipo": "string",
         "prioridad": 40, "ayuda": "Ej: D-Tap, USB-C PD, P-Tap"},
        {"key": "canales", "label": "Canales", "tipo": "number",
         "prioridad": 50, "ayuda": "Solo para distribución"},
        {"key": "amperaje", "label": "Amperaje", "tipo": "string",
         "prioridad": 60, "ayuda": "Ej: 10A"},
        {"key": "peso", "label": "Peso", "tipo": "string", "prioridad": 70},
    ],

    # 11. Media y Datos
    "Media y Datos": [
        {"key": "tipo", "label": "Tipo", "tipo": "enum",
         "enum_options": ["SD", "microSD", "CFexpress B", "CFexpress A", "CFast",
                          "SSD externo", "Lector"],
         "prioridad": 10, "obligatorio": True, "en_card": True, "en_nombre": True},
        {"key": "capacidad_gb", "label": "Capacidad", "tipo": "number", "unidad": "GB",
         "prioridad": 20, "en_card": True, "en_nombre": True},
        {"key": "velocidad_lectura", "label": "Lectura", "tipo": "number", "unidad": "MB/s",
         "prioridad": 30, "en_filtros": True},
        {"key": "velocidad_escritura", "label": "Escritura", "tipo": "number", "unidad": "MB/s",
         "prioridad": 40},
        {"key": "clase", "label": "Clase", "tipo": "string",
         "prioridad": 50, "ayuda": "Ej: V90, UHS-II, U3"},
        {"key": "interfaz", "label": "Interfaz", "tipo": "string",
         "prioridad": 60, "ayuda": "Solo lectores. Ej: USB-C, Thunderbolt 3"},
    ],

    # 12. Estudio y Producción → no template (son paquetes/sets sin specs comunes).
    # Si hace falta agregarlo después, el admin puede crear specs vía UI.
}


def seed_spec_templates(conn) -> int:
    """Inserta los templates iniciales en la DB. Idempotente: si ya existe
    el par (categoria_id, spec_key), no lo pisa.

    Devuelve la cantidad de specs insertados/actualizados."""
    inserted = 0
    for cat_nombre, specs in TEMPLATES.items():
        # Resolver el id de la categoría raíz por nombre.
        row = conn.execute(
            "SELECT id FROM categorias WHERE nombre = %s AND parent_id IS NULL",
            (cat_nombre,),
        ).fetchone()
        if not row:
            # La categoría no existe (puede pasar si el seed del árbol cambió).
            # Skipeamos en silencio en lugar de romper el init.
            continue
        cat_id = row["id"]

        for prio_idx, spec in enumerate(specs):
            enum_opts_json = (
                json.dumps(spec["enum_options"]) if spec.get("enum_options") else None
            )
            cur = conn.execute(
                """
                INSERT INTO categoria_spec_templates
                  (categoria_id, spec_key, label, tipo, unidad, enum_options,
                   prioridad, visible_en_card, visible_en_filtros,
                   visible_en_nombre, obligatorio, ayuda)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (categoria_id, spec_key) DO NOTHING
                RETURNING id
                """,
                (
                    cat_id,
                    spec["key"],
                    spec["label"],
                    spec["tipo"],
                    spec.get("unidad"),
                    enum_opts_json,
                    spec.get("prioridad", 100),
                    spec.get("en_card", False),
                    spec.get("en_filtros", False),
                    spec.get("en_nombre", False),
                    spec.get("obligatorio", False),
                    spec.get("ayuda"),
                ),
            )
            if cur.fetchone() is not None:
                inserted += 1
    return inserted
