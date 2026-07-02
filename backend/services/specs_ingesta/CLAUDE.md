# `services/specs_ingesta/` — motor de ingesta y normalización de specs (F0-F3 completas)

> **Estado: F0-F3 completas.** `parse/` (primitivas HTML) + `parsers/` (los 4 parsers grandes,
> movidos de `tools/`) ya son la fuente única — `equipo_html_extractor.py`/`luces_html_extractor.py`
> consumen de acá, **cero `sys.path.insert()` hacks**. `tools/*_parser.py` quedan como shims
> CLI-únicamente (⏰ LEGACY-adyacente) para los `*_rebuild.sh` y 2 tests que importan por nombre.
> `queries/extraer.py` (el entry point que reemplaza `extract_from_html`) todavía no existe — eso es
> F5. Hasta entonces `extract_from_html` acá es un re-export lazy (`__getattr__`, PEP 562) del viejo
> `equipo_html_extractor`.
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

## Estructura (F0-F3 completas; se sigue poblando fase a fase)

```
services/specs_ingesta/
  __init__.py     # barrel. __all__ es el contrato real.                         ✓ F0
  errors.py       # ErrorIngesta (400), HtmlNoParseable (422)                    ✓ F0
  CLAUDE.md        # este doc                                                    ✓ F0
  parse/          # DOMINIO — primitivas puras de lectura de HTML (Railway-safe) ✓ F1
    jsonld.py · dom.py · garbage.py · pares.py · serialize.py                    ✓ F1/F2
    fuentes/      #   adaptadores de fuente pluggable (bh.py, ebay.py, futuros)  ✗ F7
  parsers/        # DOMINIO — verbatim ex-tools/ (los 4 parsers grandes)         ✓ F3
    base.py       #   BHSpecsParser + helpers compartidos (antes en iluminacion_parser)
    camaras.py · lentes.py · iluminacion.py · modificadores.py · normalizar.py
  queries/        # LECTURA — lo que corre en Railway, nunca muta                ✗ F4-F5
    resolver.py   #   ya existe (F1) — resolve_pairs, el matcheo label→spec_key
  commands/       # ESCRITURA — el embudo que aprende (propone-aprobás)         ✗ F7
```

**Invariante commands↔queries (igual que `specs`/`categorias`):** `commands/` puede importar de
`queries/`; `queries/` **nunca** de `commands/`. `parse/` y `parsers/` no importan ni uno ni otro.

## Gotchas (se van sumando fase a fase)

- **`generic_html_extractor.py` YA era el core canónico** (F1 lo adoptó, no lo recreó) — tenía
  `extract_raw_pairs`/`resolve_pairs`/un solo `_GARBAGE_VALUES`. Los duplicados vivos estaban en
  `equipo` (merge JSON-LD triplicado inline) y `luces` (garbage-set propio con `":"` — drift real,
  fix confirmado: la Sony FX3A dejaba pasar "Signal-to-Noise Ratio: Not Specified by Manufacturer"
  como spec fantasma).
- **Reuso bajo prueba, no a ciegas:** cada pieza que se mueve/reusa de las capas viejas se prueba
  contra HTML real (dataset de 54 páginas en `/Users/tincho/Desktop/Paginas`, gitignored) antes de
  adoptarla tal cual — no basta con pyflakes limpio. Encontró 2 bugs reales en F2 (bool `false`→"Sí"
  por alimentar un string crudo a un serializador que esperaba Python bool tipado) y un gap real de
  extracción por línea en F3 (una constante a nivel módulo, `_TIPO_KEYWORDS`, quedó fuera del rango
  al hacer un slice manual por número de línea — **usar AST (`ast.parse` + `node.lineno`/
  `node.end_lineno`), no grep, para partir un archivo**: un grep-based slice asume que todo lo que
  hay entre dos `def` pertenece a la primera función, y no es así — puede haber constantes/alias de
  compat sueltos en el medio). Ledger completo en el plan.
- **Un test que importa por nombre desde el módulo viejo no siempre aparece en el primer grep** — el
  patrón `from X import (\n    nombre,\n)` multilínea, o un import indentado dentro de una función
  de test, no matchea un grep ingenuo de `^from`. Verificar con `grep -oP` exhaustivo antes de armar
  el `__all__` de un shim, y correr los tests afectados — no asumir que "no apareció" = "no se usa".
- **B0 (diagnóstico) corrió** sobre las 54 páginas reales: 87% detección OK, 2 casos de ruido real
  (RED KOMODO Production Pack, Canon Mount Adapter 0.71x — pendiente F4), 6 casos "0 specs" todos
  explicados por fuente no-B&H (3 eBay + 3 fabricante directo — confirma la necesidad de
  `parse/fuentes/` pluggable). Detalle → comentario en issue #1176.
- **F3 no movió `camaras_normalizar.py`/`lentes_normalizar.py`/`*_patches.py`** — confirmado que
  ningún código en vivo los importa (solo el pipeline offline de `_rebuild.sh`, que F3 no tocó).
  Quedan en `tools/` sin shim; se revisan si/cuando F5 cablea `cli.py`.
