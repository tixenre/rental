#!/usr/bin/env python3
"""
tools/equipos_match_preview.py — Preview del merge dataset ↔ DB.

Para cada producto en docs/{categoria}.json, busca su match en `equipos`
tabla usando:
  1. Match EXACTO (marca, modelo) — caso ideal.
  2. Match FUZZY por nombre normalizado (lowercase + strip + colapsar
     espacios + sacar SKUs / unidades comunes) usando difflib.

Genera dos cosas:
  - Output stdout con la tabla resumen (qué va a pasar con cada producto).
  - `docs/equipos_match.json` con el mapeo {dataset_id → equipo_id real},
     editable manualmente para resolver ambigüedades.

Los seeds (lentes.py, camaras.py, etc.) pueden consumir ese mapeo para
hacer UPDATE in-place sobre equipo.id existente (preservando FKs de pedidos
históricos).

Uso:
    cd <ruta-al-repo>
    python -m tools.equipos_match_preview               # todas las categorías
    python -m tools.equipos_match_preview --solo lentes # una categoría
    python -m tools.equipos_match_preview --umbral 0.6  # fuzzy más laxo
"""

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
MATCH_FILE = ROOT / "docs" / "equipos_match.json"

# (raíz_de_categoría, ruta_del_dataset)
DATASETS = [
    ("Cámaras",     ROOT / "docs" / "camaras.json"),
    ("Lentes",      ROOT / "docs" / "lentes.json"),
    ("Adaptadores", ROOT / "docs" / "adaptadores.json"),
    ("Filtros",     ROOT / "docs" / "filtros.json"),
    ("Iluminación", ROOT / "docs" / "iluminacion.json"),
]


def normalizar(s: str) -> str:
    """Normaliza un string para fuzzy matching: lower, sin SKU al final,
    sin múltiples espacios."""
    if not s:
        return ""
    s = s.lower().strip()
    # Sacar SKUs alfanuméricos largos al final (SEL2470GM2, 311101, etc.)
    s = re.sub(r"\s+[a-z0-9-]{6,}\s*$", "", s)
    # Sacar paréntesis con metadata
    s = re.sub(r"\s*\([^)]*\)", "", s)
    # Colapsar espacios y signos
    s = re.sub(r"[/_\-\s]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def similarity(a: str, b: str) -> float:
    """Ratio difflib entre dos strings normalizados."""
    return difflib.SequenceMatcher(None, normalizar(a), normalizar(b)).ratio()


def fetch_equipos_db(conn) -> list[dict]:
    """Trae todos los equipos no-eliminados con marca/modelo/nombre."""
    rows = conn.execute(
        """
        SELECT e.id, e.marca, e.modelo, e.nombre,
               (SELECT array_agg(c.nombre)
                FROM equipo_categorias ec
                JOIN categorias c ON c.id = ec.categoria_id
                WHERE ec.equipo_id = e.id) AS categorias
        FROM equipos e
        WHERE e.eliminado_at IS NULL
        ORDER BY e.id
        """
    ).fetchall()
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "marca": r["marca"] or "",
            "modelo": r["modelo"] or "",
            "nombre": r["nombre"] or "",
            "categorias": r["categorias"] or [],
        })
    return out


def match_producto(prod_id: str, prod: dict, equipos_db: list[dict], umbral: float) -> dict:
    """Encuentra el mejor match en DB para un producto del dataset.

    Devuelve {action, equipo_id, confidence, db_marca, db_modelo, score}.
    """
    marca = prod.get("marca", "")
    modelo = prod.get("modelo", "")

    # 1. Match exacto
    for eq in equipos_db:
        if eq["marca"].strip().lower() == marca.strip().lower() and \
           eq["modelo"].strip().lower() == modelo.strip().lower():
            return {
                "action": "update",
                "equipo_id": eq["id"],
                "confidence": "exact",
                "db_marca": eq["marca"],
                "db_modelo": eq["modelo"],
                "score": 1.0,
            }

    # 2. Fuzzy: comparar marca+modelo del dataset contra (marca+modelo) o nombre del DB
    target = f"{marca} {modelo}"
    best = None
    best_score = 0.0
    for eq in equipos_db:
        candidates = [f"{eq['marca']} {eq['modelo']}", eq["nombre"]]
        score = max(similarity(target, c) for c in candidates if c)
        if score > best_score:
            best_score = score
            best = eq

    if best and best_score >= umbral:
        return {
            "action": "review",  # requiere revisión manual
            "equipo_id": best["id"],
            "confidence": "fuzzy",
            "db_marca": best["marca"],
            "db_modelo": best["modelo"],
            "score": round(best_score, 3),
        }

    # 3. Sin match
    return {
        "action": "create",
        "equipo_id": None,
        "confidence": "none",
        "db_marca": None,
        "db_modelo": None,
        "score": round(best_score, 3) if best else 0.0,
    }


