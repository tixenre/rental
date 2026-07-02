# Plan — `specs_ingesta`: el motor-embudo de specs (2 iniciativas en paralelo + split de runtime)

> Tracking: issue padre (plan completo) → [#1178](https://github.com/tixenre/rental/issues/1178). Iniciativa A →
> issue [#1175](https://github.com/tixenre/rental/issues/1175) · Iniciativa B →
> issue [#1176](https://github.com/tixenre/rental/issues/1176), PR-hoja-de-ruta [#1177](https://github.com/tixenre/rental/pull/1177)
> (rama `feature/specs-ingesta`, sin mergear hasta completar el módulo). Manual técnico del módulo →
> `backend/services/specs_ingesta/CLAUDE.md`.

## Contexto (por qué)

Lo que "realmente le falta al rental" son los equipos con su ficha técnica. Hoy solo **28 de 199** equipos
activos tienen alguna spec (14%), aunque **138 ya tienen su `bh_url`**. B&H es la fuente; **bajar** la página
automáticamente no anda (bloqueo de bots), pero **guardar el HTML a mano y parsearlo SÍ**. El dueño tiene un
dataset de **277 HTMLs** guardados (Cámaras, Lentes —incluye adaptadores y algunos eBay—, Luces, Modificadores;
de esos, 54 son páginas de producto reales, el resto son assets `_files/` del guardado).

**Medición sobre esos HTMLs reales (B0, corriendo el extractor que YA existe, read-only, sobre las 54 páginas):**

| | Total | Detección OK | Genérico (ruido) | 0 specs |
|---|---|---|---|---|
| Cámaras | 7 | 6 | 1 | 0 |
| Lentes | 20 | 19 | 1 | 3 (eBay) |
| Luces | 20 | 18 | 2 | 2 (fabricante directo) |
| Modificadores | 7 | 4 | 3 | 1 (fabricante directo) |
| **Total** | **54** | **47 (87%)** | **7 (13%)** | **6 (11%)** |

0 errores/excepciones. Los "0 specs" están **todos explicados**: eBay (sin estructura B&H) o páginas del
**fabricante directo** (arri.com, molerichardson.com, godoxonline.com — el dueño ya tiene HTMLs de estas fuentes
guardados, confirmando que multi-fuente no es hipotético). Solo 2 casos son ruido real de detección (RED KOMODO
Production Pack, Canon Mount Adapter 0.71x).

**Diagnóstico honesto:** el sistema actual **sirve bien para la mayoría B&H con detección OK** (87%, mejor de lo
que una muestra chica inicial sugería). Los problemas reales son puntuales: 2 casos de ruido + 6 de fuente-no-B&H.
**Ninguno lo arregla un refactor de código en sí** — el refactor ordena y facilita maximizar, pero el valor sale
de: usar lo que anda + suplir los huecos puntuales + (en paralelo) ordenar el código.

## Principio rector: la correctitud de los specs es sagrada

El norte de todo este trabajo (dicho por el dueño): **un spec tiene que ser verdadero y COMPARABLE entre
equipos.** El marketing mete ruido — la Amaran 300 grita "360 W" para tapar que no publica lúmenes; cada marca
reporta a su conveniencia. El objetivo de largo plazo es una **"Wikipedia" de equipos**: campos normalizados,
honestos y comparables lado a lado, que corten ese ruido. Consecuencias de diseño, transversales a todo el plan:

- **Nunca inventar un dato.** Si no hay base, es "sin dato" (no un número lindo). Todo valor derivado/estimado
  lleva su **provenance** visible (medido/derivado/estimado).
- **Dato traído de afuera = hipótesis hasta validarlo.** El LLM offline puede no solo normalizar lo que ya está
  en el HTML, sino **buscar** lo que falta (fabricante, reviews, otros retailers). Pero eso NO se usa crudo: se
  **valida antes de persistir** (cross-check de ≥2 fuentes independientes + confirmación del dueño), se guarda
  **de dónde salió** (source URL), y sin validar queda como **candidato**, no como spec. Es el principio del repo
  _"un hallazgo es hipótesis hasta confirmarlo"_ aplicado a la data de specs.
- **Comparabilidad > fidelidad al texto de la marca.** Se normaliza a unidades y ejes comunes (ej. lúmenes a
  CCT de referencia) aunque la marca lo publique distinto.
- **La normalización es un patrón, no un one-off.** Los lúmenes (A4) son el **caso piloto**; hay que **cazar
  sistemáticamente** más casos de "ruido de marketing" y dejarlos comparables.
- El **motor de comparación** es el pago final, pero va DESPUÉS: *primero la data bien.*

> Este principio es candidato a **MEMORIA/DECISIONES** ("correctitud de specs = sagrada; comparabilidad real
> sobre ruido de marketing"). Se propone al dueño **después** de que A4 esté andando (no frenar la implementación
> con gobernanza).

## Principio de método: reuso bajo prueba (no a ciegas)

Preocupación del dueño (correcta): esta es ~la **tercera iniciativa** sobre specs. "El código existe" fue lo que
también asumieron las anteriores, y acá estamos de nuevo. **Conclusión:** reusar código es una **hipótesis hasta
probar que encaja** — el mismo _"un hallazgo es hipótesis hasta confirmarlo"_ aplicado al código, no solo a la
data.

- **Ningún reuso a ciegas.** Cada pieza candidata a reusar lleva un **probe con data real ANTES** de construir
  encima. Pasa → se reusa. Falla → sabemos **por qué** (¿el código, el concepto, o el encaje?) y
  reemplazamos/adaptamos con evidencia, no por fe.
- La barra es _proporcional_: el probe es la señal más barata que conteste "¿sirve para lo que ahora queremos?".

**Ledger de reuso:**

| Pieza candidata | Probe con data real | Estado |
|---|---|---|
| Parsers determinísticos B&H | Correr sobre las 54 páginas reales | **PROBADO ✓** (B0: 87% detección OK, 2 casos de ruido concretos, 0 errores) — se adopta **con** F4/F5, no tal cual |
| `generic` como core canónico | Correr `extract_raw_pairs`/`resolve_pairs` sobre el dataset | **PROBADO ✓** (F1: adoptado como core de `parse/`+`queries/resolver.py`, verificado byte-a-byte) |
| `spec_render` como display único | Renderizar valores reales (lúmenes+unidad, rango, bool) | **PROBADO ✓ parcial** (F2: display real verificado sobre las 54 páginas) — el **badge de provenance** sigue sin construir, es Iniciativa A4 |
| `coerce_and_serialize` / `derive_lumens_from_lux` | Alimentar valores B&H reales + un lux/beam de datasheet conocido | pendiente — **probar en A4** |
| Cola `spec_propuestas_pendientes` | Redactar un payload real (`spec_nueva`) desde unmatched real del dataset | **PROBADO ✓** (F7: `spec_nueva` con `{categoria, label, label_normalizado, count, ejemplos}` alcanza — verificado con el caso real de Modificadores, "interior color" 4x/"package weight" 6x, contra Postgres real) |
| `value_funnel` (`mapear_valor`) | Confirmar que un enum real (FF→Full-frame) pasa end-to-end | tiene tests; **re-confirmar contra el dataset** |

## Decisión de arquitectura central: split por runtime

- **Railway (servidor, camino en vivo del admin):** parser **determinístico maximizado**. Gratis, rápido,
  seguro, **sin API key ni LLM**. Es la extracción que corre en `POST /admin/equipos/{id}/upload-html-source`.
- **La compu (local/offline, el CLI batch):** el **mismo core determinístico + una capa LLM** que resuelve lo
  que el determinístico no puede (eBay, fuentes de fabricante, misdetección, labels/valores unmatched).

**Invariante:** el LLM es **offline-only**. `specs_ingesta/queries/` (lo que Railway ejecuta) queda puro y
determinístico; la capa LLM vive detrás del CLI y **nunca** se invoca en el servidor.

**Railway NO baja HTML** (mismo bloqueo que el scraping): solo **parsea el HTML que le subís** por el form. El
campo `links` guardado en el equipo NO es para que Railway fetchee — es (a) la **fuente de verdad anotada por
equipo** y (b) el input del **flujo local**.

## Modelo de datos y flujo

1. **Specs por categoría (el schema lo define la categoría, no el HTML).** El conjunto de specs es **por
   categoría** (ya es así: cada `CategoriaRegistry` tiene su `specs`). El HTML/LLM llena **valores**, no decide
   qué campos existen. Campo sin valor → **"sin dato"**; label/valor fuera del schema → al learning loop. No
   fuerza: la categoría da el esqueleto, el parseo completa lo más posible.
   - **Matiz:** distinguir "sin dato" (falta, llenar) de **"no aplica"** (N/A por subtipo) para que la
     completitud no mienta.
   - **Nota de diseño — filtros faceteados (el modelo Amazon), GUARDADO como trabajo futuro:** facets por
     categoría, mostrar un filtro solo si **(a) aplica y (b) tiene >1 valor distinto**. Issue `someday` al
     ejecutar.
2. **Campo `links` (PLURAL) = fuentes del equipo — no un campo `bh_url` singular.** Nombrar el campo por B&H lo
   bakea como "la" verdad; choca con multi-fuente + el guardrail de conflicto. `links` = lista de `{tipo, url}`
   (B&H, fabricante, medido-DXO/LensRentals, Adorama…), campo aparte del nombre del equipo. Es la llave de
   matcheo HTML↔equipo y el input del flujo local. **Fuentes de fabricante/medidos, por autoridad:** datos
   MEDIDOS (DXOMARK, LensRentals, CineD) > fabricante oficial + su PDF de specs > retailers.
3. **Guardar la fuente de verdad, limpia y re-chequeable.** Del HTML se guarda solo lo que sirve (stripear
   scripts/estilos/íconos sociales — reusar el stripping de PR #1071) + los pares crudos extraídos, para poder
   re-parsear con un extractor mejor.
4. **Valor canónico-parseable + display reconstruido — SIN migración.** `equipo_specs.value` se queda TEXT pero
   SIEMPRE canónico-parseable (nunca "10.000 lm"); la unidad y el display humano salen del registry vía
   `spec_render`. Reuso-bajo-prueba: confirmar que el TEXT-canónico alcanza antes de considerar una columna tipada.
5. **Puente compu→prod = import JSON vía `dataio`** (preserva valor tipado + unidad + provenance; el CSV los
   aplana). El CSV se queda para inventario simple (`links`, serie, valor — PR #1071).
6. **Idioma/unidad canónica es POR SPEC, por convención de dominio.** La rosca 1/4"-20 se queda imperial/inglés;
   Full-frame en inglés; otras specs en español/métrico. El registry define la forma canónica por spec, caso por
   caso — refina el issue #888 (selectiva, no un transform ciego).
7. **Control de la web no-confiable = el gate de validación.** Nada web-sourced se persiste solo — candidato con
   source URL, confirmación humana. *Pendiente de decisión:* citar snippet exacto + gate más estricto para
   web-search que para normalizar-nuestro-HTML.

## Dos iniciativas en paralelo

### Iniciativa A — Cargar los specs (issue #1175, directo a `dev`)

- **A1** — batch-cargar la mayoría B&H-limpia con el sistema actual.
- **A2** — capa LLM offline: normalizar (eBay, misdetección, unmatched) + buscar en la web (candidatos
  validados, nunca crudo).
- **A3** — cargar el resto, meta: ~170 equipos con ficha completa.
- **A4** — normalización fotométrica de luces (ver sección dedicada).
- **A5** — guardrails de correctitud (ver sección dedicada).

### Iniciativa B — `specs_ingesta` motor único + maximizar el parser (issue #1176, PR #1177)

- **B0** ✅ — diagnóstico (completo, ver tabla arriba).
- Consolidar ~7600 líneas repartidas en un motor único CQRS-lite, matando duplicación y el `sys.path` hack.
- **Maximizar el parser** guiado por B0: mejor detección (F5), mejor genérico (F4, filtrar
  `package_weight`/`box_dimensions`), más aliases. Subsume issue #1072.

Como el parser se queda y se maximiza (el LLM lo suplementa, no lo reemplaza), consolidarlo no es trabajo tirado.

## A4 — Normalización fotométrica del output de luces

**Problema:** los números de output de luz vienen inconsistentes o faltan — la Amaran 300 dice `360 W` pero no
lúmenes → no comparable. Objetivo: output comparable a **5600K (daylight) + 3200K (tungsteno)**, con provenance,
sin inventar.

**Ya existe base (reusar, no recrear):** registry con `lumens_at_5600k`, `lumens_at_3200k`, `lux_at_1m_5600k`,
`lux_at_1m_3200k`, `consumo_w`, `beam_angle`; `derive_lumens_from_lux(lux, beam_angle)` en `commands/coerce.py`
ya deriva lúmenes (fórmula punto-a-cono); migración `a8c5d7e2f9b3` ya consolidó `lumens` legacy → `lumens_at_5600k`.

**Escalera de casos** (de más a menos confiable): medido → derivado (lux+ángulo, físicamente sólido) → derivado
cross-CCT (factor documentado, marcado estimado) → watts-only (**recomendación: "sin dato", no adivinar**) → sin
base (null).

**Provenance (modelo general, no solo lúmenes):** cada valor lleva **método** (medido/derivado/estimado) +
**fuente** (B&H/web-validado/manual) + source URL si aplica. Columna(s) en `equipo_specs`.

## A5 — Guardrails de correctitud de la data

1. **Rangos de sanidad por spec** (determinístico, Railway + offline) — rechaza/flaggea lo imposible.
2. **Merge por provenance + confianza** — un valor validado no lo pisa uno estimado/sin-validar.
3. **Detección de conflicto entre fuentes** — se surfacea, no se elige en silencio. **Ranking de autoridad**
   (sugerencia, no automático): medido (DXOMARK/LensRentals/CineD) > fabricante > retailer.
4. **Carga batch dry-run + métrica de completitud** — idempotente, previsualiza diff (patrón `dataio/cli.py`).

Orden sugerido: A5.1 → A5.4 → A5.2 → A5.3.

## Representación humana de specs — ya existe, hay que unificar

El modelo ya es el real: `{spec_key, value}` interno + `label` (nombre público, obligatorio) + `unidad` +
`services/spec_render.py` arma el display. 169 specs, todas con `label`; solo 8 numéricas sin `unidad`
(correctamente, adimensionales). **No se crea — se vuelve fuente única:** `spec_render.py` se mueve adentro del
módulo; F2 delega en él en vez de reimplementar (luces formatea `K`/`" lux"` por su cuenta hoy).

## Arquitectura del módulo — CQRS-lite + capa LLM offline

```
backend/services/specs_ingesta/
  __init__.py       # barrel: __all__ = {extract_from_html, proponer_desde_unmatched, ErrorIngesta}
  errors.py         # ErrorIngesta / HtmlNoParseable
  CLAUDE.md         # por qué existe, la frontera con specs, el split de runtime
  parse/            # DOMINIO — primitivas puras de lectura del HTML (Railway-safe)
    jsonld.py · dom.py · garbage.py · pares.py · serialize.py
    fuentes/        #   adaptadores de fuente pluggable — bh.py, ebay.py; futuros: keh/adorama/fabricante
  parsers/          # DOMINIO — verbatim ex-tools/ (los 4 parsers grandes)
    base.py (BHSpecsParser) · camaras.py · lentes.py · iluminacion.py · modificadores.py · normalizar.py · patches.py
  queries/          # LECTURA — lo que corre en Railway, nunca muta
    extraer.py · detectar.py · resolver.py · normalizar.py · resultado.py · bespoke.py · generic.py
  commands/         # ESCRITURA — el embudo que aprende (propone-aprobás)
    proponer.py
  llm/              # SUPLEMENTO OFFLINE-ONLY (jamás se importa desde el route/Railway)
    normalizador.py · buscador.py · validar.py
  cli.py            # entrada offline batch — mismo motor, mismo resultado
```

**Invariante:** `commands/` puede importar de `queries/`; `queries/` nunca de `commands/`. `parse/` y `parsers/`
no importan ni uno ni otro. `llm/` solo lo importa `cli.py`.

## Comunicación entre `specs` y `specs_ingesta` — 3 canales

- **Canal A** (lectura): `REGISTRY`/`get_categoria`, `coerce_and_serialize`, tipos. El embudo de valor
  (`mapear_valor`) se expone en el `__all__` de `specs` (aditivo). **Corrección post-F2 (la afirmación
  original "el endpoint tiene conn" era falsa, verificado leyendo `routes/equipos/fotos.py`):**
  `extract_from_html` corre HOY fuera de cualquier `with get_db()`. Cablear el embudo con `conn` real
  exige threading por 3 capas (route → dispatcher → serializer) + resolver `spec_def_id` por spec (riesgo
  de N+1 en HTMLs con 40+ specs) — es plomería nueva, no una unificación. **Diferido a F7**, que de todos
  modos necesita `conn` para la cola de propuestas (Canal C). La garantía de correctitud no se pierde: el
  embudo YA corre en `persistir_specs` al guardar — F2 solo deja la vista previa sin value_funnel, no la
  persistencia.
- **Canal B** (emisión indirecta): emite `spec_key`, se detiene ahí. El front traduce a `spec_def_id`, el humano
  confirma, recién ahí `specs` persiste. Motor sagrado intacto.
- **Canal C** (escritura): reusa `spec_propuestas_pendientes` (existe, huérfana). `specs` es dueño de la cola
  (expone `encolar_propuesta`); `specs_ingesta` es productor. Aplicar = editar el registry + re-seed.

## Fases de la Iniciativa B (strangler-fig)

- **B0** ✅ — diagnóstico read-only, completo.
- **F0** ✅ — scaffold.
- **F1** ✅ — `parse/` + `queries/resolver.py` adoptando `generic` como core. 54 páginas comparadas
  byte-a-byte; 1 mejora real encontrada (garbage-filter de `equipo` no cazaba "not specified").
- **F2** ✅ — `parse/serialize.py` delegando en `spec_render` (fuente única de display) — el embudo de
  VALOR con `conn` se difiere a F7 (ver Canal A). 164 diffs encontrados y verificados contra el registry
  (todas mejoras: unidad correcta donde antes faltaba, join `" · "` consistente, bool explícito Sí/No
  — `spec_render` colapsa `false` a `""` por diseño, pero acá es información real; corregido).
- **F3** ✅ — 4 parsers movidos verbatim a `parsers/`, ambos `sys.path` hacks muertos. AST (no grep) para
  partir archivos — un slice manual perdió `_TIPO_KEYWORDS` (constante a nivel módulo entre 2 funciones);
  un scanner de dependencias por nombre de archivo perdió referencias a nombres importados; un grep de
  imports de test se comió `_parse_temperatura` (solo lo agarró correr el test real). Las 3 lecciones →
  `CLAUDE.md` del módulo.
- **F4** ✅ — unificados los 4 builders (`resultado.py::build_result`/`generic_fallback_result`,
  `bespoke.py`, `generic.py` con el filtro de ruido) + reescrito el merge JSON-LD (`parse/secciones.py`).
  **Hallazgo mayor (reversión de diseño):** la primera versión de `secciones.py` adoptó el criterio de
  luces (dedupe — solo agregar si el label no estaba ya) por "parecer más seguro"; contra las 103 páginas
  de Luces reales perdía datos en 111 casos (JSON-LD trae el valor completo, ej. "Manual\nPush Auto\nAuto",
  el DOM uno resumido para el mismo label — el dedupe se quedaba con el resumido). Se revirtió al criterio
  de `equipo` (JSON-LD siempre primero) — más simple Y correcto, reverificado 0 diffs inesperados en
  equipo y confirmado mejora también en luces. Unificar `luces` en `build_result` corrigió 2 bugs reales
  preexistentes (`peso` buscaba la key "peso" en vez de "peso_g" → siempre None; `keywords` hardcodeado a
  `[]` en vez de `compute_keywords`) — verificado 0 spec_key perdido de verdad en las 277 páginas del
  dataset completo, todo diff es una mejora ya explicada. Wireado a los 3 archivos viejos
  (`equipo_html_extractor.py`/`luces_html_extractor.py`/`generic_html_extractor.py`, ahora shims ⏰ LEGACY
  delgados). Suite completa: 2481 passed / 20 pre-existentes no relacionados (mismo baseline que F1-F3).
- **F5** ✅ (riesgo alto) — `queries/detectar.py` (detección MAXIMIZADA: barrido sistemático de las 47
  páginas B&H reales del dataset, no solo el caso ya conocido, encontró 5 fallas — RED KOMODO Production
  Pack, 2× Aputure Quick Dome, y 2 casos NUEVOS mal-rutead os a Lentes en vez de Desconocido: "Nanlite
  Fresnel Lens for Forza" y "amaran Spotlight SE Lens Kit" — ambos accesorios ópticos de luz, no lentes
  fotográficos). Los 5 fixes se probaron contra el dataset completo antes de sumarse: 0 falsos positivos.
  RED KOMODO pasó de 70 specs de ruido (genérico) a 33 curados (parser de cámaras); los 2 lens-kit
  pasaron de 1 spec basura (parser de lentes equivocado) a 4-6 specs curados (parser de modificadores).
  **Bug adicional encontrado y arreglado en el camino** (no estaba en el alcance original, pero la
  verificación de F5 lo destapó): `BHSpecsParser.title` concatenaba CUALQUIER `<title>` del documento,
  incluyendo un `<svg><title>Accessibility</title></svg>` de un ícono — 52/277 páginas del dataset tenían
  el sufijo "Accessibility" pegado al modelo/nombre_normalizado sin espacio. Arreglado: dejar de acumular
  después del primer `</title>` que cierra. `queries/extraer.py` (entry point único, reemplaza el
  dispatcher que vivía en `equipo_html_extractor.py`) + `cli.py` (offline, mismo `queries.extraer`) +
  call-site cambiado (`routes/equipos/fotos.py` ahora importa de `services.specs_ingesta`, no del shim
  viejo). **Verificado el invariante "online == offline"**: `cli.py` y el endpoint dan resultado
  byte-idéntico sobre el mismo HTML. `specs_ingesta/__init__.py` ya no necesita el `__getattr__` lazy
  (F1) — import directo, sin ciclo. Suite completa: 2481 passed / 20 pre-existentes no relacionados.
- **F6** ✅ (riesgo medio) — borrados los 3 `*_html_extractor.py` (`equipo`/`luces`/`generic`). Los 5
  tests que importaban por nombre (`test_extractor_extras_wiring.py`, `test_generic_extractor.py`,
  `test_spec_key_normalization.py`, ~30 call-sites en total) se migraron a importar de
  `services.specs_ingesta` directo — incluida una decisión de fondo: en vez de preservar
  `_specs_dict_to_array` (un shim simplificado sin equivalente real en el módulo nuevo), esos 5 tests
  se **reescribieron para ejercitar `parse/serialize.py::specs_dict_to_array`** (la función que
  REALMENTE corre en producción), probando las mismas invariantes (shape, fallback label, cero
  descartes) contra el código real en vez de una copia de test. Un `sys.path` hack más apareció
  DENTRO de un test (`test_parser_luz_no_emite_keys_huerfanas`, apuntaba a `tools/iluminacion_parser`
  directo) — no lo había cazado ninguna fase anterior porque el grep de F1/F3 buscó en `services/`,
  no en `tests/`; re-apuntado a `services.specs_ingesta.parsers.*`. `tools/*_rebuild.sh` confirmado
  **no afectado** (ya dependían solo de `parsers/`, desde F3) — migrarlos a invocar `cli.py` queda
  diferido, no bloqueaba esta fase. De paso: corregida una referencia stale en `ruff.toml` (citaba el
  archivo borrado) y reescrita `docs/SISTEMA_SPECS.md` §1 (describía un flujo Firecrawl+LLM con
  endpoints que ya no existen — predata incluso el dispatcher viejo). Suite completa: 2481 passed / 20
  pre-existentes no relacionados.
- **F7a** ✅ — el embudo que aprende. Canal C cableado en `services/specs/` (`commands/propuestas.py`:
  `encolar_propuesta`/`aplicar_propuesta`/`descartar_propuesta`, `queries/propuestas.py`:
  `listar_propuestas_pendientes`) + `services/specs_ingesta/commands/proponer.py::proponer_desde_unmatched`
  (agrupa `unmatched` de `resolve_pairs` por label normalizado a través de varios HTMLs, propone `spec_nueva`
  cuando cruza un umbral de frecuencia — default 3 HTMLs distintos —, deduplicado contra lo ya pendiente).
  Verificado contra data real (dataset de Modificadores_Luz: "interior color" 4x/"package weight" 6x se
  proponen, "material of construction" 2x no cruza el umbral) + Postgres real (INSERT/UPDATE/CHECK
  constraint/JSONB round-trip) + 7 tests permanentes (`test_specs_ingesta_proponer_db.py`, gate opt-in
  `RESERVAS_DB_TEST=1`, mismo patrón que el resto de los `*_db.py`). **Regla dura: nunca muta el
  registry** — `aplicar_propuesta` solo cierra el ítem de la cola después de que el humano ya editó el
  registry a mano y re-sembró.
- **F7b** (pendiente) — capa LLM offline (`llm/normalizador.py`/`buscador.py`/`validar.py`), cableada
  solo en `cli.py`. Decisión de diseño abierta antes de escribir código: **cómo** invoca el LLM (API
  directa con key propia vs. un modo semi-manual que arma el contexto para una sesión de Claude Code
  interactiva) — ver discusión en la conversación con el dueño.

Cada fase: verificar (pyflakes + suite + Postgres real vía clon local) antes de commit. Supervisor antes del PR
`dev→main`.

## Fuera de scope (explícito)

- **`persistir_specs` y el registry-core de `specs`** — no se tocan. Los únicos cambios a `specs` son aditivos
  (Canal A + Canal C).
- **Auto-persistir specs "sin match"** — se muestran marcados, no se guardan en silencio.
- **LLM en Railway** — el servidor queda determinístico.

## Plan de prueba

**Iniciativa A:** agarrá 3-5 de los ~170 equipos sin specs, subí su HTML por el form, aceptá y guardá → ficha
técnica completa en catálogo y admin.

**A4:** una luz con `lux@1m+beam_angle` sin lúmenes → lúmenes calculados con badge "derivado". Amaran 300
(solo watts) → "sin dato". Una luz con lúmenes directos → badge "medido".

**A5:** HTML mal-detectado → valores imposibles no aparecen. Carga con `--dry-run` → diff sin tocar DB. Re-carga
con data peor → la spec validada no se pisa. Mismo spec de 2 fuentes → conflicto marcado.

**Iniciativa B (no-regresión):** baseline antes de F1 con 1 HTML por categoría; cada fase repite y compara.
F5: `cli.py` y el endpoint dan resultado idéntico sobre el mismo HTML (la prueba del motor único).
