"""Specs canónicas de Filtros (ND, Polarizador, UV, Variable, Difusión).

`diametro_filtro` matchea con Lentes.diametro_filtro (compat="exacta") y
también participa de la generación de sub-cats (rosca on-the-fly según stock:
77mm, 82mm, ...).
"""

from __future__ import annotations

from ..models import CategoriaRegistry, SpecDef
from ..shared import coating, diametro_filtro, peso_g


CAT = CategoriaRegistry(
    nombre="Filtros",
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
        diametro_filtro(
            prioridad=20, en_card=True, en_nombre=True, destacado=True, obligatorio=True,
            ayuda="Rosca del filter thread (67, 77, 82, etc.). Compartido con Lentes.",
        ),
        SpecDef(key="front_thread", label="Rosca frontal", tipo="string",
                prioridad=25, en_filtros=True,
                ayuda="Algunos filtros aceptan otros filtros encima (ej. 82mm front threading)"),
        SpecDef(key="densidad", label="Densidad ND", tipo="string",
                prioridad=30, en_filtros=True, en_nombre=True,
                ayuda="SOLO Filtro ND/variable — ej: 1.2-Stop, 2-8 Stop (variable). "
                      "Para pérdida de luz de OTROS subtipos (polarizador, difusión) "
                      "usar light_loss_stops, no este campo.",
                aliases=["Optical Density", "ND Density", "Density", "Stop Reduction",
                         "Filter Factor"]),
        # Mismo concepto que Modificadores.light_loss_stops (número plano en
        # stops), pero acá vive aparte: "densidad" arriba es semánticamente
        # la DENSIDAD ND del producto (su identidad como filtro ND), mientras
        # que esto es la pérdida de luz incidental de CUALQUIER filtro
        # (ej. un polarizador circular pierde ~1.2 stops sin ser "ND").
        # B&H reporta ambos bajo el mismo label "Exposure Reduction" —
        # el parser (map_filtro_specs) desambigua por filtro_subtipo, no
        # renombra el campo según lo que sea más conveniente.
        SpecDef(key="light_loss_stops", label="Pérdida de luz", tipo="number",
                unidad="stops", prioridad=32, en_filtros=True,
                ayuda="Pérdida de exposición del filtro en stops (no es densidad ND)",
                aliases=["Exposure Reduction", "Light Loss"]),
        SpecDef(
            key="material", label="Material", tipo="enum",
            enum_options=["Vidrio", "Resina", "Polímero"],
            prioridad=40, en_filtros=True, ayuda="Vidrio óptico es estándar",
        ),
        SpecDef(key="ring_material", label="Material del aro", tipo="string",
                prioridad=45, ayuda="Ej: Aluminum, Brass"),
        coating(prioridad=48, ayuda="Ej: Multi-coated, Nano-X, IRND"),
        SpecDef(key="grade", label="Grado", tipo="string",
                prioridad=50, en_filtros=True, en_nombre=True,
                ayuda="Solo difusión: 1/8, 1/4, 1/2, 1, 2"),
        SpecDef(key="thickness_mm", label="Espesor", tipo="number", unidad="mm",
                prioridad=55, ayuda="Filtros slim son <5mm. Importa con grandes angulares"),
        peso_g(prioridad=60, en_filtros=False),
    ],
)
