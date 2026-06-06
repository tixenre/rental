"""busqueda/motor.py — motor único de búsqueda fuzzy (matching + ranking).

Espeja el patrón de `backend/reservas/` y `backend/reportes/`: toda la búsqueda
textual del sistema (clientes en el back-office, equipos en admin y catálogo)
pasa por acá, en vez de copiar SQL `ILIKE` ad-hoc en cada route. Una sola
dirección física para "cómo se busca y cómo se rankea".

Qué resuelve, apoyado en Postgres (`pg_trgm` + `unaccent`):
  - **Sin tildes** ("bateria" → "Batería") y **sin guiones/puntuación**
    ("a7 iii" → "A7-III"): ambos lados se pasan por `f_unaccent(lower(...))` y
    los separadores se colapsan en `normalizar`.
  - **Multi-palabra cruzando campos**: cada token debe aparecer en ALGÚN campo
    (OR entre campos), y TODOS los tokens deben estar (AND entre tokens). Así
    "santiago perez" matchea nombre="Santiago" + apellido="Pérez", y "sony fx3"
    matchea marca="Sony" + modelo="FX3".
  - **Tolerancia a typos**: `word_similarity` (trigramas) como red extra.
  - **Ranking por relevancia**: prefijo > contiene > similitud. Esto mata el
    "a veces me trae uno, a veces otro" — el mejor match va primero, siempre.

El motor NO ejecuta SQL: arma el fragmento `WHERE` y la expresión de `score`
(con sus params, en orden) para que el route los enchufe en su query. Todos los
comodines `%` viajan dentro de los params (nunca como literal en el SQL) para
no chocar con el manejo de `%` de psycopg2 — ver `database.PGConnection`.
"""

from dataclasses import dataclass, field

from busqueda.normalizar import normalizar

# Umbral de `word_similarity` para considerar un match fuzzy (0..1). Conservador
# a propósito: el substring exacto siempre rankea por encima del fuzzy, así que
# esto solo agrega resultados ante un typo, sin ensuciar con ruido.
UMBRAL_FUZZY = 0.5
# Largo mínimo del término para activar el fuzzy (typos en 1-2 chars = ruido).
MIN_FUZZY_LEN = 3


def campo_sql(expr: str) -> str:
    """Expresión canónica de un campo buscable: minúsculas, sin acentos y con la
    puntuación plegada a espacio (igual que `normalizar` del lado Python, para
    que columna y query coincidan: "A7-III" ≡ "a7 iii"). NULL-safe. DEBE
    coincidir textualmente con la usada en los índices GIN trigram de
    `database.init_db()` para que el planner los pueda usar."""
    return CAMPO_PLANTILLA.format(expr=expr)


# Forma canónica única, reusada por el motor y por los índices (database.py /
# migración). lower → sin acentos → no-alfanumérico colapsa a espacio → trim.
CAMPO_PLANTILLA = "btrim(regexp_replace(f_unaccent(lower(coalesce({expr}, ''))), '[^a-z0-9]+', ' ', 'g'))"


@dataclass
class Predicado:
    """Resultado del motor: fragmentos SQL + params (en orden de placeholders).

    - `where` / `where_params`: predicado de filtrado (va en el WHERE y en el
      COUNT). Envolver en paréntesis al concatenar.
    - `score` / `score_params`: expresión numérica de relevancia (va en el
      SELECT como `({score}) AS _score`); ordenar por `_score DESC`. Sus params
      van ANTES que los del WHERE en la lista final del SELECT.
    - `activo`: False si el query quedó vacío → el caller ignora la búsqueda.
    """

    where: str = ""
    where_params: list = field(default_factory=list)
    score: str = "0"
    score_params: list = field(default_factory=list)
    activo: bool = False


def construir(campos: list[str], query: str, *, fuzzy: bool = True) -> Predicado:
    """Arma el predicado de búsqueda de `query` sobre `campos`.

    `campos` es una lista de expresiones SQL (columnas o subqueries escalares)
    ya referidas a la tabla del caller, p.ej. `["e.nombre", "e.modelo"]` o una
    expresión combinada `"(c.nombre || ' ' || c.apellido)"`.
    """
    tokens = [t for t in normalizar(query).split(" ") if t]
    if not tokens or not campos:
        return Predicado()

    qnorm = " ".join(tokens)
    exprs = [campo_sql(c) for c in campos]

    # ── WHERE ──────────────────────────────────────────────────────────────
    where_params: list = []

    # AND entre tokens; cada token OR entre campos (substring sin acento).
    token_clauses = []
    for tok in tokens:
        ors = " OR ".join(f"{e} LIKE ?" for e in exprs)
        token_clauses.append(f"({ors})")
        where_params += [f"%{tok}%"] * len(exprs)
    where = " AND ".join(token_clauses)

    # Red fuzzy (typos): el query entero contra cada campo por trigramas.
    if fuzzy and len(qnorm) >= MIN_FUZZY_LEN:
        fuzz = " OR ".join(f"word_similarity(?, {e}) >= ?" for e in exprs)
        where = f"({where}) OR ({fuzz})"
        for _ in exprs:
            where_params += [qnorm, UMBRAL_FUZZY]

    # ── SCORE ──────────────────────────────────────────────────────────────
    # Por campo: prefijo (3) + contiene (2) + similitud (0..1). El score del
    # row es el mejor campo (GREATEST). Pesos discretos garantizan que un
    # prefijo exacto siempre gane a un "contiene", y este a un fuzzy.
    score_params: list = []
    por_campo = []
    for e in exprs:
        por_campo.append(
            f"((CASE WHEN {e} LIKE ? THEN 3 ELSE 0 END)"
            f" + (CASE WHEN {e} LIKE ? THEN 2 ELSE 0 END)"
            f" + word_similarity(?, {e}))"
        )
        score_params += [f"{qnorm}%", f"%{qnorm}%", qnorm]
    score = por_campo[0] if len(por_campo) == 1 else "GREATEST(" + ", ".join(por_campo) + ")"

    return Predicado(
        where=where,
        where_params=where_params,
        score=score,
        score_params=score_params,
        activo=True,
    )
