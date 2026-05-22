"""Registry canónico de specs por categoría.

Single source of truth. Cualquier consumer (seeds, parsers, nombre_builder,
clasificador, API) importa desde acá. No duplicar metadata en otro lado.

Convenciones de spec_key:
- Local por categoría (cada categoría tiene su namespace de keys, la DB usa
  composite UNIQUE (categoria_raiz_id, spec_key)).
- Forma snake_case ASCII (ver SpecDef.key pattern).
- Para evitar lectura ambigua, los "subtipos" usan prefijo de la cat:
  `camera_subtipo`, `iluminacion_subtipo`, `adaptador_subtipo`, `filtro_subtipo`.
- Las keys "shared semánticamente" (`lens_mount`, `formato`, `diametro_filtro`,
  `peso_g`) usan el MISMO string en todas las cats — esto NO es colisión
  porque la composite key incluye categoria. El motor de compat matchea
  por string-equality del key + value.

Convenciones de compatibilidad:
- es_compatibilidad=True declara que esta spec participa del motor _compute_compat.
- compatibilidad_modo="exacta": match si value_a == value_b (lens_mount, diametro_filtro).
- compatibilidad_modo="jerarquia": usa enum_options como escala. Roles:
  - "contenedor" = el que proyecta (lente → sensor)
  - "contenido"  = el que recibe (sensor de cámara)
"""

from __future__ import annotations

from .models import CategoriaRegistry, Registry, SpecDef, SubCategoria

# ─────────────────────────────────────────────────────────────────────
# Enums compartidos
# ─────────────────────────────────────────────────────────────────────

FORMATO_ENUM: list[str] = [
    "1\"", "MFT", "M4/3", "APS-C", "Super 35", "Full-frame", "Medium Format"
]

LENS_MOUNT_ENUM: list[str] = [
    "E", "RF", "EF", "L", "Z", "X", "MFT", "PL", "BMD", "B4", "M42"
]


# ─────────────────────────────────────────────────────────────────────
# Cámaras
# ─────────────────────────────────────────────────────────────────────

