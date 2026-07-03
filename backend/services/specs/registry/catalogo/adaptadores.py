"""Specs canónicas de Adaptadores de lente (Adaptador montura, Speedbooster,
Macro tube). Bisagra que conecta `lens_mount` (lado-body, una cámara) con
`lens_mount_out` (lado-lente, otro sistema). Ambos son compat="exacta"."""

from __future__ import annotations

from ..models import CategoriaRegistry, SpecDef
from ..shared import LENS_MOUNT_ENUM, dimensions_mm, peso_g


CAT = CategoriaRegistry(
    nombre="Adaptadores",
    specs=[
        SpecDef(
            key="adaptador_subtipo", label="Tipo", tipo="enum",
            enum_options=["Adaptador montura", "Speedbooster", "Macro tube"],
            prioridad=10, en_card=True, en_filtros=True, en_nombre=True,
            destacado=True, obligatorio=True, ayuda="Form factor",
        ),
        SpecDef(
            key="lens_mount", label="Montura", tipo="enum",
            enum_options=LENS_MOUNT_ENUM,
            prioridad=20, en_card=True, en_filtros=True, en_nombre=True,
            destacado=True, obligatorio=True,
            ayuda="Lado body (la rosca que se enchufa a la cámara)",
            es_compatibilidad=True, compatibilidad_modo="exacta",
            aliases=["Camera Mount", "Body Mount", "Camera-Side Mount", "Rear Mount"],
        ),
        SpecDef(
            key="lens_mount_out", label="Montura — lado lente", tipo="enum",
            enum_options=LENS_MOUNT_ENUM,
            prioridad=30, en_card=True, en_filtros=True, en_nombre=True, destacado=True,
            ayuda="Rosca que recibe el lente del otro sistema",
            es_compatibilidad=True, compatibilidad_modo="exacta",
            aliases=["Lens Compatibility", "Lens Mount (Front)", "Front Mount",
                     "Accepted Lens Mount"],
        ),
        SpecDef(key="electronica", label="Comunicación electrónica", tipo="bool",
                prioridad=40, en_filtros=True,
                ayuda="Transmite AF/aperture del lente al body"),
        SpecDef(key="incluye_iris", label="Iris incluido", tipo="bool",
                prioridad=50,
                ayuda="Drop-in adapters con ND variable incorporado (Canon EF→RF)"),
        SpecDef(key="magnificacion", label="Magnificación", tipo="string",
                prioridad=60, ayuda="Solo speedboosters (ej. 0.71x)"),
        peso_g(prioridad=70, en_filtros=False),
        SpecDef(key="exposure_change", label="Cambio de exposición", tipo="string",
                prioridad=75,
                ayuda="Solo speedboosters. Ej: +1 stop, +1.33 stops"),
        dimensions_mm(prioridad=85),
    ],
)
