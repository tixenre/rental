"""Single source of truth para definición de specs por categoría.

Uso típico:
    from specs import REGISTRY, get_categoria, get_spec
    cat = REGISTRY.get("Cámaras")
    for spec in cat.specs:
        ...
"""

from .models import (
    CategoriaRegistry,
    CompatMode,
    CompatRol,
    Registry,
    SpecDef,
    SpecTipo,
    SubCategoria,
)
from .registry import (
    FORMATO_ENUM,
    LENS_MOUNT_ENUM,
    REGISTRY,
    all_categorias,
    get_categoria,
    get_spec,
)

__all__ = [
    "CategoriaRegistry", "CompatMode", "CompatRol", "Registry",
    "SpecDef", "SpecTipo", "SubCategoria",
    "REGISTRY", "FORMATO_ENUM", "LENS_MOUNT_ENUM",
    "all_categorias", "get_categoria", "get_spec",
]