_CAMARAS = CategoriaRegistry(
    nombre="Cámaras",
    prioridad=10,
    sub_categorias=[
        SubCategoria(nombre="Foto", prioridad=10),
        SubCategoria(nombre="Video", prioridad=20),
        SubCategoria(nombre="Acción", prioridad=30),
        # Video > monturas (taxonomía 2-niveles).
        # Sólo las monturas en uso real. Si más adelante hay equipos con
        # otra montura, se agrega acá o se crea on-the-fly desde admin.
        SubCategoria(nombre="Montura E",   prioridad=10, parent="Video"),
        SubCategoria(nombre="Montura RF",  prioridad=20, parent="Video"),
        SubCategoria(nombre="Montura EF",  prioridad=30, parent="Video"),
    ],
    specs=[
        SpecDef(
            key="camera_subtipo", label="Tipo", tipo="enum",
            enum_options=[
                "Cinema Camera", "Mirrorless", "DSLR", "Vlogging",
                "Action Camera", "Compact", "Medium Format", "Camera",
            ],
            prioridad=10, en_card=True, en_filtros=True, en_nombre=True,
            destacado=True, ayuda="Form factor de la cámara",
        ),
        SpecDef(
            key="lens_mount", label="Lens mount", tipo="enum",
            enum_options=LENS_MOUNT_ENUM,
            prioridad=15, en_card=True, en_filtros=True, en_nombre=True,
            destacado=True,
            ayuda="Null para cámaras con lente fijo (action cams, smartphones)",
            es_compatibilidad=True, compatibilidad_modo="exacta",
        ),
        SpecDef(
            key="formato", label="Formato", tipo="enum",
            enum_options=FORMATO_ENUM,
            prioridad=20, en_card=True, en_filtros=True, en_nombre=True, destacado=True,
            es_compatibilidad=True, compatibilidad_modo="jerarquia",
            rol_compatibilidad="contenido",
        ),
        SpecDef(
            key="resolucion_max", label="Resolución máxima", tipo="enum",
            enum_options=["FHD", "2K", "4K", "5K", "5.7K", "6K", "8K", "12K"],
            prioridad=30, en_card=True, en_filtros=True, en_nombre=True, destacado=True,
        ),
        SpecDef(key="fps_max", label="FPS máx", tipo="number", unidad="fps",
                prioridad=40, en_filtros=True, destacado=True,
                ayuda="Frame rate máximo en cualquier resolución"),
        SpecDef(key="megapixels", label="Megapixels", tipo="number", unidad="MP",
                prioridad=45, en_filtros=True),
        SpecDef(key="codecs", label="Codecs principales", tipo="string",
                prioridad=60, ayuda="Ej: ProRes, REDCODE, XAVC S-I 4:2:2"),
        SpecDef(key="iso_nativo", label="ISO nativo", tipo="rango", unidad="ISO",
                prioridad=65, en_filtros=True, ayuda="Rango nativo. Ej: '80-102400'"),
        SpecDef(key="iso_extendido", label="ISO extendido", tipo="rango", unidad="ISO",
                prioridad=67, ayuda="Con boost. Ej: '80-409600'"),
        SpecDef(key="rango_dinamico_stops", label="Rango dinámico", tipo="number",
                unidad="stops", prioridad=70, en_filtros=True),
        SpecDef(key="estabilizacion", label="Estabilización óptica", tipo="bool",
                prioridad=75, en_filtros=True),
        SpecDef(key="autofocus", label="Autofocus", tipo="bool",
                prioridad=80, en_filtros=True),
        SpecDef(key="fast_slow_motion", label="Fast/Slow motion", tipo="bool",
                prioridad=85, ayuda="Soporta variable frame rate / S&Q"),
        SpecDef(key="lens_communication", label="Comunicación electrónica lente", tipo="bool",
                prioridad=90),
        SpecDef(key="gps", label="GPS", tipo="bool", prioridad=92),
        SpecDef(key="ip_streaming", label="IP Streaming", tipo="bool",
                prioridad=95, ayuda="Para broadcast / live streaming"),
        SpecDef(key="netflix_approved", label="Netflix approved", tipo="bool",
                prioridad=98, en_card=True, en_filtros=True),
        SpecDef(key="continuous_shooting_fps", label="Ráfaga (stills)", tipo="number",
                unidad="fps", prioridad=99, ayuda="Burst rate para fotografía"),
        SpecDef(key="max_aperture", label="Apertura máxima (fixed-lens)", tipo="string",
                prioridad=101, ayuda="Solo para cámaras con lente fijo (GoPro, etc.)"),
        SpecDef(key="sensor_crop", label="Sensor crop (35mm eq.)", tipo="string",
                prioridad=102),
        SpecDef(key="recording_limit_min", label="Límite de grabación", tipo="number",
                unidad="min", prioridad=103, ayuda="Algunos modelos tienen tope 29min59s"),
        SpecDef(key="peso_g", label="Peso", tipo="number", unidad="g",
                prioridad=100, ayuda="Peso del cuerpo solo, sin batería ni media"),
        # ─── Conectividad / I/O ───────────────────────────────────────
        SpecDef(key="video_io", label="Conexiones video", tipo="string",
                prioridad=110, en_filtros=True,
                ayuda="Ej: HDMI Type A, 12G-SDI, 3G-SDI"),
        SpecDef(key="audio_io", label="Conexiones audio", tipo="string",
                prioridad=115,
                ayuda="Ej: 1× 3.5mm TRS Stereo Microphone Input, 1× 3.5mm Headphone Output"),
        SpecDef(key="power_io", label="Conexiones de alimentación", tipo="string",
                prioridad=120,
                ayuda="Ej: DC In, USB-C PD, D-Tap"),
        SpecDef(key="other_io", label="Otras conexiones", tipo="string",
                prioridad=125,
                ayuda="Ej: USB-C 3.2 Gen 2 (data), Timecode, multi/USB"),
        SpecDef(
            key="wireless", label="Wireless", tipo="multi_enum",
            enum_options=["Wi-Fi", "Wi-Fi 2.4 GHz", "Wi-Fi 5 GHz", "Bluetooth", "NFC", "5G", "LTE"],
            prioridad=130, en_filtros=True,
        ),
        SpecDef(key="mobile_app_compatible", label="App móvil compatible", tipo="bool",
                prioridad=135),
        # ─── Batería / energía ────────────────────────────────────────
        SpecDef(key="battery", label="Batería", tipo="string",
                prioridad=140, en_card=True,
                ayuda="Modelo de batería nativa. Ej: NP-FZ100, BP-A30, BP-955"),
        SpecDef(key="power_consumption_w", label="Consumo", tipo="number", unidad="W",
                prioridad=145),
        # ─── Captura / sensor adicional ───────────────────────────────
        SpecDef(
            key="capture_type", label="Tipo de captura", tipo="enum",
            enum_options=["Stills", "Video", "Stills & Video"],
            prioridad=150, en_filtros=True,
        ),
        SpecDef(
            key="shutter_type", label="Tipo de obturador", tipo="enum",
            enum_options=["Electronic", "Mechanical", "Hybrid", "Global Shutter", "Rolling Shutter"],
            prioridad=155, en_filtros=True,
        ),
        SpecDef(key="shutter_speed", label="Velocidad de obturación", tipo="string",
                prioridad=160, ayuda="Ej: 1/8000 to 30 seconds"),
        SpecDef(key="built_in_nd", label="Filtro ND integrado", tipo="bool",
                prioridad=165, en_card=True, en_filtros=True,
                ayuda="Cinema cameras: ND interno fijo o variable"),
        SpecDef(key="internal_recording", label="Grabación interna", tipo="string",
                prioridad=170, ayuda="Resolución máx + framerate + bitrate más alto"),
        SpecDef(key="gamma_curve", label="Curva de gamma / log", tipo="string",
                prioridad=175, ayuda="Ej: S-Log3, V-Log, C-Log3, REDLogFilm"),
        # ─── Audio ────────────────────────────────────────────────────
        SpecDef(key="audio_recording", label="Grabación de audio", tipo="string",
                prioridad=180, ayuda="Ej: 2-Channel 16-Bit 48 kHz LPCM"),
        SpecDef(key="built_in_microphone", label="Micrófono integrado", tipo="bool",
                prioridad=185),
        # ─── Storage / media ──────────────────────────────────────────
        SpecDef(key="media_card_slots", label="Slots de memoria", tipo="string",
                prioridad=190, en_filtros=True,
                ayuda="Ej: Dual CFexpress Type A / SDXC UHS-II"),
        SpecDef(key="internal_storage", label="Almacenamiento interno", tipo="string",
                prioridad=195, ayuda="Algunos cuerpos (REDs, FX) tienen SSD interno"),
        # ─── Display / EVF ────────────────────────────────────────────
        SpecDef(key="display_type", label="Pantalla", tipo="string",
                prioridad=200, ayuda="Ej: 3.0\" LCD Touchscreen, 1.6M dot"),
        # ─── Foto ─────────────────────────────────────────────────────
        SpecDef(key="focus_points", label="Puntos de AF", tipo="number",
                prioridad=205, ayuda="Cantidad de puntos del sistema AF"),
        SpecDef(key="exposure_modes", label="Modos de exposición", tipo="string",
                prioridad=210, ayuda="Ej: P, A, S, M, Auto"),
        # ─── Físico / ambiental ───────────────────────────────────────
        SpecDef(key="dimensions_mm", label="Dimensiones", tipo="string",
                prioridad=215, ayuda="Ej: 129.7 × 77.8 × 84.5 mm (W × H × D)"),
        SpecDef(key="operating_conditions", label="Condiciones operativas", tipo="string",
                prioridad=220, ayuda="Ej: 0 to 40°C / 5-80% humidity"),
        SpecDef(key="tripod_mount", label="Rosca de trípode", tipo="string",
                prioridad=225, ayuda="Ej: 1/4-20, 3/8-16"),
        SpecDef(key="shoe_mount", label="Hot shoe", tipo="string",
                prioridad=230, ayuda="Ej: Multi Interface Shoe, 1× Cold Shoe"),
        SpecDef(key="materials", label="Materiales", tipo="string",
                prioridad=235, ayuda="Ej: Magnesium Alloy, Polycarbonate"),
        # ─── Capturados de HTMLs B&H — completar ficha técnica ────────
        SpecDef(key="white_balance", label="Balance de blancos", tipo="string", prioridad=300, ayuda="Rango K + presets"),
        SpecDef(key="bulb_time_mode", label="Modo Bulb / Time", tipo="string", prioridad=301),
        SpecDef(key="metering_method", label="Modo de medición", tipo="string", prioridad=302, ayuda="Ej: Spot, Multi-Zone, Center-Weighted"),
        SpecDef(key="exposure_compensation", label="Compensación exposición", tipo="string", prioridad=303),
        SpecDef(key="metering_range", label="Rango de medición", tipo="string", prioridad=304),
        SpecDef(key="interval_recording", label="Grabación por intervalo", tipo="bool", prioridad=305),
        SpecDef(key="self_timer", label="Disparador automático", tipo="string", prioridad=306),
        SpecDef(key="aspect_ratio", label="Relación de aspecto", tipo="string", prioridad=307, ayuda="Ej: 16:9, 4:3, 1:1"),
        SpecDef(key="image_file_format", label="Formato de imagen", tipo="string", prioridad=308, ayuda="Ej: JPEG, HEIF, RAW"),
        SpecDef(key="bit_depth", label="Profundidad de bits", tipo="string", prioridad=309),
        SpecDef(key="autofocus_sensitivity", label="Sensibilidad AF", tipo="string", prioridad=310),
        SpecDef(key="built_in_flash", label="Flash integrado", tipo="bool", prioridad=311),
        SpecDef(key="max_sync_speed", label="Velocidad sync máx", tipo="string", prioridad=312, ayuda="Para flash"),
        SpecDef(key="external_flash", label="Conexión flash externo", tipo="string", prioridad=313, ayuda="Ej: Shoe Mount, PC Sync"),
        SpecDef(key="built_in_cc", label="Filtro CC integrado", tipo="bool", prioridad=314, ayuda="Color correction"),
        SpecDef(key="internal_filter_holder", label="Porta-filtros interno", tipo="bool", prioridad=315),
        SpecDef(key="eye_point", label="Eye point (EVF)", tipo="string", prioridad=316),
        SpecDef(key="evf_coverage", label="Cobertura EVF", tipo="string", prioridad=317, ayuda="Porcentaje"),
        SpecDef(key="diopter_adjustment", label="Ajuste dióptrico (EVF)", tipo="string", prioridad=318),
        SpecDef(key="flash_modes", label="Modos de flash", tipo="string", prioridad=319),
        SpecDef(key="flash_compensation", label="Compensación flash", tipo="string", prioridad=320),
        SpecDef(key="dedicated_flash_system", label="Sistema flash dedicado", tipo="string", prioridad=321, ayuda="Ej: TTL, ADI / P-TTL"),
        SpecDef(key="color_filter_system", label="Filtro de color del sensor", tipo="string", prioridad=322, ayuda="Ej: Bayer RGB Primary"),
        SpecDef(key="scanning_system", label="Sistema de escaneo", tipo="string", prioridad=323, ayuda="Progressive / Interlaced"),
        SpecDef(key="processor", label="Procesador", tipo="string", prioridad=324),
        SpecDef(key="signal_system", label="Sistema de señal", tipo="string", prioridad=325, ayuda="NTSC/PAL"),
        SpecDef(key="system_frequency", label="Frecuencia de sistema", tipo="string", prioridad=326, ayuda="Hz disponibles"),
        SpecDef(key="time_code", label="Time code", tipo="string", prioridad=327),
        SpecDef(key="phantom_power", label="Phantom power", tipo="string", prioridad=328, ayuda="Para mics XLR. Ej: +48V"),
        SpecDef(key="shutter_angle", label="Ángulo de obturador", tipo="string", prioridad=329, ayuda="Solo cine. Ej: 0 a 360°"),
        SpecDef(key="digital_zoom", label="Zoom digital", tipo="string", prioridad=330),
        SpecDef(key="charging_time", label="Tiempo de carga", tipo="string", prioridad=331),
        SpecDef(key="battery_life", label="Duración estimada batería", tipo="string", prioridad=332),
        SpecDef(key="environmental_resistance", label="Resistencia ambiental", tipo="string", prioridad=333, ayuda="IP rating, water/dust resistant"),
        SpecDef(key="impact_resistance", label="Resistencia a impacto", tipo="string", prioridad=334),
        SpecDef(key="built_in_light", label="Luz integrada", tipo="bool", prioridad=335),
        SpecDef(key="built_in_speaker", label="Parlante integrado", tipo="bool", prioridad=336),
        SpecDef(key="creative_effects", label="Efectos creativos", tipo="string", prioridad=337, ayuda="Lista de efectos predefinidos"),
        SpecDef(key="rotation", label="Rotación", tipo="string", prioridad=338),
        SpecDef(key="built_in_controls", label="Controles integrados", tipo="string", prioridad=339),
        SpecDef(key="main_attachment", label="Montaje principal", tipo="string", prioridad=340),
        SpecDef(key="additional_mounting", label="Montajes adicionales", tipo="string", prioridad=341),
        SpecDef(key="connections", label="Conexiones (extras)", tipo="string", prioridad=342, ayuda="Conexiones específicas como Genlock, GPI"),
        SpecDef(key="package_quantity", label="Cantidad en paquete", tipo="string", prioridad=343),
        SpecDef(key="storage_capacity", label="Capacidad de almacenamiento", tipo="string", prioridad=344, ayuda="Para media incluida"),
        SpecDef(key="card_speed_rating", label="Velocidad de tarjeta (X)", tipo="string", prioridad=345),
        SpecDef(key="media_card_reader", label="Lector incluido", tipo="string", prioridad=346),
        SpecDef(key="host_connection", label="Conexión al host", tipo="string", prioridad=347),
        SpecDef(key="connector_1", label="Conector 1", tipo="string", prioridad=348),
        SpecDef(key="connector_2", label="Conector 2", tipo="string", prioridad=349),
        SpecDef(key="voltage_control", label="Control de voltaje", tipo="string", prioridad=350),
        SpecDef(key="cable_length", label="Largo del cable", tipo="string", prioridad=351),
    ],
)


