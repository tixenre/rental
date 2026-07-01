"""Specs canónicas de Lentes (Zoom, Fijo, Vintage, Especiales).

Compat con Cámaras (mismo lens_mount → exacta) y formato_sensor (jerarquía:
el lente es el "contenedor" porque proyecta sobre el sensor; la cámara
es el "contenido").
"""

from __future__ import annotations

from ..models import CategoriaRegistry, SpecDef, SubCategoria
from ..shared import (
    FORMATO_ENUM, LENS_MOUNT_ENUM,
    autofocus, coating, diametro_filtro, estabilizacion,
    dimensions_mm, peso_g,
)


CAT = CategoriaRegistry(
    nombre="Lentes",
    prioridad=20,
    grupo_visual="Óptica",
    sub_categorias=[
        SubCategoria(nombre="Zoom",       prioridad=10),
        SubCategoria(nombre="Fijo",       prioridad=20),
        SubCategoria(nombre="Vintage",    prioridad=30),
        SubCategoria(nombre="Especiales", prioridad=40),
        # Monturas: se crean on-the-fly según stock
    ],
    specs=[
        SpecDef(
            key="lens_mount", label="Montura", tipo="enum",
            enum_options=LENS_MOUNT_ENUM,
            prioridad=10, en_card=True, en_filtros=True, en_nombre=True,
            destacado=True,
            es_compatibilidad=True, compatibilidad_modo="exacta",
            aliases=["Mount", "Lens Mounting", "Mount Type"],
        ),
        SpecDef(key="distancia_focal", label="Distancia focal", tipo="rango", unidad="mm",
                prioridad=15, en_card=True, en_nombre=True, destacado=True,
                ayuda="Lista: [v] si es fijo, [min, max] si es zoom",
                aliases=["Focal Length", "Focal Length Range", "Focal Range"]),
        SpecDef(key="apertura", label="Apertura", tipo="rango", unidad="f/",
                prioridad=20, en_card=True, en_nombre=True, destacado=True,
                ayuda="Lista: [v] si es fija, [min, max] si es variable",
                aliases=["Maximum Aperture", "Aperture Range", "Max Aperture",
                         "Minimum/Maximum Aperture"]),
        SpecDef(
            key="formato", label="Formato", tipo="enum",
            enum_options=FORMATO_ENUM,
            prioridad=50, en_filtros=True, destacado=True,
            es_compatibilidad=True, compatibilidad_modo="jerarquia",
            rol_compatibilidad="contenedor",
            aliases=["Image Circle", "Coverage", "Sensor Coverage"],
            # Sinónimos de VALOR (embudo #1163 F3) — abreviaturas de uso real,
            # no variantes de formato (esas ya matchean por normalización).
            value_aliases={"Full-frame": ["FF"], "Super 35": ["S35"]},
        ),
        diametro_filtro(
            prioridad=55,
            ayuda="Diámetro de la rosca del filtro frontal (ej. 67, 77, 82)",
        ),
        SpecDef(key="linea", label="Línea", tipo="string",
                prioridad=60, en_filtros=True, en_nombre=True,
                ayuda="Ej: Art, GM, L, Cinema, Master Prime"),
        SpecDef(key="angulo_vision", label="Ángulo de visión", tipo="rango", unidad="°",
                prioridad=65, ayuda="Lista: [v] fijo, [min, max] zoom",
                aliases=["Angle of View", "Diagonal Angle of View", "Field of View"]),
        # distancia_minima_cm: la unidad canónica es cm (antes la key decía '_m'
        # pero la unidad ya era cm — renombrada por #535 para alinear key↔unidad).
        SpecDef(key="distancia_minima_cm", label="Distancia mínima de foco",
                tipo="number", unidad="cm", prioridad=70),
        SpecDef(key="magnificacion", label="Magnificación máxima", tipo="string",
                prioridad=75, ayuda="Ej: 0.32x"),
        SpecDef(key="hojas_diafragma", label="Hojas de diafragma", tipo="number",
                prioridad=78),
        estabilizacion(prioridad=80),
        autofocus(prioridad=90),
        SpecDef(key="construccion_optica", label="Construcción óptica", tipo="string",
                prioridad=95, ayuda="Ej: 20 elementos / 15 grupos"),
        peso_g(prioridad=100),
        dimensions_mm(prioridad=105, ayuda="Ej: Ø87.8 × 119.9 mm"),
        coating(prioridad=110, ayuda="Ej: Nano AR Coating II, ASC Coating, MRC Nano"),
        SpecDef(key="tripod_mounting", label="Collar para trípode", tipo="bool",
                prioridad=115, ayuda="Telefotos / cinema lenses pesados"),
    ],
)
