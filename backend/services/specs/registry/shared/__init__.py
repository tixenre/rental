"""Specs compartidas entre categorías.

`enums.py` define los enum options reusables (formato, lens_mount, montura_luz).
`physical.py` define factory functions para specs físicas (peso_g,
dimensions_mm, materials) que aparecen en múltiples categorías.

El patrón factory permite override de `prioridad` y otros flags por categoría
sin duplicar la definición canónica del spec (label/tipo/unidad/ayuda).
"""

from .enums import FORMATO_ENUM, LENS_MOUNT_ENUM, MONTURA_LUZ_ENUM
from .lighting import beam_angle, montura_luz
from .optica import autofocus, coating, diametro_filtro, estabilizacion
from .physical import dimensions_mm, materials, peso_g

__all__ = [
    "FORMATO_ENUM", "LENS_MOUNT_ENUM", "MONTURA_LUZ_ENUM",
    "beam_angle", "montura_luz",
    "autofocus", "coating", "diametro_filtro", "estabilizacion",
    "dimensions_mm", "materials", "peso_g",
]