# ─────────────────────────────────────────────────────────────────────
# Lentes
# ─────────────────────────────────────────────────────────────────────

_LENTES = CategoriaRegistry(
    nombre="Lentes",
    prioridad=20,
    grupo_visual="Óptica",
    sub_categorias=[
        SubCategoria(nombre="Zoom",       prioridad=10),
        SubCategoria(nombre="Fijo",       prioridad=20),
        SubCategoria(nombre="Vintage",    prioridad=30),
        SubCategoria(nombre="Especiales", prioridad=40),
        # Monturas: se crean on-the-fly según stock (no se declaran acá)
    ],
    specs=[
        SpecDef(
            key="lens_mount", label="Lens mount", tipo="enum",
            enum_options=LENS_MOUNT_ENUM,
            prioridad=10, en_card=True, en_filtros=True, en_nombre=True,
            destacado=True,
            es_compatibilidad=True, compatibilidad_modo="exacta",
        ),
        SpecDef(key="distancia_focal", label="Distancia focal", tipo="rango", unidad="mm",
                prioridad=15, en_card=True, en_nombre=True, destacado=True,
                ayuda="Lista: [v] si es fijo, [min, max] si es zoom"),
        SpecDef(key="apertura", label="Apertura", tipo="rango", unidad="f/",
                prioridad=20, en_card=True, en_nombre=True, destacado=True,
                ayuda="Lista: [v] si es fija, [min, max] si es variable"),
        SpecDef(
            key="formato", label="Formato", tipo="enum",
            enum_options=FORMATO_ENUM,
            prioridad=50, en_filtros=True, destacado=True,
            es_compatibilidad=True, compatibilidad_modo="jerarquia",
            rol_compatibilidad="contenedor",
        ),
        SpecDef(key="diametro_filtro", label="Diámetro de filtro", tipo="number", unidad="mm",
                prioridad=55, en_filtros=True,
                ayuda="Diámetro de la rosca del filtro frontal (ej. 67, 77, 82)",
                es_compatibilidad=True, compatibilidad_modo="exacta"),
        SpecDef(key="linea", label="Línea", tipo="string",
                prioridad=60, en_filtros=True, en_nombre=True,
                ayuda="Ej: Art, GM, L, Cinema, Master Prime"),
        SpecDef(key="angulo_vision", label="Ángulo de visión", tipo="rango", unidad="°",
                prioridad=65, ayuda="Lista: [v] fijo, [min, max] zoom"),
        SpecDef(key="distancia_minima_m", label="Distancia mínima de foco",
                tipo="number", unidad="cm", prioridad=70),
        SpecDef(key="magnificacion", label="Magnificación máxima", tipo="string",
                prioridad=75, ayuda="Ej: 0.32x"),
        SpecDef(key="hojas_diafragma", label="Hojas de diafragma", tipo="number",
                prioridad=78),
        SpecDef(key="estabilizacion", label="Estabilización óptica", tipo="bool",
                prioridad=80, en_filtros=True),
        SpecDef(key="autofocus", label="Autofocus", tipo="bool",
                prioridad=90, en_filtros=True),
        SpecDef(key="construccion_optica", label="Construcción óptica", tipo="string",
                prioridad=95, ayuda="Ej: 20 elementos / 15 grupos"),
        SpecDef(key="peso_g", label="Peso", tipo="number", unidad="g", prioridad=100),
        SpecDef(key="dimensiones", label="Dimensiones", tipo="string",
                prioridad=105, ayuda="Ej: Ø87.8 × 119.9 mm"),
        SpecDef(
            key="focus_type", label="Tipo de foco", tipo="enum",
            enum_options=["Autofocus", "Manual", "Autofocus / Manual"],
            prioridad=88, en_filtros=True,
        ),
        SpecDef(key="coating", label="Coating", tipo="string",
                prioridad=110, ayuda="Ej: Nano AR Coating II, ASC Coating, MRC Nano"),
        SpecDef(key="tripod_mounting", label="Collar para trípode", tipo="bool",
                prioridad=115, ayuda="Telefotos / cinema lenses pesados"),
    ],
)


