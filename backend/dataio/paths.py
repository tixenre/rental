"""dataio/paths.py — Ubicaciones canónicas de los JSONs versionados."""

from pathlib import Path

# Raíz del repo: backend/dataio/paths.py → repo
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Directorio donde viven los JSONs del catálogo oficial. Versionado en git.
DATA_DIR = REPO_ROOT / "data" / "catalog"

# Catálogo (commiteable en git, sin datos personales). Es el "qué alquilás":
# marcas, categorías, equipos, specs. Lo importa el startup automáticamente.
CATALOG_ENTITIES: tuple[str, ...] = (
    "marcas",
    "categorias",
    "spec_definitions",
    "categoria_spec_templates",
    "equipos",
    "equipo_specs",
    "equipo_fichas",
)

# Operacional (NO commitear a git: tiene datos personales/comerciales).
# Es el "quién alquila qué": clientes y pedidos. Solo accesible vía
# export/import ad-hoc para backups o migración entre ambientes.
# Alquileres embebe sus items y pagos para que cada pedido sea autosuficiente.
OPERATIONAL_ENTITIES: tuple[str, ...] = (
    "clientes",
    "alquileres",
)

# Configuración / contenido del admin (sin datos personales): ajustes del
# sistema, plantillas de mail, descuentos y configuración del estudio.
# No se versiona en git como el catálogo, pero tampoco tiene PII — va junto
# al catálogo en el grupo "configuración" del backup.
# Nota: estudio va DESPUÉS de equipos en ENTITY_ORDER (FK equipo_id → equipos).
CONFIG_ENTITIES: tuple[str, ...] = (
    "app_settings",
    "email_templates",
    "descuentos_jornada",
    "estudio",
)

# ── Grupos de backup expuestos en la UI (/admin/dataio) ──────────────────────
# El dueño ve 3 botones: Configuración, Clientes, Pedidos.
CONFIGURACION_GROUP: tuple[str, ...] = CATALOG_ENTITIES + CONFIG_ENTITIES
CLIENTES_GROUP: tuple[str, ...] = ("clientes",)
PEDIDOS_GROUP: tuple[str, ...] = ("alquileres",)

BACKUP_GROUPS: dict[str, tuple[str, ...]] = {
    "configuracion": CONFIGURACION_GROUP,
    "clientes": CLIENTES_GROUP,
    "pedidos": PEDIDOS_GROUP,
}

# Orden canónico de TODAS las entidades, respetando FK dependencies.
# Catálogo primero (marcas → equipos), luego config (app_settings, mails,
# descuentos, estudio — este último depende de equipos vía equipo_id),
# después operacional (clientes → alquileres → items/pagos).
ENTITY_ORDER: tuple[str, ...] = CATALOG_ENTITIES + CONFIG_ENTITIES + OPERATIONAL_ENTITIES


def entity_path(entity: str, base: Path | None = None) -> Path:
    """Devuelve la ruta al JSON de una entidad. `base` default = DATA_DIR."""
    if entity not in ENTITY_ORDER:
        raise ValueError(f"Entidad desconocida: {entity!r}. Válidas: {ENTITY_ORDER}")
    return (base or DATA_DIR) / f"{entity}.json"
