"""⏰ LEGACY — shim. El registry real vive en `services.specs` desde la Fase 1
del rediseño (docs/PLAN_SPECS_REDISENO.md, issue #1163). Este path se borra en
la Fase 6; no agregar código nuevo acá, importar de `services.specs`."""

from services.specs import (
    CategoriaRegistry,
    CompatMode,
    CompatRol,
    FORMATO_ENUM,
    LENS_MOUNT_ENUM,
    MONTURA_LUZ_ENUM,
    REGISTRY,
    Registry,
    SpecDef,
    SpecTipo,
    SubCategoria,
    ValidationError,
    all_categorias,
    get_categoria,
    get_spec,
    validate_dataset,
    validate_or_raise,
)

__all__ = [
    "CategoriaRegistry", "CompatMode", "CompatRol", "Registry",
    "SpecDef", "SpecTipo", "SubCategoria",
    "REGISTRY", "FORMATO_ENUM", "LENS_MOUNT_ENUM", "MONTURA_LUZ_ENUM",
    "all_categorias", "get_categoria", "get_spec",
    "ValidationError", "validate_dataset", "validate_or_raise",
]
