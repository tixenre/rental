"""Specs canónicas de Modificadores (Softbox / Spotlight / Fresnel-lens /
Difusión-Frame). Se acoplan a una luz vía `montura_luz` (compat con
Iluminación.montura_luz)."""

from __future__ import annotations

from ..models import CategoriaRegistry, SpecDef, SubCategoria
from ..shared import beam_angle, dimensions_mm, materials, montura_luz, peso_g


CAT = CategoriaRegistry(
    nombre="Modificadores",
    prioridad=40,
    grupo_visual="Iluminación",
    sub_categorias=[
        SubCategoria(nombre="Softbox",          prioridad=10),
        SubCategoria(nombre="Fresnel",          prioridad=20),
        SubCategoria(nombre="Spotlight",        prioridad=30),
        SubCategoria(nombre="Difusión / Frame", prioridad=40),
    ],
    specs=[
        # Subtipo: rol/función del modificador. La forma geométrica va en
        # `forma` por separado (un Softbox puede ser Parabolic, Octagonal,
        # Hexadecagon, Lantern, etc. — no mezclar).
        SpecDef(
            key="modificador_subtipo", label="Tipo", tipo="enum",
            enum_options=[
                "Softbox", "Spotlight", "Fresnel",
                "Difusor", "Bandera Negra", "Reflector",
            ],
            prioridad=10, en_card=True, en_filtros=True, en_nombre=True,
            destacado=True, ayuda="Función del modificador",
            aliases=["Item Type", "Type", "Modifier Type", "Light Shaping Tool"],
        ),
        SpecDef(
            key="forma", label="Forma", tipo="enum",
            enum_options=[
                "Octagonal", "Parabolic", "Hexadecagon", "Lantern Round",
                "Strip", "Square", "Rectangle", "Deep", "Oval",
            ],
            prioridad=20, en_filtros=True,
            ayuda="Geometría del difusor (aplica a Softbox/Lantern)",
            aliases=["Shape", "Softbox Shape"],
        ),
        SpecDef(key="diametro_cm", label="Diámetro", tipo="number", unidad="cm",
                prioridad=30, en_card=True, en_filtros=True, destacado=True,
                ayuda="Para softboxes redondos/octagonales y bola china",
                aliases=["Diameter", "Open Diameter", "Lens Diameter", "Size"]),
        dimensions_mm(
            prioridad=35,
            ayuda="Open: ø: 89 × H: 60 cm. Para softboxes hexagonales / rectangulares.",
        ),
        # Misma key + enum que `montura_luz` en Iluminación → motor de
        # compat matchea automáticamente.
        montura_luz(
            prioridad=40, en_card=True, destacado=True,
            ayuda="Lado-luz: cómo se acopla a la fuente. Compat con Iluminación.",
        ),
        # Semántica: viene CON grid en el kit. "Acepta grid pero se vende
        # aparte" → False (no lo tenemos disponible).
        SpecDef(key="incluye_grid", label="Incluye grid", tipo="bool",
                prioridad=50, en_filtros=True,
                ayuda="Grid de panal incluido en el kit (no 'acepta pero se vende aparte')",
                aliases=["Accepts Grids", "Grid", "Grid Included", "Includes Grid", "Honeycomb Grid"]),
        SpecDef(key="incluye_difusor", label="Difusor interno", tipo="bool",
                prioridad=55,
                ayuda="Interior baffle (capa difusora removible)",
                aliases=["Interior Baffle", "Diffuser", "Internal Baffle", "Diffusion", "Front Diffuser"]),
        SpecDef(key="plegable", label="Plegable", tipo="bool",
                prioridad=60, en_filtros=True,
                ayuda="Quick-Open / Foldable / Click-Lock",
                aliases=["Quick Open Type", "Foldable", "Collapsible", "Quick-Open", "Quick Release"]),
        # Number en stops. 0 = sin pérdida; None = no medido por el fabricante.
        SpecDef(key="light_loss_stops", label="Pérdida de luz", tipo="number",
                unidad="stops", prioridad=65,
                ayuda="Pérdida con difusor (1-stop loss → 1.0). 0 = sin pérdida",
                aliases=["Light Loss/Gain", "Light Loss", "Stop Loss", "F-Stop Loss"]),
        # Rango con unidad ° — mismo patrón que `angulo_vision` en Lentes.
        # [36] = ángulo fijo; [10, 45] = zoom Fresnel.
        beam_angle(
            prioridad=75,
            ayuda="Solo Spotlight/Fresnel. [v] fijo, [min, max] variable",
        ),
        materials(prioridad=100, ayuda="Ej: Fabric, Steel, Glass"),
        peso_g(prioridad=110),
    ],
)
