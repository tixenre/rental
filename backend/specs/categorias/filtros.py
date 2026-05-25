"""Specs canónicas de Filtros (ND, Polarizador, UV, Variable, Difusión).

`diametro_filtro` matchea con Lentes.diametro_filtro (compat="exacta") y
también participa de la generación de sub-cats (rosca on-the-fly según stock:
77mm, 82mm, ...).
"""

from __future__ import annotations

from ..models import CategoriaRegistry, SpecDef
from ..shared import peso_g


CAT = CategoriaRegistry(
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
        SpecDef(key="front_thread", label="Rosca frontal", tipo="string",
                prioridad=25, en_filtros=True,
                ayuda="Algunos filtros aceptan otros filtros encima (ej. 82mm front threading)"),
        SpecDef(key="densidad", label="Densidad ND", tipo="string",
                prioridad=30, en_filtros=True, en_nombre=True,
                ayuda="Ej: 1.2-Stop, 2-8 Stop (variable)"),
        SpecDef(
            key="material", label="Material", tipo="enum",
            enum_options=["Vidrio", "Resina", "Polímero"],
            prioridad=40, en_filtros=True, ayuda="Vidrio óptico es estándar",
        ),
        SpecDef(key="ring_material", label="Material del aro", tipo="string",
                prioridad=45, ayuda="Ej: Aluminum, Brass"),
        SpecDef(key="coating", label="Coating", tipo="string",
                prioridad=48, ayuda="Ej: Multi-coated, Nano-X, IRND"),
        SpecDef(key="grade", label="Grado", tipo="string",
                prioridad=50, en_filtros=True, en_nombre=True,
                ayuda="Solo difusión: 1/8, 1/4, 1/2, 1, 2"),
        SpecDef(key="thickness_mm", label="Espesor", tipo="number", unidad="mm",
                prioridad=55, ayuda="Filtros slim son <5mm. Importa con grandes angulares"),
        peso_g(prioridad=60, en_filtros=False),
    ],
)
