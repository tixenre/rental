"""busqueda/normalizar.py — normalización canónica de texto para búsqueda.

Fuente ÚNICA del lado backend de "cómo se normaliza un término para buscar".
Antes esta lógica estaba copiada (con variantes sutilmente distintas) en
`routes/busquedas.py`, en el slug, en el render de specs y en ~3 lugares del
front. Acá vive la versión canónica; el front la espeja en
`src/lib/search/normalize.ts` y un corpus de casos compartido
(`backend/tests/data/normalizacion_corpus.json`) garantiza que NO diverjan.

Reglas (idénticas en Python y TypeScript):
  1. minúsculas
  2. sin acentos/diacríticos (NFKD + drop combining) — "Batería" → "bateria"
  3. todo lo que no sea [a-z0-9] pasa a espacio — guiones, puntos, barras,
     paréntesis: "Sony A7-III" → "sony a7 iii", "f/2.8" → "f 2 8"
  4. espacios colapsados y recortados

Así "bateria" encuentra "Batería" y "a7 iii" encuentra "A7-III" sin que el
usuario tenga que tipear tildes ni guiones.
"""

import re
import unicodedata

# Largo máximo que se persiste/compara (alineado con search_queries.query_norm).
MAX_LEN = 120
# Mínimo para que un término normalizado sea útil como registro de búsqueda.
MIN_LEN = 2

_NO_ALNUM = re.compile(r"[^a-z0-9]+")


def quitar_acentos(texto: str) -> str:
    """Descompone (NFKD) y descarta los diacríticos combinantes."""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalizar(texto: str) -> str:
    """Normaliza un término a su forma canónica de búsqueda (ver reglas arriba).

    Devuelve "" si la entrada es vacía/None. No aplica MIN_LEN — eso es
    decisión del caller (el registro de búsquedas lo usa; el matching no)."""
    if not texto:
        return ""
    sin_acentos = quitar_acentos(texto.lower())
    # Cualquier no-alfanumérico (guion, punto, barra, etc.) → espacio.
    espaciado = _NO_ALNUM.sub(" ", sin_acentos)
    return " ".join(espaciado.split())[:MAX_LEN]


def tokenizar(texto: str) -> list[str]:
    """Normaliza y parte en tokens (palabras). Cada token debe matchear en
    algún campo para que el row sea un resultado (AND entre tokens)."""
    norm = normalizar(texto)
    return [t for t in norm.split(" ") if t]


def normalizar_para_registro(texto: str):
    """Normaliza para el registro de búsquedas (`search_queries.query_norm`).
    Devuelve None si queda demasiado corto (< MIN_LEN) para ser útil."""
    norm = normalizar(texto)
    if len(norm) < MIN_LEN:
        return None
    return norm
