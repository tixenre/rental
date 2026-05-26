"""Specs de iluminación reusables entre categorías.

montura_luz y beam_angle aparecen en Iluminación y Modificadores con aliases
divergentes. Las aliases están unificadas acá — ambas categorías ganan
cobertura de match completa.
"""

from __future__ import annotations

from ..models import SpecDef
from .enums import MONTURA_LUZ_ENUM


def montura_luz(
    prioridad: int = 70,
    en_card: bool = False,
    destacado: bool = False,
    ayuda: str | None = None,
) -> SpecDef:
    """Montura de acople luz ↔ modificador. tipo=enum.

    Aliases: unión de Iluminación (Mount Standard, Strobe Mount Type, Mounting System)
    + Modificadores (Strobe Mount, Mount Type, Mounting Type).
    en_filtros=True y es_compatibilidad=exacta en ambas — hardcodeado.
    """
    return SpecDef(
        key="montura_luz", label="Montura a la luz", tipo="enum",
        enum_options=MONTURA_LUZ_ENUM,
        prioridad=prioridad, en_card=en_card, en_filtros=True, destacado=destacado,
        ayuda=ayuda,
        es_compatibilidad=True, compatibilidad_modo="exacta",
        aliases=[
            "Bowens Mount", "Light Mount",
            "Mount Standard", "Strobe Mount Type", "Mounting System",
            "Strobe Mount", "Mount Type", "Mounting Type",
        ],
    )


def beam_angle(
    prioridad: int = 100,
    ayuda: str | None = None,
) -> SpecDef:
    """Ángulo del haz de luz. tipo=rango unidad=°.

    Aliases: unión de Iluminación (Illumination Angle extra) + Modificadores.
    en_filtros=True en ambas — hardcodeado.
    """
    return SpecDef(
        key="beam_angle", label="Ángulo del haz", tipo="rango", unidad="°",
        prioridad=prioridad, en_filtros=True,
        ayuda=ayuda,
        aliases=["Beam Angle", "Spread Angle", "Field Angle", "Beam Spread",
                 "Illumination Angle"],
    )