# ─────────────────────────────────────────────────────────────────────
# Iluminación
# ─────────────────────────────────────────────────────────────────────

_ILUMINACION = CategoriaRegistry(
    nombre="Iluminación",
    prioridad=30,
    sub_categorias=[
        SubCategoria(nombre="LED Daylight", prioridad=10),
        SubCategoria(nombre="LED Bicolor",  prioridad=20),
        SubCategoria(nombre="LED RGB",      prioridad=30),
        SubCategoria(nombre="Tungsteno",    prioridad=40),
        SubCategoria(nombre="Flash",        prioridad=50),
    ],
    specs=[
        SpecDef(
            key="iluminacion_subtipo", label="Tipo", tipo="enum",
            enum_options=[
                "Flash", "Bulb / Lamp", "Panel", "Tube Light", "Flexible Mat",
                "Monolight", "COB Monolight", "Spotlight", "Fresnel", "On-Camera",
            ],
            prioridad=10, en_card=True, en_filtros=True, en_nombre=True,
            destacado=True, ayuda="Form factor del fixture",
        ),
        SpecDef(key="potencia_w", label="Potencia", tipo="number", unidad="W",
                prioridad=20, en_card=True, en_filtros=True, en_nombre=True, destacado=True),
        SpecDef(
            key="color_modes", label="Modos de color", tipo="multi_enum",
            enum_options=["RGB", "Daylight", "Tungsten", "HSI", "Bicolor variable"],
            prioridad=30, en_card=True, en_filtros=True, destacado=True,
        ),
        SpecDef(key="temperatura_k", label="Temperatura color", tipo="rango", unidad="K",
                prioridad=40, en_card=True, en_filtros=True,
                ayuda="Rango Kelvin. Si fijo: usar [v]; si variable: [min, max]"),
        SpecDef(key="cri", label="CRI", tipo="number",
                prioridad=50, en_filtros=True, ayuda="Color Rendering Index 0-100"),
        SpecDef(key="tlci", label="TLCI", tipo="number",
                prioridad=55, ayuda="Broadcast color rendering 0-100"),
        SpecDef(key="lumens_at_5600k", label="Lúmenes (5600K)", tipo="number", unidad="lm",
                prioridad=58, en_card=True, en_filtros=True,
                ayuda="Lúmenes totales a daylight — estándar de medición en cine/video"),
        SpecDef(key="lumens_at_3200k", label="Lúmenes (3200K)", tipo="number", unidad="lm",
                prioridad=60, en_filtros=True,
                ayuda="Lúmenes totales a tungsten. Las luces bicolor rinden menos a 3200K que a 5600K"),
        SpecDef(key="lux_at_1m_5600k", label="Lux a 1m (5600K)", tipo="number", unidad="lx",
                prioridad=62, ayuda="Estándar cine — Lux a 1m daylight"),
        SpecDef(key="lux_at_1m_3200k", label="Lux a 1m (3200K)", tipo="number", unidad="lx",
                prioridad=63, ayuda="Lux a 1m tungsten"),
        SpecDef(key="r9", label="R9", tipo="number", prioridad=65,
                ayuda="Deep red rendering 0-100"),
        SpecDef(key="dimming", label="Dimmer", tipo="bool",
                prioridad=70, en_filtros=True),
        SpecDef(
            key="control_inalambrico", label="Control inalámbrico", tipo="multi_enum",
            enum_options=["Bluetooth", "DMX", "RDM", "Wi-Fi", "CRMX", "Lumenradio", "Art-Net", "sACN"],
            prioridad=80, en_filtros=True,
        ),
        SpecDef(
            key="alimentacion", label="Alimentación", tipo="multi_enum",
            enum_options=["AC", "V-mount", "Gold Mount", "NP-F", "D-Tap", "USB-C", "Batería integrada"],
            prioridad=90, en_filtros=True,
        ),
        SpecDef(
            key="montaje", label="Montaje (modificador)", tipo="enum",
            enum_options=["Bowens", "Propietario", "Fresnel", "Profoto", "Elinchrom"],
            prioridad=100, en_filtros=True,
        ),
        SpecDef(key="peso_g", label="Peso", tipo="number", unidad="g",
                prioridad=110, ayuda="Peso del fixture solo, sin accesorios"),
        # ─── Energía / consumo ────────────────────────────────────────
        SpecDef(key="power_consumption_w", label="Consumo", tipo="number", unidad="W",
                prioridad=120, en_filtros=True),
        SpecDef(key="battery", label="Batería", tipo="string",
                prioridad=125, ayuda="Modelo de batería compatible (V-mount, NP-F970, etc.)"),
        SpecDef(key="power_pass_thru", label="Power pass-thru", tipo="bool",
                prioridad=130,
                ayuda="Permite operar con AC + batería como respaldo simultáneo"),
        # ─── Performance fotométrico ──────────────────────────────────
        SpecDef(key="beam_angle", label="Beam angle", tipo="string",
                prioridad=135, ayuda="Ángulo de haz. Ej: 45°, 15-45° (variable con lente)"),
        # ─── Hardware / control físico ────────────────────────────────
        SpecDef(
            key="cooling_system", label="Sistema de enfriamiento", tipo="enum",
            enum_options=["Active (Fan)", "Passive", "Smart Fan"],
            prioridad=140,
        ),
        SpecDef(key="display", label="Display integrado", tipo="string",
                prioridad=145, ayuda="Ej: OLED touchscreen, LCD"),
        SpecDef(key="umbrella_mount", label="Umbrella mount", tipo="bool",
                prioridad=150, en_filtros=True),
        SpecDef(key="effects", label="Efectos preprogramados", tipo="bool",
                prioridad=155,
                ayuda="Lightning, fire, TV, club, etc."),
        SpecDef(key="mobile_app_compatible", label="App móvil compatible", tipo="bool",
                prioridad=160),
        SpecDef(key="wireless_range_m", label="Alcance wireless", tipo="number", unidad="m",
                prioridad=165),
        # ─── Físico / ambiental ───────────────────────────────────────
        SpecDef(key="dimensions_mm", label="Dimensiones", tipo="string",
                prioridad=170, ayuda="Ej: 200 × 100 × 80 mm (W × H × D)"),
        SpecDef(key="environmental_resistance", label="Resistencia ambiental", tipo="string",
                prioridad=175, ayuda="Ej: IP54, IP65, Dust & Splash Resistant"),
        SpecDef(key="operating_conditions", label="Condiciones operativas", tipo="string",
                prioridad=180, ayuda="Ej: -10 to 45°C / 0-90% humidity"),
        # ─── Capturados de HTMLs B&H — completar ficha técnica ────────
        SpecDef(key="incluye_estuche", label="Estuche incluido", tipo="bool", prioridad=200),
        SpecDef(key="incluye_adapter_cable", label="Adapter / cable incluido", tipo="string", prioridad=201),
        SpecDef(key="incluye_adapter", label="Adapter de montaje incluido", tipo="string", prioridad=202),
        SpecDef(key="incluye_modificador", label="Modificador incluido", tipo="string", prioridad=203, ayuda="Softbox, grid, snoot, etc."),
        SpecDef(key="incluye_filtros", label="Filtros incluidos", tipo="string", prioridad=204),
        SpecDef(key="built_in_flash", label="Flash incorporado", tipo="bool", prioridad=205),
        SpecDef(key="inline_switch", label="Interruptor inline", tipo="bool", prioridad=206, ayuda="Switch en el cable de alimentación"),
        SpecDef(key="wireless_channels", label="Canales wireless", tipo="number", prioridad=207),
        SpecDef(key="wireless_groups", label="Grupos wireless", tipo="number", prioridad=208),
        SpecDef(key="wireless_frequency", label="Frecuencia wireless", tipo="string", prioridad=209, ayuda="Ej: 2.4 GHz"),
        SpecDef(key="certifications", label="Certificaciones", tipo="string", prioridad=210, ayuda="CE, FCC, RoHS, etc."),
        SpecDef(key="battery_charging", label="Recarga de batería", tipo="string", prioridad=211),
        SpecDef(key="auto_zoom_head", label="Zoom motorizado", tipo="bool", prioridad=212),
        SpecDef(key="bounce_adjustment", label="Bounce / ajuste vertical", tipo="string", prioridad=213),
        SpecDef(key="swivel_adjustment", label="Swivel / ajuste horizontal", tipo="string", prioridad=214),
        SpecDef(key="exposure_control", label="Control de exposición", tipo="string", prioridad=215),
        SpecDef(key="off_camera_terminal", label="Terminal off-camera", tipo="string", prioridad=216, ayuda="Ej: 2.5 mm jack para sync"),
        SpecDef(key="pixel_zones", label="Zonas de pixel", tipo="number", prioridad=217),
        SpecDef(key="flash_duration", label="Duración del flash", tipo="string", prioridad=218),
        SpecDef(key="recycle_time", label="Tiempo de recarga del flash", tipo="string", prioridad=219),
        SpecDef(key="secondary_illumination", label="Iluminación secundaria", tipo="string", prioridad=220, ayuda="Ej: Modeling Light"),
        SpecDef(key="flash_modes", label="Modos de flash", tipo="string", prioridad=221),
        SpecDef(key="power_range", label="Rango de potencia", tipo="string", prioridad=222, ayuda="Ej: 1/1 a 1/256"),
        SpecDef(key="flash_compensation", label="Compensación de flash", tipo="string", prioridad=223),
        SpecDef(key="external_power_pack", label="Compatible con power pack externo", tipo="bool", prioridad=224),
        SpecDef(key="materials", label="Materiales", tipo="string", prioridad=225),
        SpecDef(key="inputs_outputs", label="Conexiones físicas", tipo="string", prioridad=226, ayuda="DC IN, DMX IN/OUT, USB-C, AUX"),
    ],
)


