# `services/specs_ingesta/` — motor de ingesta y normalización de specs (F0-F6 completas)

> **Estado: F0-F6 completas.** Los 3 wrapper viejos (`services/{equipo,luces,generic}_html_extractor.py`)
> **ya no existen** — se borraron en F6. `parse/` (primitivas HTML) + `parsers/` (los 4 parsers
> grandes, movidos de `tools/`) + `queries/{resultado,bespoke,generic,detectar,extraer}.py` son la
> fuente única, sin shims por delante — **cero `sys.path.insert()` hacks, cero lógica duplicada, cero
> dispatcher fuera de `queries/extraer.py`**. `tools/*_parser.py` siguen como shims CLI-únicamente
> (⏰ LEGACY-adyacente, no tocados por F6) para los `*_rebuild.sh` y 2 tests que importan por nombre.
> `specs_ingesta.extract_from_html` (el barrel) importa DIRECTO de `queries/extraer.py`. `cli.py` es
> el entry point offline — mismo `queries/extraer`, verificado byte-idéntico al del endpoint sobre el
> mismo HTML. La capa `llm/` (suplemento offline-only) todavía no existe — eso es F7, la única fase
> que falta.
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
- **La compu (offline, `cli.py`):** el mismo `queries/extraer` + la capa `llm/` como suplemento (F7,
  todavía no existe) — resuelve lo que el determinístico no puede (eBay, fuentes de fabricante,
  misdetección, unmatched).
- **`llm/` SOLO lo importa `cli.py`.** Si algo en `queries/` o `parse/` importa de `llm/`, es un bug —
  rompe el split de runtime.

## Estructura (F0-F6 completas; solo falta F7)

