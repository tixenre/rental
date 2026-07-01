"""Specs ópticas reusables entre categorías.

coating, diametro_filtro, estabilizacion, autofocus aparecen en Filtros/Lentes
(las dos primeras) y Cámaras/Lentes (las dos últimas). Las aliases de cada
call-site original están unificadas acá — ninguna categoría pierde cobertura
de match y todas ganan las aliases que les faltaban.
"""

from __future__ import annotations

from ..models import SpecDef


def coating(
    prioridad: int = 80,
    ayuda: str | None = None,
) -> SpecDef:
    """Tipo de coating óptico. tipo=string."""
    return SpecDef(
        key="coating", label="Coating", tipo="string",
        prioridad=prioridad,
        ayuda=ayuda,
    )


def diametro_filtro(
    prioridad: int = 55,
    en_card: bool = False,
    en_nombre: bool = False,
    destacado: bool = False,
    obligatorio: bool = False,
    ayuda: str | None = None,
) -> SpecDef:
    """Diámetro de rosca de filtro en mm. tipo=number unidad=mm.

    Aliases: unión de Filtros + Lentes (Filter Thread Size, Front Filter Size, etc.).
    es_compatibilidad=exacta en ambas categorías — hardcodeado en la factory.
    """
    return SpecDef(
        key="diametro_filtro", label="Diámetro de filtro", tipo="number", unidad="mm",
        prioridad=prioridad, en_card=en_card, en_filtros=True, en_nombre=en_nombre,
        destacado=destacado, obligatorio=obligatorio,
        ayuda=ayuda,
        es_compatibilidad=True, compatibilidad_modo="exacta",
        aliases=[
            "Filter Size", "Filter Diameter", "Thread Size",
            "Filter Thread Size", "Filter Thread",
            "Front Filter Size", "Front Filter Diameter",
        ],
    )


def estabilizacion(
    prioridad: int = 80,
) -> SpecDef:
    """Estabilización óptica / IBIS. tipo=bool.

    Aliases: unión de Cámaras (Image Stabilization, IBIS) + Lentes (sin aliases propios).
    en_filtros=True en ambas categorías — hardcodeado.
    """
    return SpecDef(
        key="estabilizacion", label="Estabilización óptica", tipo="bool",
        prioridad=prioridad, en_filtros=True,
        aliases=["Image Stabilization", "In-Body Image Stabilization", "IBIS"],
    )


def autofocus(
    prioridad: int = 85,
) -> SpecDef:
    """Autofocus disponible. tipo=bool.

    Aliases: unión de Cámaras (Auto Focus, Autofocus System, Focus System)
    + Lentes (sin aliases propios).
    en_filtros=True en ambas categorías — hardcodeado.
    """
    return SpecDef(
        key="autofocus", label="Autofocus", tipo="bool",
        prioridad=prioridad, en_filtros=True,
        aliases=["Auto Focus", "Autofocus System", "Focus System"],
    )