# ─────────────────────────────────────────────────────────────────────
# Adaptadores
# ─────────────────────────────────────────────────────────────────────

_ADAPTADORES = CategoriaRegistry(
    nombre="Adaptadores",
    prioridad=25,
    grupo_visual="Óptica",
    sub_categorias=[],  # monturas on-the-fly
    specs=[
        SpecDef(
            key="adaptador_subtipo", label="Tipo", tipo="enum",
            enum_options=["Adaptador montura", "Speedbooster", "Macro tube"],
            prioridad=10, en_card=True, en_filtros=True, en_nombre=True,
            destacado=True, obligatorio=True, ayuda="Form factor",
        ),
        SpecDef(
            key="lens_mount", label="Lens mount", tipo="enum",
            enum_options=LENS_MOUNT_ENUM,
            prioridad=20, en_card=True, en_filtros=True, en_nombre=True,
            destacado=True, obligatorio=True,
            ayuda="Lado body (la rosca que se enchufa a la cámara)",
            es_compatibilidad=True, compatibilidad_modo="exacta",
        ),
        SpecDef(
            key="lens_mount_out", label="Lens mount — lado lente", tipo="enum",
            enum_options=LENS_MOUNT_ENUM,
            prioridad=30, en_card=True, en_filtros=True, en_nombre=True, destacado=True,
            ayuda="Rosca que recibe el lente del otro sistema",
        ),
        SpecDef(key="electronica", label="Comunicación electrónica", tipo="bool",
                prioridad=40, en_filtros=True,
                ayuda="Transmite AF/aperture del lente al body"),
        SpecDef(key="incluye_iris", label="Iris incluido", tipo="bool",
                prioridad=50,
                ayuda="Drop-in adapters con ND variable incorporado (Canon EF→RF)"),
        SpecDef(key="magnificacion", label="Magnificación", tipo="string",
                prioridad=60, ayuda="Solo speedboosters (ej. 0.71x)"),
        SpecDef(key="peso_g", label="Peso", tipo="number", unidad="g", prioridad=70),
        SpecDef(key="exposure_change", label="Cambio de exposición", tipo="string",
                prioridad=75,
                ayuda="Solo speedboosters. Ej: +1 stop, +1.33 stops"),
        SpecDef(key="materials", label="Materiales", tipo="string",
                prioridad=80, ayuda="Ej: Aluminum, Brass"),
        SpecDef(key="dimensions_mm", label="Dimensiones", tipo="string",
                prioridad=85),
    ],
)


