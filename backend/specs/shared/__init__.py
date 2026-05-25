"""Specs compartidas entre categorías.

`enums.py` define los enum options reusables (formato, lens_mount, montura_luz).
`physical.py` define factory functions para specs físicas (peso_g,
dimensions_mm, materials) que aparecen en múltiples categorías.

El patrón factory permite override de `prioridad` y otros flags por categoría
sin duplicar la definición canónica del spec (label/tipo/unidad/ayuda).
"""

from .enums import FORMATO_ENUM, LENS_MOUNT_ENUM, MONTURA_LUZ_ENUM
from .physical import dimensions_mm, materials, peso_g

__all__ = [
    "FORMATO_ENUM", "LENS_MOUNT_ENUM", "MONTURA_LUZ_ENUM",
    "dimensions_mm", "materials", "peso_g",
]
