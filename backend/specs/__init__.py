"""Single source of truth para definición de specs por categoría.

Arquitectura modular (PR fase Z1):
    backend/specs/
    ├── models.py              SpecDef, CategoriaRegistry, Registry, ...
    ├── validation.py          validate_dataset
    ├── shared/                Specs/enums reusables entre cats
    │   ├── enums.py           FORMATO_ENUM, LENS_MOUNT_ENUM, MONTURA_LUZ_ENUM
    │   └── physical.py        factory: peso_g(), dimensions_mm(), materials()
    └── categorias/
        ├── camaras.py         CAT (CategoriaRegistry)
        ├── lentes.py          CAT
        ├── iluminacion.py     CAT
        ├── modificadores.py   CAT
        ├── adaptadores.py     CAT
        └── filtros.py         CAT

Uso típico:
    from specs import REGISTRY, get_categoria, get_spec
    cat = REGISTRY.get("Cámaras")
    for spec in cat.specs:
        ...
"""

from .categorias import (
    ADAPTADORES,
    CAMARAS,
    FILTROS,
    ILUMINACION,
    LENTES,
    MODIFICADORES,
)
from .models import (
    CategoriaRegistry,
    CompatMode,
    CompatRol,
    Registry,
    SpecDef,
    SpecTipo,
    SubCategoria,
)
from .shared import FORMATO_ENUM, LENS_MOUNT_ENUM, MONTURA_LUZ_ENUM
from .validation import (
    ValidationError,
    validate_dataset,
    validate_or_raise,
)


REGISTRY: Registry = Registry(categorias={
    "Cámaras":       CAMARAS,
    "Lentes":        LENTES,
    "Iluminación":   ILUMINACION,
    "Modificadores": MODIFICADORES,
    "Adaptadores":   ADAPTADORES,
    "Filtros":       FILTROS,
})


def all_categorias() -> list[CategoriaRegistry]:
    return list(REGISTRY.categorias.values())


def get_categoria(nombre: str) -> CategoriaRegistry | None:
    return REGISTRY.get(nombre)


def get_spec(categoria_raiz: str, spec_key: str) -> SpecDef | None:
    cat = REGISTRY.get(categoria_raiz)
    return cat.get_spec(spec_key) if cat else None


__all__ = [
    "CategoriaRegistry", "CompatMode", "CompatRol", "Registry",
    "SpecDef", "SpecTipo", "SubCategoria",
    "REGISTRY", "FORMATO_ENUM", "LENS_MOUNT_ENUM", "MONTURA_LUZ_ENUM",
    "all_categorias", "get_categoria", "get_spec",
    "ValidationError", "validate_dataset", "validate_or_raise",
]
