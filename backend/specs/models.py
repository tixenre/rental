"""⏰ LEGACY — shim. Ver services/specs/registry/models.py (Fase 1, #1163)."""

from services.specs.registry.models import (
    CategoriaRegistry,
    CompatMode,
    CompatRol,
    Registry,
    SpecDef,
    SpecTipo,
    SubCategoria,
)

__all__ = [
    "SpecTipo", "CompatMode", "CompatRol",
    "SpecDef", "SubCategoria", "CategoriaRegistry", "Registry",
]
