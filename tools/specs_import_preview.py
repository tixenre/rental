#!/usr/bin/env python3
"""tools/specs_import_preview.py — Puente dataset B&H → archivo de import.

Lee los datasets curados (docs/{categoria}.json) + el mapping
(docs/equipos_match.json) y produce TRES outputs en /tmp/import_preview/:

  1. equipos_specs_preview.json — agrupado por equipo, legible humano.
     Para cada equipo: action resuelta, slug propuesto, equipo_id DB
     (si match), marca/modelo, lista de specs con valor raw + serializado
     + label, y specs canónicas FALTANTES en el dataset.

  2. equipos.json — formato dataio: lista de Equipo con marca/modelo
     (aplicando overrides del match), nombre, slug, foto_url, bh_url.
     Pegable a `data/catalog/equipos.json` para corregir marca/modelo
     mal etiquetados (Arri 650 Plus, Mole 2000W, Godox TL60, etc).

  3. equipo_specs.json — formato dataio: lista plana de
     {equipo_slug, spec_ref:{categoria_raiz_nombre, spec_key}, value}.
     Pegable a `data/catalog/equipo_specs.json` para correr
     `python -m backend.dataio.cli import [--dry-run]`.

Reglas:
  - action="skip" del match file → producto excluido (no aparece en outputs).
  - action="update"|"review"|"create" → incluido.
  - producto sin entrada en match file → incluido como "create_implicit".
  - override_marca/override_modelo del match se respetan en el preview.
  - serialize_spec_value() del seed se reusa tal cual (misma serialización
    que cuando un seed escribe a DB).

NO toca DB. NO requiere conexión.

Uso:
  cd /Users/tincho/rental
  python -m tools.specs_import_preview
  python -m tools.specs_import_preview --solo iluminacion
  python -m tools.specs_import_preview --out /tmp/otro_dir
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEFAULT_OUT = Path("/tmp/import_preview")
MATCH_FILE = ROOT / "docs" / "equipos_match.json"

DATASETS = [
    ("Cámaras",       ROOT / "docs" / "camaras.json"),
    ("Lentes",        ROOT / "docs" / "lentes.json"),
    ("Adaptadores",   ROOT / "docs" / "adaptadores.json"),
    ("Filtros",       ROOT / "docs" / "filtros.json"),
    ("Iluminación",   ROOT / "docs" / "iluminacion.json"),
    ("Modificadores", ROOT / "docs" / "modificadores.json"),
]

# Importar helpers existentes del backend
sys.path.insert(0, str(ROOT / "backend"))
from seeds.registry_seeder import serialize_spec_value  # noqa: E402
from specs import get_categoria  # noqa: E402


def load_match() -> dict:
    if not MATCH_FILE.exists():
        return {}
    return json.loads(MATCH_FILE.read_text(encoding="utf-8"))


def load_db_slugs_by_id() -> dict[int, str]:
    """Consulta la DB y devuelve {equipo_id: slug_real}.

    El slug en DB es kebab-case (red-komodo-x) y el prod_id del dataset es
    snake_case (red_komodo_x), entonces no coinciden literalmente. Esta función
    permite resolver el slug correcto para los productos matcheados con
    equipo_id, antes de generar el equipo_specs.json importable.

    Si la DB no está disponible (sin postgres, sin credenciales, etc.),
    devuelve {} y el caller cae al fallback de usar prod_id.
    """
    try:
        sys.path.insert(0, str(ROOT / "backend"))
        from database import get_db  # type: ignore
    except Exception as e:
        print(f"⚠ No pude importar backend.database (sin DB?): {e}")
        return {}
    try:
        conn = get_db()
    except Exception as e:
        print(f"⚠ No pude conectar a la DB: {e}")
        return {}
    try:
        rows = conn.execute(
            "SELECT id, slug FROM equipos WHERE eliminado_at IS NULL AND slug IS NOT NULL"
        ).fetchall()
        return {r["id"]: r["slug"] for r in rows}
    finally:
        conn.close()


def process_categoria(
    categoria_raiz: str,
    dataset_path: Path,
    match_map: dict,
    db_slugs_by_id: dict[int, str] | None = None,
) -> dict:
    if not dataset_path.exists():
        return {"error": f"No existe {dataset_path.name}"}

    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    products = data.get("products", {})

    cat_reg = get_categoria(categoria_raiz)
    if not cat_reg:
        return {"error": f"Categoría '{categoria_raiz}' no está en el registry"}
    specs_by_key = {s.key: s for s in cat_reg.specs}
    all_spec_keys = set(specs_by_key.keys())

    cat_match = match_map.get(categoria_raiz, {})
    db_slugs_by_id = db_slugs_by_id or {}

    preview = []
    dataio_equipos = []
    dataio_specs = []
    stats = {
        "productos_dataset": len(products),
        "incluidos": 0,
        "skipped": 0,
        "action_update": 0,
        "action_create": 0,
        "action_review": 0,
        "action_implicit_create": 0,
        "specs_emitidas": 0,
        "specs_sin_definicion": 0,
        "slug_resuelto_desde_db": 0,
        "slug_fallback_prod_id": 0,
    }

    for prod_id, prod in products.items():
        m = cat_match.get(prod_id) or {}
        action = m.get("action")
        equipo_id_db = m.get("equipo_id")
        override_marca = m.get("override_marca")
        override_modelo = m.get("override_modelo")
        note = m.get("_note")

        if action == "skip":
            stats["skipped"] += 1
            continue

        if not action:
            action_resolved = "create_implicit"
            stats["action_implicit_create"] += 1
        elif action == "update":
            action_resolved = "update"
            stats["action_update"] += 1
        elif action == "create":
            action_resolved = "create"
            stats["action_create"] += 1
        elif action == "review":
            action_resolved = "review"
            stats["action_review"] += 1
        else:
            action_resolved = action

        stats["incluidos"] += 1
        marca = override_marca or prod.get("marca", "")
        modelo = override_modelo or prod.get("modelo", "")
        nombre = f"{marca} {modelo}".strip()
        foto_url = prod.get("image_url") or None
        bh_url = prod.get("url_source") or None

        # Resolver slug REAL: si el match tiene equipo_id y la DB tiene slug
        # para ese id, usarlo. Sino fallback al prod_id del dataset.
        db_slug = None
        if equipo_id_db is not None:
            db_slug = db_slugs_by_id.get(int(equipo_id_db))
        if db_slug:
            slug_to_use = db_slug
            stats["slug_resuelto_desde_db"] += 1
        else:
            slug_to_use = prod_id
            stats["slug_fallback_prod_id"] += 1

        dataio_equipos.append({
            "slug": slug_to_use,
            "nombre": nombre,
            "marca": marca or None,
            "modelo": modelo or None,
            "marca_nombre": marca or None,
            "foto_url": foto_url,
            "bh_url": bh_url,
        })

        specs_in = prod.get("specs", {}) or {}
        specs_preview = []
        present_keys = set()

        for spec_key, value in specs_in.items():
            spec_def = specs_by_key.get(spec_key)
            if not spec_def:
                stats["specs_sin_definicion"] += 1
                specs_preview.append({
                    "spec_key": spec_key,
                    "raw": value,
                    "WARN": "key no existe en registry para esta categoría — se descarta",
                })
                continue
            value_str = serialize_spec_value(spec_def, value)
            if value_str is None:
                specs_preview.append({
                    "spec_key": spec_key,
                    "label": spec_def.label,
                    "raw": value,
                    "WARN": "serializa a None (valor no aplicable) — se descarta",
                })
                continue

            present_keys.add(spec_key)
            stats["specs_emitidas"] += 1

            specs_preview.append({
                "spec_key": spec_key,
                "label": spec_def.label,
                "tipo": spec_def.tipo,
                "unidad": spec_def.unidad,
                "raw": value,
                "serialized": value_str,
            })

            dataio_specs.append({
                "equipo_slug": slug_to_use,
                "spec_ref": {
                    "categoria_raiz_nombre": categoria_raiz,
                    "spec_key": spec_key,
                },
                "value": value_str,
            })

        faltantes = sorted(all_spec_keys - present_keys)
        faltantes_obligatorias = [
            k for k in faltantes if specs_by_key[k].obligatorio
        ]

        preview.append({
            "equipo_slug_propuesto": slug_to_use,
            "prod_id_dataset": prod_id,
            "slug_origen": "db" if db_slug else "prod_id (fallback)",
            "action": action_resolved,
            "equipo_id_db": equipo_id_db,
            "marca": marca,
            "modelo": modelo,
            "_note": note,
            "url_bh": prod.get("url_source"),
            "image_url": prod.get("image_url"),
            "specs_emitidas_count": len([s for s in specs_preview if "WARN" not in s]),
            "specs_descartadas_count": len([s for s in specs_preview if "WARN" in s]),
            "specs_faltantes_count": len(faltantes),
            "specs_faltantes_obligatorias": faltantes_obligatorias,
            "specs": specs_preview,
            "specs_faltantes_keys": faltantes,
        })

    return {
        "preview": preview,
        "dataio_equipos": dataio_equipos,
        "dataio_specs": dataio_specs,
        "stats": stats,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", help="Filtra una categoría (ej. iluminacion)", default=None)
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="Carpeta de output")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    match_map = load_match()
    db_slugs_by_id = load_db_slugs_by_id()
    if db_slugs_by_id:
        print(f"✓ Conectado a DB: {len(db_slugs_by_id)} slugs cargados para resolver matches.")
    else:
        print("⚠ Sin DB: voy a usar prod_id del dataset como slug (puede no coincidir con DB).")

    all_preview: dict = {}
    all_dataio_equipos: list = []
    all_dataio_specs: list = []
    all_stats: dict = {}

    for cat_raiz, path in DATASETS:
        if args.solo and args.solo.lower() not in cat_raiz.lower():
            continue
        result = process_categoria(cat_raiz, path, match_map, db_slugs_by_id)
        if "error" in result:
            print(f"⚠ {cat_raiz}: {result['error']}")
            continue
        all_preview[cat_raiz] = result["preview"]
        all_dataio_equipos.extend(result["dataio_equipos"])
        all_dataio_specs.extend(result["dataio_specs"])
        all_stats[cat_raiz] = result["stats"]

    preview_file = out_dir / "equipos_specs_preview.json"
    preview_payload = {
        "_meta": {
            "generado_por": "tools/specs_import_preview.py",
            "fuente_datasets": "docs/{categoria}.json (parseados desde HTMLs de ~/Desktop/Paginas/)",
            "fuente_match": "docs/equipos_match.json",
            "stats_por_categoria": all_stats,
            "nota_slug": (
                "equipo_slug_propuesto = prod_id del dataset. Coincide con la convención "
                "{marca_snake}_{modelo_snake} usada por los seeds. Si los equipos en DB ya "
                "tienen otro slug, hay que reconciliar antes de importar via dataio."
            ),
        },
        "equipos_por_categoria": all_preview,
    }
    preview_file.write_text(
        json.dumps(preview_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    equipos_file = out_dir / "equipos.json"
    equipos_file.write_text(
        json.dumps(all_dataio_equipos, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    dataio_file = out_dir / "equipo_specs.json"
    dataio_file.write_text(
        json.dumps(all_dataio_specs, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"\n{'═' * 60}")
    print("  Specs import preview")
    print('═' * 60)
    total_incluidos = 0
    total_specs = 0
    for cat, st in all_stats.items():
        print(f"\n▸ {cat}")
        for k, v in st.items():
            print(f"    {k:<28} {v}")
        total_incluidos += st["incluidos"]
        total_specs += st["specs_emitidas"]
    print(f"\n  TOTAL equipos incluidos: {total_incluidos}")
    print(f"  TOTAL spec entries:      {total_specs}")

    print(f"\n→ Preview legible:   {preview_file}")
    print(f"→ Dataio equipos:    {equipos_file}   ({len(all_dataio_equipos)} equipos)")
    print(f"→ Dataio specs:      {dataio_file}   ({len(all_dataio_specs)} spec entries)")

    print(f"\nPróximos pasos sugeridos:")
    print(f"  • Ver un equipo:  jq '.equipos_por_categoria.\"Iluminación\"[0]' {preview_file}")
    print(f"  • Listar slugs:   jq '[.[].slug] | sort' {equipos_file}")
    print(f"  • Ver overrides:  jq '.[] | select(.marca | test(\"ARRI|Mole\"))' {equipos_file}")
    print(f"  • Importar via dataio (cuando estés listo):")
    print(f"      mkdir -p data/catalog")
    print(f"      cp {equipos_file} {dataio_file} data/catalog/")
    print(f"      python -m backend.dataio.cli import --dry-run --scope catalog")


if __name__ == "__main__":
    main()