# ─────────────────────────────────────────────────────────────────────
# Filtros
# ─────────────────────────────────────────────────────────────────────

_FILTROS = CategoriaRegistry(
    nombre="Filtros",
    prioridad=27,
    grupo_visual="Óptica",
    sub_categorias=[],  # diámetros on-the-fly
    specs=[
        SpecDef(
            key="filtro_subtipo", label="Tipo", tipo="enum",
            enum_options=[
                "Filtro ND", "Filtro polarizador", "Filtro UV",
                "Filtro variable", "Filtro difusión",
            ],
            prioridad=10, en_card=True, en_filtros=True, en_nombre=True,
            destacado=True, obligatorio=True, ayuda="Form factor",
        ),
        SpecDef(
            key="diametro_filtro", label="Diámetro de filtro", tipo="number", unidad="mm",
            prioridad=20, en_card=True, en_filtros=True, en_nombre=True,
            destacado=True, obligatorio=True,
            ayuda="Rosca del filter thread (67, 77, 82, etc.). Compartido con Lentes.",
            es_compatibilidad=True, compatibilidad_modo="exacta",
        ),
        SpecDef(key="densidad", label="Densidad ND", tipo="string",
                prioridad=30, en_filtros=True, en_nombre=True,
                ayuda="Ej: 1.2-Stop, 2-8 Stop (variable)"),
        SpecDef(
            key="material", label="Material", tipo="enum",
            enum_options=["Vidrio", "Resina", "Polímero"],
            prioridad=40, en_filtros=True, ayuda="Vidrio óptico es estándar",
        ),
        SpecDef(key="grade", label="Grado", tipo="string",
                prioridad=50, en_filtros=True, en_nombre=True,
                ayuda="Solo difusión: 1/8, 1/4, 1/2, 1, 2"),
        SpecDef(key="peso_g", label="Peso", tipo="number", unidad="g", prioridad=60),
        SpecDef(key="front_thread", label="Rosca frontal", tipo="string",
                prioridad=25, en_filtros=True,
                ayuda="Algunos filtros aceptan otros filtros encima (ej. 82mm front threading)"),
        SpecDef(key="ring_material", label="Material del aro", tipo="string",
                prioridad=45, ayuda="Ej: Aluminum, Brass"),
        SpecDef(key="coating", label="Coating", tipo="string",
                prioridad=48, ayuda="Ej: Multi-coated, Nano-X, IRND"),
        SpecDef(key="thickness_mm", label="Espesor", tipo="number", unidad="mm",
                prioridad=55, ayuda="Filtros slim son <5mm. Importa con grandes angulares"),
    ],
)


# ─────────────────────────────────────────────────────────────────────
# REGISTRY — punto de entrada único
# ─────────────────────────────────────────────────────────────────────

REGISTRY: Registry = Registry(categorias={
    "Cámaras":     _CAMARAS,
    "Lentes":      _LENTES,
    "Iluminación": _ILUMINACION,
    "Adaptadores": _ADAPTADORES,
    "Filtros":     _FILTROS,
})


def all_categorias() -> list[CategoriaRegistry]:
    return list(REGISTRY.categorias.values())


def get_categoria(nombre: str) -> CategoriaRegistry | None:
    return REGISTRY.get(nombre)


def get_spec(categoria_raiz: str, spec_key: str) -> SpecDef | None:
    cat = REGISTRY.get(categoria_raiz)
    return cat.get_spec(spec_key) if cat else None
