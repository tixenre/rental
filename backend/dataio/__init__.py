"""dataio — Sistema de export/import del catálogo basado en JSONs versionados.

Reemplaza el sistema viejo de seeds (`backend/seeds/*.py` + `docs/*.json`)
por un módulo bidireccional con claves naturales en lugar de IDs SERIAL.

La fuente de verdad de "lo oficial" son los JSONs commiteados en
`/data/catalog/`. Lo que está en la DB pero no en esos JSONs es custom
(creado/editado a mano desde la UI).

Entrypoints públicos:
    from backend.dataio import orchestrator
    orchestrator.export_all(conn, out_dir)
    orchestrator.import_all(conn, in_dir, dry_run=False, prune=False)
"""

from . import exporters, importers, natural_keys, orchestrator, paths, schema, slug

__all__ = [
    "exporters",
    "importers",
    "natural_keys",
    "orchestrator",
    "paths",
    "schema",
    "slug",
]
