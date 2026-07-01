"""⏰ LEGACY — shim. Ver services/specs/commands/seed.py (Fase 1, #1163).

Re-exporta también REGISTRY/CategoriaRegistry/SpecDef porque
tests/test_seeder_resiliente.py hace `from seeds.registry_seeder import
seed_all_categorias, REGISTRY` — no tocar sin actualizar ese test también."""

from services.specs import REGISTRY, CategoriaRegistry, SpecDef
from services.specs.commands.seed import (
    purge_stale_specs,
    seed_all_categorias,
    seed_categoria_from_registry,
    serialize_spec_value,
)

__all__ = [
    "seed_all_categorias", "purge_stale_specs",
    "seed_categoria_from_registry", "serialize_spec_value",
    "REGISTRY", "CategoriaRegistry", "SpecDef",
]
