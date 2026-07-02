"""queries/detectar.py — Detección de categoría desde título + HTML.

Movido de equipo_html_extractor.py::_detect_categoria (F5 del rediseño de
ingesta) + MAXIMIZADO: barrido sistemático de los 277 HTMLs reales del
dataset (`/Users/tincho/Desktop/Paginas`, gitignored) filtrando a las 47
páginas B&H reales (no assets `_files/`, no otras fuentes) encontró 5 fallas
de detección — 2 ya conocidas por B0, 3 nuevas. Cada signal nuevo se probó
contra el dataset completo ANTES de sumarse (0 falsos positivos) — ver
docs/PLAN_SPECS_INGESTA.md F5.

Casos que arregla (evidencia, no intuición):
- "RED DIGITAL CINEMA KOMODO 6K Camera Production Pack" caía a Desconocido
  (→ genérico, 70 specs de ruido) porque "cinema" y "camera" no eran
  adyacentes en el título real. Fix: co-ocurrencia de ambas palabras en
  cualquier posición del título, no exige adyacencia. Verificado: ahora rutea
  al parser de cámaras, 33 specs curados en vez de 70 con ruido.
- "Aputure Quick Dome 60/90" caían a Desconocido. Un "dome" es un modificador
  de difusión — sumado a Modificadores.
- "Nanlite Fresnel Lens for Forza 300 and 500" / "amaran Spotlight SE 36°
  Lens Kit" caían a **Lentes** (peor que Desconocido: rutea al parser
  equivocado, producía 1 spec basura). Son accesorios ópticos PARA una luz
  (lente/kit que da forma al haz), no lentes fotográficos — el título dice
  "lens" pero el contexto (fresnel/spotlight) lo desambigua. Se movió el
  chequeo de Modificadores ANTES que Lentes (antes eran independientes
  porque se asumía que no colisionaban; esta evidencia lo refuta) + se
  sumaron "fresnel lens" y la co-ocurrencia spotlight+lens. Verificado: ahora
  producen 6 y 4 specs curados respectivamente, en vez de 1 basura.

Fuera de scope acá (no es un problema de REGEX de detección, es de FUENTE):
3 páginas del dataset (Mole Richardson, ARRI, GodoxOnline) son del sitio del
FABRICANTE, no de B&H — nuestros parsers dependen de la estructura
data-selenium/JSON-LD específica de B&H, así que aunque detectáramos bien su
categoría, no hay specs que extraer de esa estructura. Es el caso que motiva
`parse/fuentes/` pluggable (diferido a F7)."""

import re


def detect_categoria(html_content: str, title: str = "") -> str:
    """Detecta la categoría del HTML basado en título + JSON-LD + heurística.

    Devuelve: "Cámaras" | "Lentes" | "Adaptadores" | "Filtros" | "Modificadores"
              | "Iluminación" | "Desconocido"
    """
    t = (title or "").lower()
    body_excerpt = html_content[:50_000].lower()  # primeros 50KB

    # Adaptadores: mención explícita
    if re.search(r"\b(lens\s+mount\s+adapter|mount\s+converter|speedbooster|lens\s+adapter)\b", t):
        return "Adaptadores"
    if "lens mount adapter" in body_excerpt[:5000]:
        return "Adaptadores"

    # Filtros
    if re.search(r"\b(filter|polariz|pro-?mist|nd\s+filter|variable\s+nd)\b", t):
        return "Filtros"

    # Cámaras (incluye action cams). "cinema" + "camera" en cualquier
    # posición del título (no exige adyacencia) — ver caso RED KOMODO arriba.
    if re.search(r"\b(mirrorless|dslr|action\s+camera|action\s+cam\b|camera\s+body|camcorder|gopro|insta360)\b", t) or (
        re.search(r"\bcinema\b", t) and re.search(r"\bcamera\b", t)
    ):
        return "Cámaras"

    # Modificadores: accesorios que se acoplan a una luz. Chequeado ANTES que
    # Lentes — 2 casos reales usan "lens" en el título para un accesorio
    # óptico de luz, no un lente fotográfico (ver docstring del módulo).
    if re.search(
        r"\b(fresnel\s+attachment|fresnel\s+lens|softbox|octobox|diffusion\s+frame|beauty\s+dish|reflector\s+dish|parabolic|dome)\b",
        t,
    ) or (re.search(r"\bspotlight\b", t) and re.search(r"\blens\b", t)):
        return "Modificadores"

    # Lentes (después de adaptadores/filtros/modificadores para evitar falsos positivos)
    if re.search(r"\b(lens|lente)\b", t) and not re.search(r"\b(adapter|filter|hood|cap)\b", t):
        return "Lentes"

    # Iluminación: amplio (LED, light, monolight, flash, tube, panel, fresnel)
    if re.search(r"\b(led|light|monolight|spotlight|flash|tube\s+light|fresnel|panel)\b", t):
        return "Iluminación"

    return "Desconocido"
