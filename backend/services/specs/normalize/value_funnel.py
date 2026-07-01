"""normalize/value_funnel.py — el embudo de alias de valor (#1163, Fase 2/3).

`mapear_valor` es la ÚNICA función que decide "a qué valor canónico
corresponde este crudo" para un spec enum/multi_enum. Cuádruple uso (ver
docs/PLAN_SPECS_REDISENO.md):
  1. Normaliza al persistir  — commands/coerce.py antepone esto a su match.
  2. Valida mapeando         — queries/validation.py, en vez de rechazar.
  3. Búsqueda                — queries/aliases.py expande el término (Fase 4).
  4. Compatibilidad          — gratis: si todo se persiste canónico, el
     motor de compat (que matchea por igualdad exacta de value) deja de
     fallar por variantes tipo "FF" vs "Full-frame".

Fase 2: esta función existe y es correcta, pero TODAVÍA NADIE LA LLAMA desde
coerce/validation — eso es Fase 3 ("enchufar el embudo a las 4 bocas"). Hoy
es fail-open por diseño: `spec_value_aliases` nace vacía, así que hasta que
se curen alias reales, `mapear_valor` para el 99% de las specs simplemente
confirma el value si ya es canónico, o devuelve None si no matchea nada —
comportamiento equivalente a no tener embudo.
"""

from __future__ import annotations

from busqueda.normalizar import normalizar

from ..commands.coerce import _parse_opts


def mapear_valor(conn, spec_def_id: int, raw: str) -> str | None:
    """Dado un value crudo, devuelve el canónico correspondiente o None.

    Orden: (1) `raw` normalizado ya es un canónico de `enum_options` → se
    devuelve tal cual está en `enum_options` (preserva mayúsculas/formato
    canónico); (2) si no, se busca en `spec_value_aliases` para este
    `spec_def_id`; (3) si nada matchea, None (fail-open — el caller decide
    qué hacer, típicamente descartar o usar el raw sin coercionar).

    La comparación es vía `busqueda.normalizar.normalizar` en AMBOS lados
    (nunca se re-implementa la normalización en SQL — fuente única, evita
    el drift que ya se resolvió una vez para el motor de búsqueda)."""
    raw_norm = normalizar(raw)
    if not raw_norm:
        return None

    def_row = conn.execute(
        "SELECT enum_options FROM spec_definitions WHERE id = %s", (spec_def_id,)
    ).fetchone()
    if not def_row:
        return None

    # enum_options viene ya-lista en Postgres real (JSONB auto-decodeado por
    # el driver) pero como JSON string crudo en algunos fakes de test (sqlite)
    # — _parse_opts (mismo helper que usa coerce_and_serialize) normaliza los
    # dos casos. Fuente única, no un segundo parseo paralelo.
    for canonico in _parse_opts(def_row["enum_options"]):
        if normalizar(canonico) == raw_norm:
            return canonico

    alias_rows = conn.execute(
        "SELECT alias, valor_canonico FROM spec_value_aliases WHERE spec_def_id = %s",
        (spec_def_id,),
    ).fetchall()
    for r in alias_rows:
        if normalizar(r["alias"]) == raw_norm:
            return r["valor_canonico"]

    return None
