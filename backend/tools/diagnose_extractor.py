#!/usr/bin/env python3
"""tools/diagnose_extractor.py — Instrumento de diagnóstico del extractor de specs.

Loop de mejora del extractor: dado uno o más HTML reales de B&H/eBay, corre el
extractor y reporta, por archivo:

  - Categoría detectada.
  - raw_pairs: TODO lo que la página trae (JSON-LD + DOM).
  - matched:   specs que terminaron en la ficha (con su spec_key canónica).
  - unmatched: labels que la página trae pero el extractor NO mapeó (los gaps —
    estos son los candidatos a aliases o parser nuevos).
  - cobertura: % de raw_pairs que terminaron capturados.

No escribe nada. Es read-only sobre el extractor. Uso:

    python tools/diagnose_extractor.py <archivo.html> [<archivo2.html> ...]
    python tools/diagnose_extractor.py --json <archivo.html>   # salida machine-readable

El path a tools/ y backend/ lo inyecta services.equipo_html_extractor al importar.
"""

import argparse
import json
import sys
from pathlib import Path

# Asegurar que backend/ esté en el path para importar services.*
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from services.equipo_html_extractor import _detect_categoria, extract_from_html  # noqa: E402
from services.generic_html_extractor import extract_raw_pairs, resolve_pairs  # noqa: E402


def _norm(s: str) -> str:
    return " ".join((s or "").split()).strip().lower()


def _title_of(html: str) -> str:
    """Mismo title que usa extract_from_html para la detección de categoría."""
    import re
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


def diagnose_one(path: Path) -> dict:
    """Corre el extractor sobre un HTML y devuelve el reporte estructurado."""
    html = path.read_text(encoding="utf-8", errors="replace")

    # 1. Categoría detectada — con el title, igual que en producción.
    title = _title_of(html)
    categoria = _detect_categoria(html, title)

    # 2. Lo que la página trae (universal: JSON-LD + DOM).
    raw_pairs = extract_raw_pairs(html)

    # 3. Resolución contra el registry de aliases de la categoría detectada.
    #    matched/unmatched son la fuente real de "qué resuelve el alias-index":
    #    unmatched = labels que la página trae y NO mapeamos → candidatos a alias.
    cat_hint = categoria if categoria != "Desconocido" else None
    matched, unmatched = resolve_pairs(raw_pairs, cat_hint)

    # 4. Resultado FINAL del extractor completo (parser específico si la
    #    categoría se detectó; genérico si no).
    result = extract_from_html(html)
    final_specs = result.get("specs", [])

    total = len(raw_pairs)
    cobertura = (len(matched) / total * 100) if total else 0.0

    return {
        "archivo": path.name,
        "categoria_detectada": categoria,
        "categoria_sugerida": result.get("categoria_sugerida"),
        "marca": result.get("marca"),
        "modelo": result.get("modelo"),
        "raw_pairs_total": total,
        "matched_total": len(matched),
        "unmatched_total": len(unmatched),
        "specs_final_total": len(final_specs),
        "cobertura_pct": round(cobertura, 1),
        "matched_alias": [{"spec_key": m["spec_key"], "label": m["label"]} for m in matched],
        "perdidos": [{"label": u["label"], "value": (u["value"] or "")[:70]} for u in unmatched],
    }


def _print_report(rep: dict) -> None:
    print("=" * 78)
    print(f"📄 {rep['archivo']}")
    print(f"   Categoría detectada: {rep['categoria_detectada']}  →  sugerida: {rep['categoria_sugerida']}")
    print(f"   {rep['marca']} {rep['modelo']}")
    print(f"   La página trae {rep['raw_pairs_total']} specs · alias resuelve {rep['matched_total']} · "
          f"cobertura {rep['cobertura_pct']}% · ficha final {rep['specs_final_total']} specs")
    perdidos = rep["perdidos"]
    if perdidos:
        print(f"\n   ⚠ {len(perdidos)} labels que la página trae pero el alias-index NO mapea (candidatos a alias):")
        for p in perdidos:
            print(f"       · {p['label']:<40} = {p['value']}")
    else:
        print("\n   ✓ Capturamos todo lo que la página trae.")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description="Diagnóstico del extractor de specs.")
    ap.add_argument("archivos", nargs="+", type=Path, help="HTML(s) a diagnosticar")
    ap.add_argument("--json", action="store_true", help="Salida JSON machine-readable")
    args = ap.parse_args()

    reports = []
    for path in args.archivos:
        if not path.exists():
            print(f"✗ No existe: {path}", file=sys.stderr)
            continue
        try:
            reports.append(diagnose_one(path))
        except Exception as exc:  # noqa: BLE001
            print(f"✗ Error procesando {path.name}: {exc}", file=sys.stderr)

    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
    else:
        for rep in reports:
            _print_report(rep)
        if reports:
            total_perdidos = sum(len(r["perdidos"]) for r in reports)
            avg_cov = sum(r["cobertura_pct"] for r in reports) / len(reports)
            print("=" * 78)
            print(f"RESUMEN: {len(reports)} archivos · cobertura promedio {avg_cov:.1f}% · "
                  f"{total_perdidos} specs perdidas en total")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
