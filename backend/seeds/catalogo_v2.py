"""
seeds/catalogo_v2.py — Catálogo normalizado v2 de specs.

Basado en relevamiento Firecrawl directo a 22 productos B&H representativos
del rubro AV pro (Sony FX3, Sigma 50 Art, Aputure 600d Pro, Rode Wireless
GO II, etc.). Cubre 167 labels únicos consolidados en 100 specs canónicas
organizadas en 13 dominios.

Este seed COEXISTE con `spec_templates.py` legacy — agrega las specs nuevas
con `spec_key`s que NO colisionan con las existentes. La consolidación
(merge entre viejas y nuevas) se hace después con el dedup tool admin
(`/admin/specs/dedup`) bajo curación humana.

Aplicar: el endpoint `/admin/specs/seed-catalogo-v2` ejecuta esta función
(o la migración Alembic c1d3e5f7a9b2).
"""

import json


# 100 specs canónicas organizadas por dominio. Cada entrada genera una
# row en `spec_definitions`. Las asignaciones a categorías se manejan
# aparte (el admin las hace via UI o con seed posterior).
CATALOGO_V2: list[dict] = [
    # ── Transversales (aparecen en múltiples categorías) ────────────────
    {"spec_key": "peso_g", "label": "Peso", "tipo": "number", "unidad": "g",
     "ayuda": "Peso del fixture (no del packaging). Imperial→métrico vía normalizer."},
    {"spec_key": "dimensiones_mm", "label": "Dimensiones", "tipo": "wxhxd", "unidad": "mm",
     "ayuda": "W×H×D. Acepta también 2 medidas (W×H) o 1 (largo)."},
    {"spec_key": "color_v2", "label": "Color", "tipo": "string"},
    {"spec_key": "material_construccion", "label": "Material de construcción", "tipo": "string"},
    {"spec_key": "packaging_peso", "label": "Peso con packaging", "tipo": "number", "unidad": "g",
     "ayuda": "Peso con caja/embalaje. Aparece en 8+ productos B&H — separado del fixture."},
    {"spec_key": "packaging_dimensiones", "label": "Dimensiones con packaging", "tipo": "wxhxd", "unidad": "mm"},

    # ── Mounts (zoo de 9 conceptos distintos identificados) ─────────────
    {"spec_key": "lens_mount_v2", "label": "Lens mount", "tipo": "enum",
     "enum_options": ["Sony E", "Canon RF", "Canon EF", "L", "Z", "X", "MFT", "M4/3", "PL", "BMD", "B4", "M42"],
     "ayuda": "Rosca lente↔cuerpo. Cámaras / lentes / adaptadores."},
    {"spec_key": "battery_mount", "label": "Battery mount", "tipo": "enum",
     "enum_options": ["V-Mount", "Gold-Mount", "NP-F", "NP-FZ100", "L-Series", "BP-U", "LP-E6", "LiPo 3S", "Built-in"],
     "ayuda": "Plate de batería que acepta el equipo (luces/cámaras/monitores)."},
    {"spec_key": "modifier_mount", "label": "Modifier mount", "tipo": "enum",
     "enum_options": ["Bowens S", "Profoto", "Elinchrom", "Mola", "Speedring", "Aputure 600d", "Godox"],
     "ayuda": "Sistema de montaje de modificador en la luz."},
    {"spec_key": "fixture_mounting", "label": "Fixture mounting", "tipo": "string",
     "ayuda": 'Cómo la luz se monta al soporte. Ej: "1-1/8\\" Stud with 5/8\\" Receiver", "Junior Pin", "Yoke".'},
    {"spec_key": "umbrella_mount", "label": "Umbrella mount", "tipo": "bool"},
    {"spec_key": "camera_mount_threads", "label": "Roscas de cámara", "tipo": "string",
     "ayuda": "Cómo el soporte agarra la cámara. Ej: 1/4-20, Manfrotto plate, V-Lock."},
    {"spec_key": "tripod_base_mount", "label": "Base del cabezal", "tipo": "enum",
     "enum_options": ["75mm Half-Ball", "100mm Half-Ball", "150mm Half-Ball", "Flat Base 3/8", "Flat Base 1/4"]},
    {"spec_key": "accessory_threads", "label": "Roscas de accesorios", "tipo": "multi_enum",
     "enum_options": ["1/4-20", "3/8-16", "5/8-27", "Cold Shoe", "Hot Shoe", "NATO Rail", "ARRI Rosette"]},
    {"spec_key": "mic_mounting_options", "label": "Opciones de montaje (mic)", "tipo": "multi_enum",
     "enum_options": ["Cold Shoe", "Magic Arm", "Belt Clip", "Lightning Plug-In", "USB-C Plug-In", "Hand-Held"]},

    # ── Cámaras ─────────────────────────────────────────────────────────
    {"spec_key": "sensor_tipo", "label": "Tipo de sensor", "tipo": "enum",
     "enum_options": ["Full-Frame", "Super35", "APS-C", "MFT", "M4/3", "1\"", "Medium Format"]},
    {"spec_key": "sensor_resolucion_mp", "label": "Resolución del sensor", "tipo": "number", "unidad": "MP"},
    {"spec_key": "iso_rango_nativo", "label": "ISO nativo (rango)", "tipo": "rango", "unidad": "ISO"},
    {"spec_key": "video_modos_grabacion", "label": "Modos de grabación", "tipo": "string",
     "ayuda": "Compuesto: codec + resolución + fps + bit depth."},
    {"spec_key": "video_out_max", "label": "Salida video máx", "tipo": "string"},
    {"spec_key": "memoria_slots", "label": "Slots de memoria", "tipo": "string",
     "ayuda": 'Ej: "Slot 1: SD UHS-II; Slot 2: CFast", "Dual CFexpress Type A".'},
    {"spec_key": "image_stabilization", "label": "Estabilización óptica", "tipo": "enum",
     "enum_options": ["Yes", "No", "Sensor-Shift", "Optical", "5-Axis Sensor-Shift", "Lens-based"]},

    # ── Lentes (la categoría más estandarizada en B&H) ──────────────────
    {"spec_key": "distancia_focal_v2", "label": "Distancia focal", "tipo": "rango", "unidad": "mm"},
    {"spec_key": "apertura_v2", "label": "Apertura", "tipo": "rango", "unidad": "f/",
     "ayuda": "Parser: extrae 'Maximum: f/X, Minimum: f/Y'."},
    {"spec_key": "formato_cobertura", "label": "Cobertura de formato", "tipo": "enum",
     "enum_options": ["Full-Frame", "Super35", "APS-C", "MFT", "M4/3", "Medium Format"]},
    {"spec_key": "angulo_vision", "label": "Ángulo de visión", "tipo": "rango", "unidad": "°"},
    {"spec_key": "distancia_minima_enfoque", "label": "Distancia mínima de enfoque", "tipo": "number", "unidad": "cm"},
    {"spec_key": "magnificacion", "label": "Magnificación", "tipo": "string",
     "ayuda": "Ej: 0.32x, 1:5.55. String porque hay 2 notaciones."},
    {"spec_key": "construccion_optica", "label": "Construcción óptica", "tipo": "string",
     "ayuda": "Ej: 20 elementos / 15 grupos."},
    {"spec_key": "hojas_diafragma", "label": "Hojas del diafragma", "tipo": "number"},
    {"spec_key": "focus_type", "label": "Tipo de enfoque", "tipo": "enum",
     "enum_options": ["Autofocus", "Manual", "AF/MF", "Autofocus with Manual Override"]},
    {"spec_key": "filter_size", "label": "Diámetro de filtro", "tipo": "number", "unidad": "mm"},

    # ── Iluminación ─────────────────────────────────────────────────────
    {"spec_key": "potencia_w_v2", "label": "Potencia", "tipo": "number", "unidad": "W"},
    {"spec_key": "cct", "label": "Temperatura de color (CCT)", "tipo": "rango", "unidad": "K"},
    {"spec_key": "color_modes", "label": "Modos de color", "tipo": "multi_enum",
     "enum_options": ["RGB", "Daylight", "Tungsten", "Bicolor", "Bicolor+Green/Magenta", "Full Spectrum", "CCT", "HSI", "GEL"]},
    {"spec_key": "cri_v2", "label": "CRI", "tipo": "number",
     "ayuda": "Color Rendering Index 0-100."},
    {"spec_key": "tlci", "label": "TLCI", "tipo": "number",
     "ayuda": "Television Lighting Consistency Index 0-100."},
    {"spec_key": "fotometria_lumens", "label": "Lúmenes (output)", "tipo": "number", "unidad": "lm"},
    {"spec_key": "fotometria_lux_1m", "label": "Lux @ 1m", "tipo": "tabla",
     "tabla_columnas": [
         {"key": "temperatura", "label": "Temp", "tipo": "valor_unidad", "unidades_opciones": ["K"]},
         {"key": "angulo", "label": "Ángulo", "tipo": "valor_unidad", "unidades_opciones": ["°"], "prefijo": "a"},
         {"key": "lux", "label": "Lux", "tipo": "valor_unidad", "unidades_opciones": ["lux", "Lux"], "prefijo": "→"},
         {"key": "fc", "label": "fc", "tipo": "valor_unidad", "unidades_opciones": ["fc"], "prefijo": "/"},
     ],
     "ayuda": "Matriz de lux por (temperatura, ángulo). B&H lo da como string compuesto."},
    {"spec_key": "beam_angle", "label": "Ángulo de haz", "tipo": "string",
     "ayuda": 'Ej: "70° Unmodified ; 45° with Included Reflector".'},
    {"spec_key": "dimming", "label": "Dimming", "tipo": "string",
     "ayuda": "Compuesto: control + rango. Ej: 'App-Controlled / Built-In Dimmer / DMX ; 0 to 100%'."},
    {"spec_key": "control_inalambrico", "label": "Control inalámbrico", "tipo": "multi_enum",
     "enum_options": ["Bluetooth", "Wi-Fi", "DMX", "Lumenradio", "App", "RF 2.4 GHz"]},
    {"spec_key": "cooling_system", "label": "Sistema de enfriamiento", "tipo": "enum",
     "enum_options": ["Fan", "Passive", "Hybrid"]},

    # ── Sonido (la categoría más rica, wireless complejo) ───────────────
    {"spec_key": "mic_tipo", "label": "Tipo de micrófono", "tipo": "enum",
     "enum_options": ["Lavalier", "Shotgun", "On-camera", "Estudio", "Inalámbrico", "Boom", "Intercom", "Built-In (Clip-On Transmitter)"]},
    {"spec_key": "patron_polar", "label": "Patrón polar", "tipo": "multi_enum",
     "enum_options": ["Cardioide", "Supercardioide", "Hipercardioide", "Omnidireccional", "Bidireccional", "Lobar"]},
    {"spec_key": "elemento_tipo", "label": "Tipo de elemento", "tipo": "enum",
     "enum_options": ["Condenser", "Dynamic", "Ribbon", "Electret"]},
    {"spec_key": "tx_count", "label": "Transmisores incluidos", "tipo": "number"},
    {"spec_key": "rx_count", "label": "Receptores incluidos", "tipo": "string"},
    {"spec_key": "wireless_tech", "label": "Tecnología inalámbrica", "tipo": "enum",
     "enum_options": ["Digital 2.4 GHz", "Digital DECT (1.9 GHz)", "Digital UHF", "Analog UHF", "Analog VHF"]},
    {"spec_key": "rf_band", "label": "Banda RF", "tipo": "string"},
    {"spec_key": "rango_operacion_m", "label": "Rango máximo de operación", "tipo": "number", "unidad": "m"},
    {"spec_key": "spl_max_db", "label": "SPL máximo", "tipo": "number", "unidad": "dB"},
    {"spec_key": "freq_response_hz", "label": "Respuesta de frecuencia", "tipo": "rango", "unidad": "Hz"},
    {"spec_key": "rec_internal", "label": "Grabador interno", "tipo": "bool"},
    {"spec_key": "timecode_support", "label": "Soporte timecode", "tipo": "bool"},
    {"spec_key": "encryption", "label": "Encriptación", "tipo": "string"},
    {"spec_key": "audio_canales", "label": "Canales de audio", "tipo": "number"},
    {"spec_key": "diversidad", "label": "Diversidad", "tipo": "enum",
     "enum_options": ["True Diversity", "Antenna Diversity", "Frequency Diversity", "No"]},
    {"spec_key": "gain_range_db", "label": "Rango de ganancia", "tipo": "rango", "unidad": "dB"},

    # ── Monitores y Video ───────────────────────────────────────────────
    {"spec_key": "display_pulgadas", "label": "Pulgadas", "tipo": "number", "unidad": '"'},
    {"spec_key": "resolucion_nativa", "label": "Resolución nativa", "tipo": "wxh", "unidad": "px"},
    {"spec_key": "touchscreen", "label": "Touchscreen", "tipo": "bool"},
    {"spec_key": "hdr_support", "label": "Soporte HDR", "tipo": "multi_enum",
     "enum_options": ["HDR10", "HLG", "Dolby Vision", "PQ", "Rec. 2020"]},
    {"spec_key": "panel_type", "label": "Tipo de panel", "tipo": "enum",
     "enum_options": ["IPS", "OLED", "TFT-LCD", "Mini-LED", "LCD"]},
    {"spec_key": "brillo_nits_v2", "label": "Brillo máximo", "tipo": "number", "unidad": "nits"},
    {"spec_key": "contraste", "label": "Contraste", "tipo": "string"},
    {"spec_key": "color_gamut", "label": "Color gamut", "tipo": "string"},
    {"spec_key": "lut_support", "label": "Soporte LUT", "tipo": "bool"},

    # ── Soportes ────────────────────────────────────────────────────────
    {"spec_key": "head_type", "label": "Tipo de cabezal", "tipo": "enum",
     "enum_options": ["Fluid Video", "Ball", "Gimbal Head", "Geared", "3-Way Pan/Tilt", "Pistol Grip"]},
    {"spec_key": "drag_control", "label": "Control de drag", "tipo": "string"},
    {"spec_key": "carga_max_kg", "label": "Carga máxima", "tipo": "number", "unidad": "kg"},
    {"spec_key": "counter_balance", "label": "Contrapeso", "tipo": "string"},
    {"spec_key": "vertical_tilt", "label": "Inclinación vertical", "tipo": "string"},
    {"spec_key": "bubble_level", "label": "Nivel de burbuja", "tipo": "bool"},
    {"spec_key": "altura_max_m", "label": "Altura máxima", "tipo": "number", "unidad": "m"},
    {"spec_key": "altura_min_cm", "label": "Altura mínima", "tipo": "number", "unidad": "cm"},

    # ── Energía ─────────────────────────────────────────────────────────
    {"spec_key": "battery_quimica", "label": "Química de batería", "tipo": "enum",
     "enum_options": ["Lithium-Ion", "LiPo", "Lead-Acid", "NiMH", "Alkaline"]},
    {"spec_key": "battery_capacidad_wh", "label": "Capacidad (Wh)", "tipo": "number", "unidad": "Wh"},
    {"spec_key": "battery_capacidad_mah", "label": "Capacidad (mAh)", "tipo": "number", "unidad": "mAh"},
    {"spec_key": "battery_voltage", "label": "Voltaje", "tipo": "number", "unidad": "V"},
    {"spec_key": "battery_indicator", "label": "Indicador", "tipo": "enum",
     "enum_options": ["LCD", "LED", "Battery Gauge", "App", "None"]},

    # ── Media y Datos ───────────────────────────────────────────────────
    {"spec_key": "media_card_type", "label": "Tipo de tarjeta", "tipo": "enum",
     "enum_options": ["SDXC", "SDHC", "microSDXC", "CFexpress Type A", "CFexpress Type B", "CFast", "XQD", "Compact Flash"]},
    {"spec_key": "media_capacidad_gb", "label": "Capacidad", "tipo": "number", "unidad": "GB"},
    {"spec_key": "media_bus", "label": "Bus", "tipo": "enum",
     "enum_options": ["UHS-I", "UHS-II", "UHS-III", "PCIe 3.0 x2", "PCIe 4.0 x4"]},
    {"spec_key": "media_speed_class", "label": "Speed class", "tipo": "multi_enum",
     "enum_options": ["Class 10", "U1", "U3", "V30", "V60", "V90", "A1", "A2"]},
    {"spec_key": "media_read_mbps", "label": "Velocidad de lectura", "tipo": "number", "unidad": "MB/s"},
    {"spec_key": "media_write_mbps", "label": "Velocidad de escritura", "tipo": "number", "unidad": "MB/s"},

    # ── Modificadores ───────────────────────────────────────────────────
    {"spec_key": "modifier_light_loss", "label": "Pérdida/ganancia de luz", "tipo": "string",
     "ayuda": 'Ej: "2.5-Stop Loss (with Diffuser and Baffle)".'},
    {"spec_key": "modifier_accepts_grids", "label": "Acepta grids", "tipo": "bool"},
    {"spec_key": "modifier_quick_open", "label": "Apertura rápida", "tipo": "bool"},
    {"spec_key": "modifier_interior_color", "label": "Color interior", "tipo": "enum",
     "enum_options": ["Silver", "White", "Gold", "Black"]},
    {"spec_key": "modifier_removable_face", "label": "Frente removible", "tipo": "bool"},

    # ── Conectividad (I/O, transversal en cámaras/monitores/luces) ──────
    {"spec_key": "video_io", "label": "I/O de video", "tipo": "multi_enum",
     "enum_options": ["HDMI Type-A", "HDMI Type-D (Micro)", "HDMI Type-C (Mini)", "SDI 3G", "SDI 6G", "SDI 12G", "USB-C", "BNC", "Genlock"]},
    {"spec_key": "audio_io_v2", "label": "I/O de audio", "tipo": "multi_enum",
     "enum_options": ["XLR", "3.5mm TRS", "3.5mm TRRS", "1/4 TRS", "USB-C", "Lightning", "Headphone", "TC"]},
    {"spec_key": "power_io", "label": "I/O de poder", "tipo": "multi_enum",
     "enum_options": ["D-Tap", "P-Tap", "USB-C PD", "USB-A", "Barrel DC", "XLR 4-Pin", "V-Mount", "L-Series"]},
    {"spec_key": "wireless_general", "label": "Conectividad inalámbrica", "tipo": "multi_enum",
     "enum_options": ["Wi-Fi 5", "Wi-Fi 6", "Bluetooth 4.0", "Bluetooth 5.0", "NFC", "DMX", "Lumenradio"]},

    # ── Environment (transversal) ───────────────────────────────────────
    {"spec_key": "operating_temp", "label": "Temperatura de operación", "tipo": "rango", "unidad": "°C"},
    {"spec_key": "storage_temp", "label": "Temperatura de almacenamiento", "tipo": "rango", "unidad": "°C"},
    {"spec_key": "env_resistance", "label": "Resistencia ambiental", "tipo": "string",
     "ayuda": 'Ej: "Dust/Water-Resistant (IP54)", "Sealed".'},
]


def seed_catalogo_v2(conn) -> dict:
    """Inserta las 100 specs del catálogo normalizado v2.

    Idempotente: cada spec_key se inserta con ON CONFLICT DO NOTHING.
    Specs existentes (de spec_templates.py legacy) NO se modifican.

    Devuelve {inserted, skipped, total}.
    """
    inserted = 0
    skipped = 0
    for spec in CATALOGO_V2:
        enum_opts = json.dumps(spec.get("enum_options")) if spec.get("enum_options") else None
        tabla_cols = json.dumps(spec.get("tabla_columnas")) if spec.get("tabla_columnas") else None
        cur = conn.execute(
            """
            INSERT INTO spec_definitions
              (spec_key, label, tipo, unidad, enum_options, ayuda, tabla_columnas)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (spec_key) DO NOTHING
            RETURNING id
            """,
            (
                spec["spec_key"],
                spec["label"],
                spec["tipo"],
                spec.get("unidad"),
                enum_opts,
                spec.get("ayuda"),
                tabla_cols,
            ),
        )
        if cur.fetchone():
            inserted += 1
        else:
            skipped += 1
    return {"inserted": inserted, "skipped": skipped, "total": len(CATALOGO_V2)}
