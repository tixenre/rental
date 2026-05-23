#!/usr/bin/env python3
"""
Matchea productos exportados de Booqable contra el catalogo local de equipos.

Estrategia (por orden de prioridad):
  1. EXACT_SLUG     — slug Booqable == slug local
  2. EXACT_MM       — (marca, modelo) Booqable inferida == local
  3. FUZZY_NAME     — difflib ratio entre nombres normalizados >= umbral
  4. NO_MATCH       — sin candidato suficiente

Uso:
    python3 tools/booqable_match_equipos.py \\
        --products  /path/to/products.csv \\
        --equipos   /path/to/equipos.json \\
        --outdir    /path/to/out \\
        [--umbral 0.75]

Produce:
    equipos_match.csv    — CSV editable a mano con todos los matches.
    equipos_no_match.csv — Productos Booqable sin candidato local.

El CSV de match tiene una columna `local_slug` editable. Si la dejas vacia
o ponemos un slug invalido, el converter de alquileres lo va a tratar como
no-match y va a generar un placeholder.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


def normalize(text: str) -> str:
    """Lowercase + sin acentos + colapsar espacios + sacar tokens ruidosos."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    t = t.lower()
    # Sacar parentesis y su contenido (a menudo "(1 x 1.85 mts)" etc.)
    t = re.sub(r"\([^)]*\)", " ", t)
    # Sacar unidades comunes y tokens irrelevantes
    t = re.sub(r"\b(mm|cm|mts?|kg|gr|und|unidad|unidades|kit|pack)\b", " ", t)
    # Sacar SKUs estilo MAYUSCULAS_CON_GUIONES (ya lowered, asi que esto no aplica
    # pero limpiamos cualquier secuencia rara)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def infer_marca_modelo(name: str) -> tuple[str, str]:
    """Heuristica simple: primera palabra = marca, resto = modelo.

    Booqable no separa marca/modelo, asi que esto es best-effort para el
    match EXACT_MM. Si tu catalogo local guarda marca y modelo separados,
    esto a veces va a coincidir.
    """
    parts = (name or "").strip().split()
    if not parts:
        return ("", "")
    if len(parts) == 1:
        return (parts[0], "")
    return (parts[0], " ".join(parts[1:]))


