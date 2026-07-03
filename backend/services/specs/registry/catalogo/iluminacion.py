"""Specs canónicas de Iluminación (LED Daylight/Bicolor/RGB, Tungsteno, Flash).

`montura_luz` matchea con Modificadores.montura_luz (motor de compat → exacta)
para conectar fixture ↔ softbox/spotlight/fresnel-lens.
"""

from __future__ import annotations

from ..models import CategoriaRegistry, SpecDef
from ..shared import beam_angle, dimensions_mm, materials, montura_luz, peso_g


CAT = CategoriaRegistry(
    nombre="Iluminación",
    specs=[
        # ─── Identidad ────────────────────────────────────────────────
        SpecDef(
            key="iluminacion_subtipo", label="Tipo", tipo="enum",
            enum_options=[
                "Flash", "Foco", "Panel", "Tube Light", "Flexible Mat",
                "Monoled", "Fresnel", "On-Camera",
            ],
            prioridad=10, en_card=True, en_filtros=True, en_nombre=True,
            destacado=True, ayuda="Form factor del fixture",
        ),
        # Watts = consumo eléctrico del fixture (no potencia óptica — esa son lúmenes).
        SpecDef(key="consumo_w", label="Consumo eléctrico", tipo="number", unidad="W",
                prioridad=20, en_card=True, en_filtros=True, en_nombre=True, destacado=True,
                aliases=["Power", "Wattage", "Power Consumption", "Power Draw",
                         "Power Input", "Rated Power"]),
        SpecDef(
            key="color_modes", label="Modos de color", tipo="multi_enum",
            enum_options=["RGB", "Bicolor", "Daylight", "Tungsten"],
            prioridad=30, en_card=True, en_filtros=True, destacado=True,
            ayuda="Si una luz es bicolor (variable Daylight↔Tungsten) marcala como Bicolor, no las dos por separado.",
        ),
        SpecDef(key="temperatura_k", label="Temperatura color", tipo="rango", unidad="K",
                prioridad=40, en_card=True, en_filtros=True,
                ayuda="Rango Kelvin. Si fijo: usar [v]; si variable: [min, max]",
                aliases=["Color Temperature", "Color Temperature Range", "Color Temp",
                         "Color Temp Range"]),
        # ─── Fotométrico ──────────────────────────────────────────────
        SpecDef(key="cri", label="CRI", tipo="number",
                prioridad=50, en_filtros=True, ayuda="Color Rendering Index 0-100",
                aliases=["Color Rendering Index", "CRI Value", "Ra", "CRI (Ra)"]),
        SpecDef(key="tlci", label="TLCI", tipo="number",
                prioridad=55, ayuda="Broadcast color rendering 0-100"),
        SpecDef(key="lumens_at_5600k", label="Lúmenes (5600K)", tipo="number", unidad="lm",
                prioridad=58, en_card=True, en_filtros=True,
                ayuda="Lúmenes totales a daylight sin modificador — estándar de medición en cine/video",
                aliases=["Luminous Flux", "Lumen Output", "Brightness", "Total Lumens"]),
        SpecDef(key="lumens_at_3200k", label="Lúmenes (3200K)", tipo="number", unidad="lm",
                prioridad=60, en_filtros=True,
                ayuda="Lúmenes totales a tungsten sin modificador. Las luces bicolor rinden menos a 3200K que a 5600K"),
        # Lux: fuente para derivar lúmenes cuando el fabricante no los reporta.
        # Convención: siempre sin modificador/difusor (fixture desnudo).
        # Los lúmenes se derivan automáticamente al persistir si se tiene beam_angle.
        SpecDef(key="lux_at_1m_5600k", label="Lux a 1m (5600K)", tipo="number", unidad="lx",
                prioridad=62,
                ayuda="Iluminancia a 1m sin modificador, daylight. Se usa para derivar lúmenes.",
                aliases=["Illuminance (at 1 Meter, Daylight)", "Lux at 1m (Daylight)",
                         "Illuminance (5600K)", "Lux (Daylight)", "Illuminance at 1m"]),
        SpecDef(key="lux_at_1m_3200k", label="Lux a 1m (3200K)", tipo="number", unidad="lx",
                prioridad=63,
                ayuda="Iluminancia a 1m sin modificador, tungsten.",
                aliases=["Illuminance (at 1 Meter, Tungsten)", "Lux at 1m (Tungsten)",
                         "Illuminance (3200K)", "Lux (Tungsten)"]),
        SpecDef(key="r9", label="R9", tipo="number", prioridad=65,
                ayuda="Deep red rendering 0-100"),
        # ─── Control ──────────────────────────────────────────────────
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
        # Lado-luz del acople con modificadores. MISMA key + enum que
        # `montura_luz` de Modificadores → motor de compat matchea
        # automáticamente luz↔softbox/spotlight/fresnel-lens.
        montura_luz(
            prioridad=100,
            ayuda="Acople con modificadores. 'Sin montura' = no acepta modificadores estándar (fresnels tradicionales).",
        ),
        peso_g(prioridad=110, ayuda="Peso del fixture solo, sin accesorios"),
        # ─── Energía / consumo ────────────────────────────────────────
        SpecDef(key="battery", label="Batería", tipo="string",
                prioridad=125, ayuda="Modelo de batería compatible (V-mount, NP-F970, etc.)"),
        SpecDef(key="power_pass_thru", label="Power pass-thru", tipo="bool",
                prioridad=130,
                ayuda="Permite operar con AC + batería como respaldo simultáneo"),
        # ─── Performance fotométrico ──────────────────────────────────
        # tipo=rango: [v] fijo, [min, max] variable. Mismo patrón que
        # `angulo_vision` en Lentes y `beam_angle` en Modificadores.
        # beam_angle se usa también para derivar lúmenes desde lux (spec_coerce).
        beam_angle(
            prioridad=135,
            ayuda="[v] fijo, [min, max] variable (zoom Fresnel/spotlight)",
        ),
        # ─── Hardware / control físico ────────────────────────────────
        SpecDef(
            key="cooling_system", label="Sistema de enfriamiento", tipo="enum",
            enum_options=["Active (Fan)", "Passive", "Smart Fan"],
            prioridad=140,
        ),
        SpecDef(key="display", label="Display integrado", tipo="string",
                prioridad=145, ayuda="Ej: OLED touchscreen, LCD"),
        SpecDef(key="umbrella_mount", label="Montura paraguas", tipo="bool",
                prioridad=150, en_filtros=True),
        SpecDef(key="effects", label="Efectos preprogramados", tipo="bool",
                prioridad=155,
                ayuda="Lightning, fire, TV, club, etc."),
        SpecDef(key="mobile_app_compatible", label="App móvil compatible", tipo="bool",
                prioridad=160, en_filtros=True),
        SpecDef(key="wireless_range_m", label="Alcance wireless", tipo="number", unidad="m",
                prioridad=165),
        # ─── Físico / ambiental ───────────────────────────────────────
        dimensions_mm(prioridad=170, ayuda="Ej: 200 × 100 × 80 mm (W × H × D)"),
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
        SpecDef(key="inline_switch", label="Interruptor inline", tipo="bool", prioridad=206, ayuda="Switch en el cable de alimentación"),
        SpecDef(key="wireless_channels", label="Canales wireless", tipo="number", prioridad=207),
        SpecDef(key="wireless_groups", label="Grupos wireless", tipo="number", prioridad=208),
        SpecDef(key="wireless_frequency", label="Frecuencia wireless", tipo="string", prioridad=209, ayuda="Ej: 2.4 GHz"),
        SpecDef(key="certifications", label="Certificaciones", tipo="string", prioridad=210, ayuda="CE, FCC, RoHS, etc."),
        SpecDef(key="battery_charging", label="Recarga de batería", tipo="string", prioridad=211),
        SpecDef(key="auto_zoom_head", label="Zoom motorizado", tipo="bool", prioridad=212),
        SpecDef(key="pixel_zones", label="Zonas de pixel", tipo="number", prioridad=217),
        SpecDef(key="secondary_illumination", label="Iluminación secundaria", tipo="string", prioridad=220, ayuda="Ej: Modeling Light"),
        SpecDef(key="power_range", label="Rango de potencia", tipo="string", prioridad=222, ayuda="Ej: 1/1 a 1/256"),
        materials(prioridad=225),
        SpecDef(key="inputs_outputs", label="Conexiones físicas", tipo="string", prioridad=226, ayuda="DC IN, DMX IN/OUT, USB-C, AUX"),
    ],
)
