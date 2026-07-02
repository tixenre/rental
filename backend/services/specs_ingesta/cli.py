"""services/specs_ingesta/cli.py — Entrypoint offline (la compu).

Uso:
    python -m backend.services.specs_ingesta.cli extract archivo.html
    python -m backend.services.specs_ingesta.cli extract archivo.html --categoria Cámaras
    python -m backend.services.specs_ingesta.cli extract archivo.html --out resultado.json

Corre el MISMO `queries.extraer.extract_from_html` que usa el endpoint admin
en Railway (`POST /admin/equipos/{id}/upload-html-source`, vía
`services.specs_ingesta.extract_from_html`) — determinístico, sin LLM. Es la
prueba del invariante "online == offline, mismo resultado sobre el mismo
HTML" (F5 del plan). La capa LLM offline (`llm/`, suplemento para eBay/
fuentes-no-B&H/misdetección) se cablea acá cuando exista — F7, todavía no.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from services.specs_ingesta.queries.extraer import extract_from_html


def _cmd_extract(args: argparse.Namespace) -> int:
    html_path = Path(args.html_file)
    if not html_path.is_file():
        print(f"error: no existe {html_path}", file=sys.stderr)
        return 1

    html_content = html_path.read_text(encoding="utf-8", errors="replace")
    result = extract_from_html(html_content, categoria_hint=args.categoria)

    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"Guardado en {args.out} ({len(result['specs'])} specs, categoría: {result['categoria_sugerida']})")
    else:
        print(output)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="specs_ingesta.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract", help="Extrae specs de un HTML guardado")
    p_extract.add_argument("html_file", help="Path al HTML (Cmd+S de B&H)")
    p_extract.add_argument("--categoria", default=None, help="Hint de categoría (evita la detección automática)")
    p_extract.add_argument("--out", default=None, help="Path de salida (default: stdout)")
    p_extract.set_defaults(func=_cmd_extract)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
