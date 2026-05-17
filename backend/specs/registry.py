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
        # Video > monturas (taxonomía 2-niveles)
        SubCategoria(nombre="Montura E",   prioridad=10, parent="Video"),
        SubCategoria(nombre="Montura RF",  prioridad=20, parent="Video"),
        SubCategoria(nombre="Montura EF",  prioridad=30, parent="Video"),
        SubCategoria(nombre="Montura L",   prioridad=40, parent="Video"),
        SubCategoria(nombre="Montura Z",   prioridad=50, parent="Video"),
        SubCategoria(nombre="Montura PL",  prioridad=60, parent="Video"),
        SubCategoria(nombre="Montura BMD", prioridad=70, parent="Video"),
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
                prioridad=60, en_filtros=True, ayuda="Lúmenes totales a daylight"),
        SpecDef(key="lumens_at_3200k", label="Lúmenes (3200K)", tipo="number", unidad="lm",
                prioridad=61, ayuda="Lúmenes totales a tungsten"),
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
