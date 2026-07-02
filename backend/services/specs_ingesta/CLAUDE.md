# `services/specs_ingesta/` — motor de ingesta y normalización de specs (F0 en curso)

> **Estado: F0 (scaffold) completo. El resto de la implementación vive en los `*_html_extractor.py`
> viejos todavía** — `extract_from_html` acá es un re-export temporal, sin lógica movida.
> Plan completo + fases → [`docs/PLAN_SPECS_INGESTA.md`](../../../docs/PLAN_SPECS_INGESTA.md) ·
> tracking → issue [#1176](https://github.com/tixenre/rental/issues/1176) · rama aislada
> `feature/specs-ingesta`, PR sin mergear hasta completar el módulo (convención "PR como hoja de ruta").

## Por qué existe

Hoy la extracción HTML→specs vive partida en dos capas mal empalmadas: una capa "wrapper" en
`services/{generic,luces,equipo}_html_extractor.py` (~1200 líneas, con duplicación real — parseo
JSON-LD triplicado, garbage-filter con constantes distintas entre `generic` y `luces`) que reachea
hacia `tools/*_parser.py` (~6400 líneas más, en la raíz del repo) vía un hack de `sys.path.insert()`.

Este módulo consolida ambas capas en un motor único, CQRS-lite (espeja `services/specs/` y
`services/categorias/`), y **maximiza el parser determinístico** (issue #1072 subsumido acá) — no
solo reordena código.

## La frontera con `services/specs/` — dependencia UN SOLO sentido

`specs_ingesta` **lee** de `services/specs` (su barrel público, nunca internals). `specs` **nunca**
importa `specs_ingesta`. Tres canales (detalle en el plan):
- **Canal A** (lectura): `REGISTRY`/`get_categoria`, `coerce_and_serialize`, el embudo de valor.
- **Canal B** (emisión indirecta): este módulo emite `spec_key` y se **detiene ahí** — nunca resuelve
  `spec_def_id` ni llama `persistir_specs`. El front traduce, el humano confirma, recién ahí `specs`
  persiste. El motor de persistencia sagrado no se toca.
- **Canal C** (escritura, vía `commands/`): propone specs/aliases nuevos a la cola
  `spec_propuestas_pendientes` (ya existe en `specs`, hoy huérfana) — nunca escribe el registry directo.

## Split de runtime (invariante dura)

- **Railway (en vivo, el endpoint admin):** solo `queries/` + `parse/` + `parsers/` — determinístico,
  sin LLM, sin API key. Railway **no baja HTML** (mismo bloqueo de bots que el scraping) — solo parsea
  lo que el form le sube.
- **La compu (offline, `cli.py`):** el mismo `queries/extraer` + la capa `llm/` como suplemento —
  resuelve lo que el determinístico no puede (eBay, fuentes de fabricante, misdetección, unmatched).
- **`llm/` SOLO lo importa `cli.py`.** Si algo en `queries/` o `parse/` importa de `llm/`, es un bug —
  rompe el split de runtime.

## Estructura (F0 — scaffold; se puebla fase a fase)

```
services/specs_ingesta/
  __init__.py     # barrel. __all__ es el contrato real.                         ✓ F0
  errors.py       # ErrorIngesta (400), HtmlNoParseable (422)                    ✓ F0
  CLAUDE.md        # este doc                                                    ✓ F0
  parse/          # DOMINIO — primitivas puras de lectura de HTML (Railway-safe) ✗ F1
    fuentes/      #   adaptadores de fuente pluggable (bh.py, ebay.py, futuros)  ✗ F1/F7
  parsers/        # DOMINIO — verbatim ex-tools/ (los 4 parsers grandes)         ✗ F3
  queries/        # LECTURA — lo que corre en Railway, nunca muta                ✗ F1-F5
  commands/       # ESCRITURA — el embudo que aprende (propone-aprobás)         ✗ F7
```

**Invariante commands↔queries (igual que `specs`/`categorias`):** `commands/` puede importar de
`queries/`; `queries/` **nunca** de `commands/`. `parse/` y `parsers/` no importan ni uno ni otro.

## Gotchas (se van sumando fase a fase)

- **`generic_html_extractor.py` YA es el core canónico** (no recrear en F1) — tiene
  `extract_raw_pairs`/`resolve_pairs`/un solo `_GARBAGE_VALUES`. Los duplicados vivos están en
  `equipo` (merge JSON-LD triplicado inline) y `luces` (garbage-set propio con `":"` — drift real).
- **Reuso bajo prueba, no a ciegas:** cada pieza que se mueve/reusa de las capas viejas se prueba
  contra HTML real (dataset de 54 páginas en `/Users/tincho/Desktop/Paginas`, gitignored) antes de
  adoptarla tal cual. Ledger completo en el plan.
- **B0 (diagnóstico) ya corrió** sobre las 54 páginas reales: 87% detección OK, 2 casos de ruido real
  (RED KOMODO Production Pack, Canon Mount Adapter 0.71x — arreglar en F4), 6 casos "0 specs" todos
  explicados por fuente no-B&H (3 eBay + 3 fabricante directo — confirma la necesidad de
  `parse/fuentes/` pluggable). Detalle → comentario en issue #1176.
