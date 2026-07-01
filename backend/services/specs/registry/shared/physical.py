"""Specs físicas reusables entre categorías.

Estas tres specs aparecen en casi todas las cats (peso, dimensiones,
materiales) con definición idéntica (label/tipo/unidad/ayuda) y solo
varían en `prioridad` y `en_filtros` según la categoría. Las exponemos
como factory functions con defaults razonables — cada cat puede
overrideear los flags que cambien.

Ejemplo:
    from ..shared import physical

    specs=[
        # peso con prio=100 (cámaras), filtrable
        physical.peso_g(prioridad=100),
        # dimensiones sin override (usa defaults)
        physical.dimensions_mm(),
        # materiales con prio custom + ayuda específica de la cat
        physical.materials(prioridad=235, ayuda="Ej: Magnesium, Polycarbonate"),
    ]

Por qué factory en vez de instancia compartida: pydantic.BaseModel es
inmutable después de construido, así que cada cat necesita su propia
instancia con su `prioridad`. La factory mantiene UNA fuente de verdad
del label/tipo/unidad/ayuda y deja que cada cat elija dónde la pone.
"""

from __future__ import annotations

from ..models import SpecDef


def peso_g(
    prioridad: int = 110,
    en_filtros: bool = True,
    ayuda: str | None = None,
) -> SpecDef:
    """Peso del equipo en gramos. tipo=number unidad=g."""
    return SpecDef(
        key="peso_g", label="Peso", tipo="number", unidad="g",
        prioridad=prioridad, en_filtros=en_filtros,
        ayuda=ayuda,
        aliases=["Weight", "Net Weight", "Weight (Body Only)", "Product Weight"],
    )


def dimensions_mm(
    prioridad: int = 170,
    ayuda: str | None = None,
) -> SpecDef:
    """Dimensiones del equipo como string formateado. tipo=string.

    Convención: 'W × H × D mm' (Cámaras/Iluminación) o 'ø × H cm'
    (Modificadores redondos). El valor exacto lo decide el parser de
    cada cat. Acá solo declaramos que la key y el label son comunes.
    """
    return SpecDef(
        key="dimensions_mm", label="Dimensiones", tipo="string",
        prioridad=prioridad,
        ayuda=ayuda or "Ej: 129.7 × 77.8 × 84.5 mm (W × H × D)",
    )


def materials(
    prioridad: int = 100,
    ayuda: str | None = None,
) -> SpecDef:
    """Materiales de construcción como string libre. tipo=string."""
    return SpecDef(
        key="materials", label="Materiales", tipo="string",
        prioridad=prioridad,
        ayuda=ayuda,
    )