```
services/specs_ingesta/
  __init__.py     # barrel. __all__ es el contrato real.                         ✓ F0
  errors.py       # ErrorIngesta (400), HtmlNoParseable (422)                    ✓ F0
  CLAUDE.md        # este doc                                                    ✓ F0
  cli.py          # entry point offline — mismo queries/extraer, sin LLM todavía ✓ F5
  parse/          # DOMINIO — primitivas puras de lectura de HTML (Railway-safe) ✓ F1
    jsonld.py · dom.py · garbage.py · pares.py · serialize.py                    ✓ F1/F2
    fuentes/      #   adaptadores de fuente pluggable (bh.py, ebay.py, futuros)  ✗ F7
  parsers/        # DOMINIO — verbatim ex-tools/ (los 4 parsers grandes)         ✓ F3
    base.py       #   BHSpecsParser + helpers compartidos (antes en iluminacion_parser)
    camaras.py · lentes.py · iluminacion.py · modificadores.py · normalizar.py
  queries/        # LECTURA — lo que corre en Railway, nunca muta                ✓ F5
    resolver.py   #   resolve_pairs, el matcheo label→spec_key                   ✓ F1
    resultado.py  #   build_result/generic_fallback_result — fuente única AutocompletarResult ✓ F4
    bespoke.py    #   4 categorías con parser (cámaras/lentes/modificadores/iluminación)       ✓ F4
    generic.py    #   categorías sin parser — + filtro de ruido (package_weight, etc.)         ✓ F4
    detectar.py   #   detección de categoría, MAXIMIZADA contra el dataset real                ✓ F5
    extraer.py    #   entry point único (detecta + rutea) — usado por Railway Y cli.py          ✓ F5
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
  (RED KOMODO Production Pack, Canon Mount Adapter 0.71x), 6 casos "0 specs" todos explicados por
  fuente no-B&H (3 eBay + 3 fabricante directo — confirma la necesidad de `parse/fuentes/` pluggable).
  Detalle → comentario en issue #1176. **F4 resolvió el filtro de ruido genérico** (`package_weight`/
  `box_dimensions` — Canon Mount Adapter queda 100% limpio); **F5 resolvió RED KOMODO** — la causa real
  era que el título no matcheaba el regex de detección de cámaras (caía al genérico, 70 specs de ruido
  de los accesorios del bundle) — con detección arreglada rutea al parser de cámaras, 33 specs curados.
- **F3 no movió `camaras_normalizar.py`/`lentes_normalizar.py`/`*_patches.py`** — confirmado que
  ningún código en vivo los importa (solo el pipeline offline de `_rebuild.sh`, que F3 no tocó).
  Quedan en `tools/` sin shim; se revisan si/cuando F5 cablea `cli.py`.
- **F4 — el "criterio más seguro" no lo era: probarlo contra data real lo refutó.** El merge JSON-LD
  tenía 2 criterios distintos en el código viejo — `equipo` anteponía JSON-LD siempre primero, `luces`
  hacía dedupe (solo agregaba si el label no estaba ya en el DOM). La primera versión de
  `parse/secciones.py` adoptó el de luces asumiendo que "no pisar nada" era más conservador — **al
  probarlo contra las 103 páginas reales de Luces perdía datos en 111 casos**: JSON-LD trae el valor
  RICO (ej. multi-línea con las 4 combinaciones de ángulo×CCT), el DOM uno resumido para el mismo
  label, y el dedupe se quedaba con el resumido por haber llegado "primero". Se revirtió al criterio de
  `equipo` (más simple, además de correcto). Lección: cuando dos implementaciones viejas discrepan y hay
  que elegir una, "la que parece más cautelosa" es una hipótesis igual que cualquier otra — se prueba
  contra data real, no se elige por intuición aunque suene razonable.
- **F4 — unificar destapó 2 bugs reales que llevaban tiempo silenciosos en `luces_html_extractor.py`**
  (nunca se habrían visto sin el diff empírico completo, no alcanzaba con leer el código): `peso` SIEMPRE
  daba `None` en la ficha de una luz porque el código buscaba la key `"peso"` en el dict de specs, pero
  el mapper real emite `"peso_g"`; `keywords` SIEMPRE daba `[]` porque estaba hardcodeado en vez de llamar
  `compute_keywords()` (sin ninguna razón category-specific — la función es genérica). Ambos se
  corrigieron gratis al pasar luces por el mismo `build_result` que ya usaban las otras 3 categorías.
- **F5 — "maximizar detección" es barrido sistemático, no parchear el caso ya conocido.** B0 solo había
  encontrado el caso RED KOMODO. Correr `detect_categoria` contra las 47 páginas B&H reales del dataset
  (filtrando los assets `_files/` del guardado y las páginas de fabricante que no son B&H) encontró 3
  fallas MÁS que nadie había visto: 2 casos donde el título decía "lens" para un accesorio óptico de luz
  (no un lente fotográfico) y caía al parser EQUIVOCADO — peor que caer a "Desconocido", porque produce
  un resultado con apariencia válida pero basura (1 spec). La lección: un fix puntual sobre el caso que
  se conoce deja plata en la mesa — correr el diagnóstico contra TODO el dataset (mismo método de B0) es
  lo que separa "arreglé el caso que vi" de "maximicé la detección".
- **F5 — un bug de parseo puede esconderse en un campo que nunca se compara.** Ninguna verificación
  previa (F1-F4) había puesto el ojo en `modelo`/`nombre_normalizado` porque los diffs se enfocaban en
  `specs` (lo que importa para persistir) — pero `BHSpecsParser.title` tenía un bug real y grande (52/277
  páginas con "Accessibility" pegado al título, sin espacio: un `<title>` de un ícono SVG de accesibilidad
  se sumaba al título de la página porque el parser no distingue `<title>` de `<head>` de `<title>` de
  `<svg>`) que solo salió a la luz al mirar TODOS los campos del diff, no solo los que uno espera que
  cambien. Moraleja: al verificar "no cambió nada inesperado", diffear el resultado completo — no solo
  el campo que la fase que estás haciendo se supone que toca.
- **F5 — un valor "roto" puede ser basura genuina de la fuente, no un bug propio.** Un `extras['video_io']
  = '</b<'` en RED KOMODO resultó ser exactamente ese string, literal, en el JSON-LD del HTML de B&H
  (`grep` lo confirmó en el HTML crudo) — no algo que nuestro parser corrompe. Antes de "arreglar" un
  valor sospechoso, confirmar si el HTML fuente ya lo trae roto; en ese caso no hay fix razonable del
  lado del parser (headers/JSON-LD malformados de terceros son la realidad de scrapear/parsear la web) y
  el bucket `extras` (cola larga, no curada) ya tolera esto por diseño — no se promueve a `specs`.
- **F6 — podar un shim de test puede ser la oportunidad de testear lo REAL, no solo mudar el import.**
  `_specs_dict_to_array` (el shim ⏰ LEGACY de F2) no tenía equivalente exacto en el módulo nuevo — su
  firma simplificada (`registry_labels` dict a mano) nunca fue lo que corre en producción, solo un
  stand-in de cuando el test se escribió. En vez de preservarla artificialmente, los 5 tests que la
  usaban se reescribieron contra `parse/serialize.py::specs_dict_to_array` (la función real, con
  `categoria` en vez de un dict a mano) — mismas invariantes, pero ahora ejercitando el código que
  efectivamente corre. Regla: podar un shim de test no es "encontrar dónde pegar el import nuevo" —
  es la oportunidad de preguntarse si el test debería ejercitar la función real en primer lugar.
- **F6 — un `sys.path` hack puede sobrevivir escondido DENTRO de un test**, no solo en código de
  producción. F1/F3 habían limpiado los hacks de `services/`/`tools/`, pero
  `test_spec_key_normalization.py::test_parser_luz_no_emite_keys_huerfanas` tenía su propio
  `sys.path.insert()` apuntando a `tools/iluminacion_parser` — invisible a un grep que solo mira
  `services/`. Verificar `tests/` con la misma exhaustividad que el código de producción, no asumir
  que los hacks solo viven del lado no-test.
- **F6 — borrar un archivo puede exponer que un doc lo describía mal desde antes.** `docs/SISTEMA_SPECS.md`
  §1 describía un flujo Firecrawl+LLM (`/admin/equipos/autocompletar`, `/batch-enriquecer`) que ya no
  existía — ni siquiera era el dispatcher pre-`specs_ingesta`, era una capa MÁS vieja todavía. Nadie lo
  había notado porque nadie leyó ese doc buscando algo relacionado hasta que F6 borró el archivo que
  citaba. Reescrito con el flujo real (§1 arriba). El resto de la staleness ya conocida de ese doc
  (§2/§5/§6, el workflow de seeders viejo) se dejó como estaba — está fuera del alcance de esta
  iniciativa y ya tiene su propio disclaimer.
