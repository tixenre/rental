"""parse/dom.py — Extracción de pares {label, value} de tablas/dl del DOM.

Fallback genérico cuando no hay JSON-LD (o lo complementa): parsea
<tr><th>L</th><td>V</td></tr> y <dl><dt>L</dt><dd>V</dd></dl>. NO es lo
mismo que `parsers/base.py::BHSpecsParser` (que lee la estructura
`data-selenium` específica de B&H, más rica) — este es el fallback
agnóstico de sitio, movido verbatim de generic_html_extractor.py.

Captura texto ANIDADO dentro de la celda (F7b, del rediseño de ingesta) —
antes solo capturaba texto que fuera hijo DIRECTO de th/td/dt/dd; sitios con
markup por componentes (ej. eBay: `<dt><div><span>Label</span></div></dt>`)
quedaban en 0 pares. Verificado contra las 277 páginas del dataset: 0 diffs
en los casos B&H ya cubiertos (su markup no anida así) + 15 pares nuevos
reales en un caso eBay que antes daba 0 (Maximum Aperture, Mount, Focal
Length, Brand...). Dos guardas para no capturar ruido de la MISMA
profundidad: `aria-hidden="true"` (contenido duplicado para expansión
"read more", patrón estándar de accesibilidad — no es específico de eBay)
y `<button>` (texto de controles UI, no dato)."""

from __future__ import annotations

import html as html_lib
from html.parser import HTMLParser

# Elementos vacíos (nunca tienen endtag): si se empujan a la pila de tags
# abiertos quedan huérfanos para siempre — el primer endtag real que venga
# después (de un tag totalmente distinto) los "cierra" por error y desalinea
# el resto de la pila. Bug real encontrado al extender la captura a texto
# anidado (el markup de B&H no lo disparaba; el de eBay, lleno de <img>/
# íconos dentro de las celdas, sí) — lista estándar de void elements HTML5.
_VOID_ELEMENTS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})

_CELL_TAGS = ("th", "td", "dt", "dd")


class _TableParser(HTMLParser):
    """Parser HTML minimalista: extrae pares de tablas <tr><th>L</th><td>V</td></tr>
    y listas de definición <dl><dt>L</dt><dd>V</dd></dl>. Captura todo el texto
    anidado dentro de la celda (no solo hijos directos), salvo subárboles
    `aria-hidden`/`<button>`.
    """

    def __init__(self) -> None:
        super().__init__()
        self.pairs: list[dict[str, str]] = []
        self._stack: list[dict] = []  # [{tag, suppress}] por cada tag abierto (no solo celdas)
        self._pending_label: str | None = None
        self._buf: str = ""

    def _in_cell(self) -> bool:
        return any(frame["tag"] in _CELL_TAGS for frame in self._stack)

    def _suppressed(self) -> bool:
        return any(frame["suppress"] for frame in self._stack)

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in _VOID_ELEMENTS:
            return
        attrs_d = dict(attrs)
        is_noise = attrs_d.get("aria-hidden") == "true" or tag == "button"
        self._stack.append({"tag": tag, "suppress": is_noise})
        if tag in _CELL_TAGS:
            self._buf = ""

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID_ELEMENTS:
            return
        if self._stack and self._stack[-1]["tag"] == tag:
            self._stack.pop()
        if tag in _CELL_TAGS:
            text = html_lib.unescape(self._buf.replace("\xa0", " ").strip())
            if tag in ("th", "dt") and text:
                self._pending_label = text
            elif tag in ("td", "dd") and text and self._pending_label:
                self.pairs.append({"label": self._pending_label, "value": text[:500]})
                self._pending_label = None
            self._buf = ""

    def handle_data(self, data: str) -> None:
        if self._in_cell() and not self._suppressed():
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