def load_equipos(path: Path) -> list[dict[str, Any]]:
    """Acepta tanto un array como un dict con 'equipos' o 'products'."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("equipos", "products", "data"):
            if key in raw and isinstance(raw[key], list):
                return raw[key]
    raise ValueError(f"No pude detectar la lista de equipos en {path}")


def index_equipos(equipos: list[dict[str, Any]]) -> tuple[dict, dict, dict]:
    """Construye los 3 indices que usa el matcher."""
    by_slug: dict[str, dict] = {}
    by_mm: dict[tuple[str, str], dict] = {}
    by_norm_name: dict[str, dict] = {}
    for e in equipos:
        slug = (e.get("slug") or "").strip().lower()
        if slug:
            by_slug[slug] = e
        marca = normalize(e.get("marca") or "")
        modelo = normalize(e.get("modelo") or "")
        if marca and modelo:
            by_mm[(marca, modelo)] = e
        nombre = e.get("nombre") or ""
        n = normalize(nombre)
        if n:
            by_norm_name[n] = e
    return by_slug, by_mm, by_norm_name


def match_product(
    prod: dict[str, str],
    by_slug: dict,
    by_mm: dict,
    by_norm_name: dict,
    name_keys: list[str],
    umbral: float,
) -> tuple[str, dict | None, float]:
    """Devuelve (tipo_match, equipo_local|None, confianza)."""
    # 1. EXACT_SLUG
    bslug = (prod.get("slug") or "").strip().lower()
    if bslug and bslug in by_slug:
        return ("EXACT_SLUG", by_slug[bslug], 1.0)

    # 2. EXACT_MM (marca, modelo inferidos)
    name = prod.get("name") or ""
    bmarca_raw, bmodelo_raw = infer_marca_modelo(name)
    bmarca = normalize(bmarca_raw)
    bmodelo = normalize(bmodelo_raw)
    if bmarca and bmodelo and (bmarca, bmodelo) in by_mm:
        return ("EXACT_MM", by_mm[(bmarca, bmodelo)], 0.95)

    # 3. FUZZY_NAME
    bname_norm = normalize(name)
    if bname_norm and name_keys:
        best = difflib.get_close_matches(bname_norm, name_keys, n=1, cutoff=umbral)
        if best:
            ratio = difflib.SequenceMatcher(None, bname_norm, best[0]).ratio()
            return ("FUZZY_NAME", by_norm_name[best[0]], ratio)

    return ("NO_MATCH", None, 0.0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--products", required=True, help="products.csv de Booqable")
    ap.add_argument("--equipos", required=True, help="equipos.json del export local")
    ap.add_argument("--outdir", required=True, help="Directorio de salida")
    ap.add_argument(
        "--umbral", type=float, default=0.75,
        help="Umbral fuzzy (0.0-1.0). Default 0.75. Bajar para mas matches laxos.",
    )
    args = ap.parse_args()

    products_path = Path(args.products)
    equipos_path = Path(args.equipos)
    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    equipos = load_equipos(equipos_path)
    print(f"Equipos locales: {len(equipos)}", file=sys.stderr)

    by_slug, by_mm, by_norm_name = index_equipos(equipos)
    name_keys = list(by_norm_name.keys())

    with products_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        products = list(reader)
    print(f"Productos Booqable: {len(products)}", file=sys.stderr)

    matches: list[dict[str, Any]] = []
    no_match: list[dict[str, Any]] = []
    stats = {"EXACT_SLUG": 0, "EXACT_MM": 0, "FUZZY_NAME": 0, "NO_MATCH": 0}

    for p in products:
        # Saltar archivados (Booqable los marca con archived=True)
        if (p.get("archived") or "").lower() == "true":
            continue

        tipo, local, conf = match_product(p, by_slug, by_mm, by_norm_name, name_keys, args.umbral)
        stats[tipo] += 1

        if local is None:
            no_match.append({
                "booqable_id": p.get("id", ""),
                "booqable_name": p.get("name", ""),
                "booqable_slug": p.get("slug", ""),
                "booqable_sku": p.get("sku", ""),
                "base_price_ars": int(p.get("base_price_in_cents") or 0) // 100,
            })

        matches.append({
            "booqable_id": p.get("id", ""),
            "booqable_name": p.get("name", ""),
            "booqable_slug": p.get("slug", ""),
            "booqable_sku": p.get("sku", ""),
            "match_type": tipo,
            "confidence": f"{conf:.2f}",
            # Estos 3 son editables a mano por el usuario
            "local_slug": (local or {}).get("slug", ""),
            "local_nombre": (local or {}).get("nombre", ""),
            "local_id": (local or {}).get("id", ""),
        })

    # Escribir match CSV (ordenado: NO_MATCH primero para revision)
    sort_key = {"NO_MATCH": 0, "FUZZY_NAME": 1, "EXACT_MM": 2, "EXACT_SLUG": 3}
    matches.sort(key=lambda m: (sort_key[m["match_type"]], float(m["confidence"])))

    match_path = out_dir / "equipos_match.csv"
    with match_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "booqable_id", "booqable_name", "booqable_slug", "booqable_sku",
            "match_type", "confidence", "local_slug", "local_nombre", "local_id",
        ])
        w.writeheader()
        w.writerows(matches)

    # Escribir no_match (subset, para foco rapido)
    if no_match:
        no_match_path = out_dir / "equipos_no_match.csv"
        with no_match_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(no_match[0].keys()))
            w.writeheader()
            w.writerows(no_match)

    print(f"\nResumen:", file=sys.stderr)
    for k, v in stats.items():
        print(f"  {k:>12}: {v}", file=sys.stderr)
    print(f"\nMatch CSV:    {match_path}", file=sys.stderr)
    if no_match:
        print(f"No match CSV: {out_dir / 'equipos_no_match.csv'}", file=sys.stderr)
    print(
        "\nProximo paso: editar equipos_match.csv a mano (corregir slugs locales\n"
        "para los FUZZY_NAME dudosos y los NO_MATCH si tenes equivalente).\n"
        "Despues correr tools/booqable_to_alquileres.py con ese CSV.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