def preview_categoria(conn, categoria_raiz: str, dataset_path: Path, umbral: float) -> dict:
    """Procesa una categoría: lee dataset, matchea contra DB, devuelve dict."""
    if not dataset_path.exists():
        return {"error": f"No existe {dataset_path.name}"}

    with open(dataset_path) as f:
        data = json.load(f)
    products = data.get("products", {})
    equipos_db = fetch_equipos_db(conn)

    matches: dict[str, dict] = {}
    for prod_id, prod in products.items():
        matches[prod_id] = match_producto(prod_id, prod, equipos_db, umbral)
        matches[prod_id]["dataset_marca"] = prod.get("marca", "")
        matches[prod_id]["dataset_modelo"] = prod.get("modelo", "")

    # Detectar huérfanos en DB (con esta categoría raíz, pero sin match en dataset)
    matched_eq_ids = {m["equipo_id"] for m in matches.values() if m["equipo_id"]}
    huerfanos = [
        eq for eq in equipos_db
        if categoria_raiz in (eq.get("categorias") or [])
        and eq["id"] not in matched_eq_ids
    ]

    return {"matches": matches, "huerfanos": huerfanos}


def imprimir_tabla(categoria: str, result: dict) -> None:
    matches = result.get("matches", {})
    huerfanos = result.get("huerfanos", [])
    if "error" in result:
        print(f"\n{categoria}: {result['error']}")
        return

    counts = {"update": 0, "review": 0, "create": 0}
    for m in matches.values():
        counts[m["action"]] += 1

    print(f"\n═══ {categoria} ═══")
    print(f"  ✓ {counts['update']} UPDATE (match exacto)")
    print(f"  ⚠ {counts['review']} REVIEW (match fuzzy — confirmá manualmente)")
    print(f"  + {counts['create']} CREATE (no existe en DB)")
    if huerfanos:
        print(f"  ? {len(huerfanos)} HUÉRFANOS en DB (no tocados):")
        for h in huerfanos[:10]:
            print(f"      [{h['id']}] {h['marca']} {h['modelo']}")
        if len(huerfanos) > 10:
            print(f"      ... y {len(huerfanos) - 10} más")

    for prod_id, m in matches.items():
        action = m["action"]
        if action == "update":
            mark = "✓"
        elif action == "review":
            mark = "⚠"
        else:
            mark = "+"
        line = f"  {mark} [{prod_id}] {m['dataset_marca']} {m['dataset_modelo']}"
        if m["equipo_id"]:
            line += f"  →  [{m['equipo_id']}] {m['db_marca']} {m['db_modelo']}"
            if action == "review":
                line += f"  (score={m['score']})"
        print(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", help="Procesa solo una categoría (ej. 'lentes')", default=None)
    ap.add_argument("--umbral", type=float, default=0.65,
                    help="Score mínimo para considerar fuzzy match (default 0.65)")
    args = ap.parse_args()

    sys.path.insert(0, str(ROOT / "backend"))
    try:
        from database import get_db  # type: ignore
    except ImportError as e:
        print(f"No pude importar backend.database: {e}")
        sys.exit(1)

    conn = get_db()
    try:
        all_results: dict[str, dict] = {}
        for cat, path in DATASETS:
            if args.solo and args.solo.lower() not in cat.lower():
                continue
            result = preview_categoria(conn, cat, path, args.umbral)
            all_results[cat] = result
            imprimir_tabla(cat, result)

        # Persistir mapeo para que los seeds lo consuman
        out = {}
        for cat, res in all_results.items():
            if "matches" not in res:
                continue
            out[cat] = {
                pid: {
                    "action": m["action"],
                    "equipo_id": m["equipo_id"],
                    "confidence": m["confidence"],
                    "score": m["score"],
                    "dataset_marca": m["dataset_marca"],
                    "dataset_modelo": m["dataset_modelo"],
                    "db_marca": m["db_marca"],
                    "db_modelo": m["db_modelo"],
                }
                for pid, m in res["matches"].items()
            }
        MATCH_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        print(f"\n→ Mapeo escrito en {MATCH_FILE.relative_to(ROOT)}")
        print("   Editá los `action`/`equipo_id` para casos REVIEW antes de correr el seed.")
        print("   Después: bash tools/seeds_run.sh  (o python -m backend.seeds.X)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
