"""seeds/compat_config.py — Helpers de matcheo de equipos para seeds.

NOTA: con el registry Pydantic (backend/specs/registry.py) como single
source of truth, los flags es_compatibilidad / compatibilidad_modo /
rol_compatibilidad / enum_options se escriben directo desde el registry
seeder. Este archivo conserva solo las utilidades de matching de equipos
del dataset → DB (preservar equipo.id para FKs de pedidos históricos).

Para cambios de specs/cats: editar `backend/specs/registry.py`.
"""

import json
from pathlib import Path

# FORMATO_ENUM expuesto acá para retrocompat — el canónico vive en specs.registry.
try:
    from specs.registry import FORMATO_ENUM
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from specs.registry import FORMATO_ENUM  # type: ignore

__all__ = [
    "FORMATO_ENUM",
    "load_match_file",
    "resolve_equipo_id",
    "apply_overrides",
    "write_keywords",
]


def load_match_file(categoria_raiz: str) -> dict:
    """Carga `docs/equipos_match.json` y devuelve el sub-dict de esta cat.

    Estructura: { prod_id_dataset: {action, equipo_id, ...} }.
    Vacío si el archivo no existe.
    """
    p = Path(__file__).parent.parent.parent / "docs" / "equipos_match.json"
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data.get(categoria_raiz, {})


def resolve_equipo_id(
    conn, prod_id: str, marca: str, modelo: str, match_map: dict,
) -> tuple[int | None, str]:
    """Resuelve a qué equipo.id corresponde un producto del dataset.

    Prioridad:
      1. match_map[prod_id].action == "skip" → (None, "skip")
      2. match_map[prod_id] con equipo_id explícito → preserva ese id (FK safe)
      3. Match exacto por (marca, modelo)
      4. None — el seed crea equipo nuevo
    """
    m = match_map.get(prod_id)
    if m:
        action = m.get("action")
        if action == "skip":
            return None, "skip"
        if action in ("update", "review") and m.get("equipo_id"):
            return int(m["equipo_id"]), "match_file"

    existing = conn.execute(
        "SELECT id FROM equipos WHERE marca = %s AND modelo = %s LIMIT 1",
        (marca, modelo),
    ).fetchone()
    if existing:
        return existing["id"], "marca_modelo"
    return None, "none"


def apply_overrides(
    conn, prod_id: str, equipo_id: int, match_map: dict, dry_run: bool = False,
) -> dict[str, str]:
    """Aplica override_marca / override_modelo del match_file (corrige equipos
    mal-etiquetados sin perder FKs)."""
    m = match_map.get(prod_id)
    if not m:
        return {}
    overrides: dict[str, str] = {}
    if m.get("override_marca"):
        overrides["marca"] = m["override_marca"]
    if m.get("override_modelo"):
        overrides["modelo"] = m["override_modelo"]
    if not overrides or dry_run:
        return overrides
    sets = ", ".join(f"{k} = %s" for k in overrides)
    params = list(overrides.values()) + [equipo_id]
    conn.execute(f"UPDATE equipos SET {sets} WHERE id = %s", params)
    return overrides


def write_keywords(conn, equipo_id: int, specs: dict, dry_run: bool = False) -> int:
    """Genera keywords derivadas de specs y las escribe a equipo_fichas."""
    import sys
    backend_path = Path(__file__).parent.parent
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    from services.nombre_builder import compute_keywords  # type: ignore

    keywords = compute_keywords(specs)
    if not keywords:
        return 0
    if dry_run:
        return len(keywords)
    kw_json = json.dumps(keywords, ensure_ascii=False)
    conn.execute(
        """
        INSERT INTO equipo_fichas (equipo_id, keywords_json)
        VALUES (%s, %s)
        ON CONFLICT (equipo_id) DO UPDATE SET keywords_json = EXCLUDED.keywords_json
        """,
        (equipo_id, kw_json),
    )
    return len(keywords)
