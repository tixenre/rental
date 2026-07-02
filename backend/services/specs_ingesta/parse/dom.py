"""parse/dom.py — Extracción de pares {label, value} de tablas/dl del DOM.

Fallback genérico cuando no hay JSON-LD (o lo complementa): parsea
<tr><th>L</th><td>V</td></tr> y <dl><dt>L</dt><dd>V</dd></dl>. NO es lo
mismo que `parsers/base.py::BHSpecsParser` (que lee la estructura
`data-selenium` específica de B&H, más rica) — este es el fallback
agnóstico de sitio, movido verbatim de generic_html_extractor.py.
"""

from __future__ import annotations

import html as html_lib
from html.parser import HTMLParser


class _TableParser(HTMLParser):
    """Parser HTML minimalista: extrae pares de tablas <tr><th>L</th><td>V</td></tr>
    y listas de definición <dl><dt>L</dt><dd>V</dd></dl>.
    """

    def __init__(self) -> None:
        super().__init__()
        self.pairs: list[dict[str, str]] = []
        self._tag_stack: list[str] = []
        self._pending_label: str | None = None
        self._buf: str = ""

    def handle_starttag(self, tag: str, attrs: list) -> None:
        self._tag_stack.append(tag)
        if tag in ("th", "dt"):
            self._buf = ""
            self._pending_label = None
        elif tag in ("td", "dd"):
            self._buf = ""

    def handle_endtag(self, tag: str) -> None:
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
        text = html_lib.unescape(self._buf.replace("\xa0", " ").strip())
        if tag in ("th", "dt") and text:
            self._pending_label = text
        elif tag in ("td", "dd") and text and self._pending_label:
            self.pairs.append({"label": self._pending_label, "value": text})
            self._pending_label = None
        self._buf = ""

    def handle_data(self, data: str) -> None:
        if self._tag_stack and self._tag_stack[-1] in ("th", "td", "dt", "dd"):
            self._buf += data


def extract_dom_pairs(html_content: str) -> list[dict[str, str]]:
    """Extrae pares {label, value} de tablas y listas de definición del DOM."""
    parser = _TableParser()
    try:
        parser.feed(html_content)
    except Exception:
        pass
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for p in parser.pairs:
        if p["label"] not in seen:
            seen.add(p["label"])
            unique.append(p)
    return unique
