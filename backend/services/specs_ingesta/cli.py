"""services/specs_ingesta/cli.py — Entrypoint offline (la compu).

Uso:
    python -m backend.services.specs_ingesta.cli extract archivo.html
    python -m backend.services.specs_ingesta.cli extract archivo.html --categoria Cámaras
    python -m backend.services.specs_ingesta.cli extract archivo.html --out resultado.json

    python -m backend.services.specs_ingesta.cli context archivo.html
    python -m backend.services.specs_ingesta.cli context archivo.html --categoria Lentes --out ctx.json

    python -m backend.services.specs_ingesta.cli diagnose archivo1.html archivo2.html ...
    python -m backend.services.specs_ingesta.cli diagnose tests/fixtures/html/dataset/*.html --json

`extract` corre el MISMO `queries.extraer.extract_from_html` que usa el
endpoint admin en Railway (`POST /admin/equipos/{id}/upload-html-source`,
vía `services.specs_ingesta.extract_from_html`) — determinístico, sin LLM.
Es la prueba del invariante "online == offline, mismo resultado sobre el
mismo HTML" (F5 del plan).

`context` es el suplemento offline (F7b) — para cuando `extract` no puede
con un HTML (eBay, fuente no-B&H, categoría mal-detectada): arma un bundle
prolijo (raw pairs + el schema de specs de la categoría) para que una
sesión de Claude Code interactiva lo razone y proponga specs vía
`services.specs.encolar_propuesta` — sin API key propia, sin llamada
automática a un LLM (decisión de diseño, ver `llm/contexto.py`).

`diagnose` (#1072/#1073) es el instrumento de medición de cobertura del
extractor — read-only, no toca DB. Por cada HTML: categoría detectada, cuántos
raw_pairs trae la página, cuántos resuelve el alias-index (`resolve_pairs`,
el mismo que usan `bespoke.py`/`generic.py`) y la lista de labels perdidos
(candidatos a alias nuevo). Reescrito, no portado, del PR #1073
(`backend/tools/diagnose_extractor.py`) — ese archivo importaba
`services.equipo_html_extractor`/`services.generic_html_extractor`, borrados
en F6 de este módulo; acá reusa `queries/detectar.py`+`parse/pares.py`+
`queries/resolver.py`+`queries/extraer.py`, ya movidos y con sus propios tests.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from services.specs_ingesta.llm.contexto import armar_contexto
from services.specs_ingesta.parse.pares import extract_raw_pairs
from services.specs_ingesta.queries.detectar import detect_categoria
from services.specs_ingesta.queries.extraer import extract_from_html
from services.specs_ingesta.queries.resolver import resolve_pairs


def _leer_html(html_file: str) -> str | None:
    html_path = Path(html_file)
    if not html_path.is_file():
        print(f"error: no existe {html_path}", file=sys.stderr)
        return None
    return html_path.read_text(encoding="utf-8", errors="replace")


def _emitir(data: dict, out: str | None, resumen: str) -> None:
    output = json.dumps(data, indent=2, ensure_ascii=False)
    if out:
        Path(out).write_text(output, encoding="utf-8")
        print(f"Guardado en {out} ({resumen})")
    else:
        print(output)


def _cmd_extract(args: argparse.Namespace) -> int:
    html_content = _leer_html(args.html_file)
    if html_content is None:
        return 1
    result = extract_from_html(html_content, categoria_hint=args.categoria)
    _emitir(result, args.out, f"{len(result['specs'])} specs, categoría: {result['categoria_sugerida']}")
    return 0


def _cmd_context(args: argparse.Namespace) -> int:
    html_content = _leer_html(args.html_file)
    if html_content is None:
        return 1
    ctx = armar_contexto(html_content, categoria_hint=args.categoria)
    _emitir(
        ctx, args.out,
        f"{len(ctx['raw_pairs'])} raw pairs, categoría: {ctx['categoria_detectada']}, "
        f"{len(ctx['schema_categoria'])} specs en el schema",
    )
    return 0


def _title_de(html_content: str) -> str:
    """Mismo regex de título que usa `queries/extraer.py::extract_from_html`
    para detectar categoría — la medición tiene que ver el mismo título que
    ve producción, no una heurística distinta."""
    m = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _diagnose_one(path: Path) -> dict:
    """Corre el extractor sobre un HTML y arma el reporte de cobertura.

    Read-only: no toca DB, no persiste nada. `matched`/`unmatched` salen de
    `resolve_pairs` (mismo resolver que corre en Railway vía bespoke.py/
    generic.py) — no un segundo mecanismo de matching para el diagnóstico."""
    html_content = path.read_text(encoding="utf-8", errors="replace")

    title = _title_de(html_content)
    categoria = detect_categoria(html_content, title)
    cat_hint = categoria if categoria != "Desconocido" else None

    raw_pairs = extract_raw_pairs(html_content)
    matched, unmatched = resolve_pairs(raw_pairs, cat_hint)

    result = extract_from_html(html_content)
    total = len(raw_pairs)
    cobertura_pct = round(len(matched) / total * 100, 1) if total else 0.0

    return {
        "archivo": path.name,
        "categoria_detectada": categoria,
        "categoria_sugerida": result.get("categoria_sugerida"),
        "marca": result.get("marca"),
        "modelo": result.get("modelo"),
        "raw_pairs_total": total,
        "matched_total": len(matched),
        "unmatched_total": len(unmatched),
        "specs_final_total": len(result.get("specs", [])),
        "cobertura_pct": cobertura_pct,
        "perdidos": [{"label": u["label"], "value": (u["value"] or "")[:70]} for u in unmatched],
    }


def _print_diagnose_report(rep: dict) -> None:
    print("=" * 78)
    print(f"{rep['archivo']}")
    print(f"   Categoría detectada: {rep['categoria_detectada']}  ->  sugerida: {rep['categoria_sugerida']}")
    print(f"   {rep['marca']} {rep['modelo']}")
    print(
        f"   La página trae {rep['raw_pairs_total']} pares · alias resuelve {rep['matched_total']} · "
        f"cobertura {rep['cobertura_pct']}% · ficha final {rep['specs_final_total']} specs"
    )
    perdidos = rep["perdidos"]
    if perdidos:
        print(f"\n   {len(perdidos)} labels que la página trae pero el alias-index NO mapea (candidatos a alias):")
        for p in perdidos:
            print(f"       - {p['label']:<40} = {p['value']}")
    else:
        print("\n   Capturamos todo lo que la página trae.")
    print()


def _cmd_diagnose(args: argparse.Namespace) -> int:
    reports = []
    for path in args.archivos:
        if not path.exists():
            print(f"error: no existe {path}", file=sys.stderr)
            continue
        try:
            reports.append(_diagnose_one(path))
        except Exception as exc:  # noqa: BLE001 — instrumento de diagnóstico: 1 HTML roto no debe abortar el batch
            print(f"error procesando {path.name}: {exc}", file=sys.stderr)

    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
    else:
        for rep in reports:
            _print_diagnose_report(rep)
        if reports:
            total_perdidos = sum(len(r["perdidos"]) for r in reports)
            avg_cov = sum(r["cobertura_pct"] for r in reports) / len(reports)
            print("=" * 78)
            print(f"RESUMEN: {len(reports)} archivos · cobertura promedio {avg_cov:.1f}% · {total_perdidos} labels perdidos en total")

    return 0 if reports else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="specs_ingesta.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract", help="Extrae specs de un HTML guardado (determinístico)")
    p_extract.add_argument("html_file", help="Path al HTML (Cmd+S de B&H)")
    p_extract.add_argument("--categoria", default=None, help="Hint de categoría (evita la detección automática)")
    p_extract.add_argument("--out", default=None, help="Path de salida (default: stdout)")
    p_extract.set_defaults(func=_cmd_extract)

    p_context = sub.add_parser(
        "context", help="Arma el bundle para razonar specs a mano / con Claude Code (suplemento offline)"
    )
    p_context.add_argument("html_file", help="Path al HTML (eBay, fabricante, o un caso que 'extract' resolvió mal)")
    p_context.add_argument("--categoria", default=None, help="Hint de categoría (evita la detección automática)")
    p_context.add_argument("--out", default=None, help="Path de salida (default: stdout)")
    p_context.set_defaults(func=_cmd_context)

    p_diagnose = sub.add_parser(
        "diagnose", help="Mide cobertura del alias-index sobre uno o más HTML (read-only, #1072)"
    )
    p_diagnose.add_argument("archivos", nargs="+", type=Path, help="HTML(s) a diagnosticar")
    p_diagnose.add_argument("--json", action="store_true", help="Salida JSON machine-readable")
    p_diagnose.set_defaults(func=_cmd_diagnose)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
