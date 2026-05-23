"""dataio/paths.py — Ubicaciones canónicas de los JSONs versionados."""

from pathlib import Path

# Raíz del repo: backend/dataio/paths.py → repo
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Directorio donde viven los JSONs del catálogo oficial. Versionado en git.
DATA_DIR = REPO_ROOT / "data" / "catalog"

# Orden canónico de las entidades, respetando dependencias de FK.
# El importer las procesa en este orden; el exporter las escribe igual.
ENTITY_ORDER: tuple[str, ...] = (
    "marcas",
    "categorias",
    "etiquetas",
    "spec_definitions",
    "categoria_spec_templates",
    "equipos",
    "equipo_specs",
    "equipo_fichas",
)


def entity_path(entity: str, base: Path | None = None) -> Path:
    """Devuelve la ruta al JSON de una entidad. `base` default = DATA_DIR."""
    if entity not in ENTITY_ORDER:
        raise ValueError(f"Entidad desconocida: {entity!r}. Válidas: {ENTITY_ORDER}")
    return (base or DATA_DIR) / f"{entity}.json"
