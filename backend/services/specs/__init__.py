"""services/specs — barrel público del motor de specs.

Fase 1 del rediseño (ver docs/PLAN_SPECS_REDISENO.md e issue #1163): el
registry (modelo declarativo) y la persistencia (coerce/persist/seed) ya
viven acá, movidos verbatim de sus ubicaciones viejas. Los paths viejos
(`backend/specs/`, `backend/services/spec_coerce.py`, `spec_persist.py`,
`backend/seeds/registry_seeder.py`) quedan como shims ⏰ LEGACY que
re-exportan desde acá — se borran en la Fase 6.

Todavía no implementado: `commands/value_aliases.py` (CRUD ad-hoc de aliases
desde el admin) y `queries/aliases.py` (expansión de término — refinamiento,
`search_source.py` ya cubre lo básico).

Mismo patrón que `services/categorias/`: commands = única puerta de escritura,
queries nunca mutan, todo recibe `conn`, sin dependencia de FastAPI. `__all__`
es el contrato real — si algo no está ahí, es un detalle interno del paquete.
"""

from .registry import (
    REGISTRY,
    CategoriaRegistry,
    CompatMode,
    CompatRol,
    FORMATO_ENUM,
    LENS_MOUNT_ENUM,
    MONTURA_LUZ_ENUM,
    Registry,
    SpecDef,
    SpecTipo,
    all_categorias,
    get_categoria,
    get_spec,
)
from .queries.validation import ValidationError, validate_dataset, validate_or_raise
from .queries.propuestas import listar_propuestas_pendientes
from .queries.equipo_specs import get_equipo_specs_rows, specs_en_nombre_de_equipo
from .commands.coerce import coerce_and_serialize
from .commands.persist import persistir_specs
from .commands.propuestas import aplicar_propuesta, descartar_propuesta, encolar_propuesta
from .commands.seed import (
    purge_stale_specs,
    seed_all_categorias,
    seed_categoria_from_registry,
    serialize_spec_value,
)

__all__ = [
    # registry
    "REGISTRY", "CategoriaRegistry", "CompatMode", "CompatRol",
    "FORMATO_ENUM", "LENS_MOUNT_ENUM", "MONTURA_LUZ_ENUM",
    "Registry", "SpecDef", "SpecTipo",
    "all_categorias", "get_categoria", "get_spec",
    # queries
    "ValidationError", "validate_dataset", "validate_or_raise",
    "listar_propuestas_pendientes", "get_equipo_specs_rows",
    "specs_en_nombre_de_equipo",
    # commands
    "coerce_and_serialize", "persistir_specs",
    "purge_stale_specs", "seed_all_categorias",
    "seed_categoria_from_registry", "serialize_spec_value",
    "encolar_propuesta", "aplicar_propuesta", "descartar_propuesta",
]
