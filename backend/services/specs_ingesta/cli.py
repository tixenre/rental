"""services/specs_ingesta/cli.py — Entrypoint offline (la compu).

Uso:
    python -m backend.services.specs_ingesta.cli extract archivo.html
    python -m backend.services.specs_ingesta.cli extract archivo.html --categoria Cámaras
    python -m backend.services.specs_ingesta.cli extract archivo.html --out resultado.json

    python -m backend.services.specs_ingesta.cli context archivo.html
    python -m backend.services.specs_ingesta.cli context archivo.html --categoria Lentes --out ctx.json

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
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from services.specs_ingesta.llm.contexto import armar_contexto
from services.specs_ingesta.queries.extraer import extract_from_html


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

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
