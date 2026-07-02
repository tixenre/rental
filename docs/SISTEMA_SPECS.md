# Sistema de specs / categorías / datasets / autocompletar / compatibilidad

> **Manual técnico vivo.** Reúne el detalle del sistema de specs y catálogo que antes vivía
> en `MANIFIESTO.md` §6 (parte) y §7. El MANIFIESTO ahora solo orienta y apunta acá.
>
> **Fuente de verdad del schema:** [`backend/services/specs/`](../backend/services/specs/)
> (barrel público; `registry/` define `REGISTRY: Registry`, modular: una categoría por archivo en
> `registry/catalogo/`). Cada `CategoriaRegistry` solo declara `nombre` (ancla por nombre a una
> categoría real del catálogo) + `specs` — no navegación ni jerarquía visual, eso lo maneja el dueño
> a mano desde `/admin/categorias` (desenredo categorías↔specs, #1163 F6).
> Para conteos exactos de specs por categoría, mirá el registry — no los números fijos de un doc.
>
> Reemplaza al borrador histórico `docs/archive/DISEÑO_SPECS.md` (diseño original ya implementado).
>
> ⏰ **Staleness conocida (no introducida por #1163 F6, pero notada al pasar):** las §2/§5/§6
> describen un workflow de seeders **por categoría** (`backend/seeds/<categoria>.py` con
> `categorize()`, sub-cats "on-the-fly" por stock) que ya **no existe** — se eliminó en una
> "Fase C" anterior a esta iniciativa. El flujo activo de carga bulk es
> `tools/specs_import_preview.py` + `dataio.cli import` (ver `services/specs/commands/seed.py`
> docstring). Esas secciones quedan sin reescribir acá — encoladas aparte.

---

## 1. Autocompletar de specs (admin UI, por equipo)

> **Cuándo se usa:** admin agrega/edita un equipo individual y sube el HTML de su página B&H
> guardada. Equipo a equipo, on-demand, vía UI. **NO confundir** con el seed bulk inicial (ver §2).
>
> ⏰ **Reescrito 2026-07 (rediseño `specs_ingesta`, issue #1176)** — reemplaza una versión vieja de
> esta sección que describía un flujo Firecrawl+LLM (`POST /admin/equipos/autocompletar`,
> `/batch-enriquecer`, `/autocompletar-from-html`) que **ya no existe**: esos endpoints se retiraron.

- **Un solo endpoint**: `POST /admin/equipos/{id}/upload-html-source` — el admin sube un `.html`
  guardado (Cmd+S → Webpage Complete desde B&H). **Sin LLM ni scraping en vivo**: Railway no puede
  bajar la página de B&H (mismo bloqueo de bots que cualquier scraper) — solo parsea el HTML que le
  suben. Guarda el blob en R2 (`equipos/{id}/source.html`, path determinístico — re-subir
  sobreescribe) y devuelve `AutocompletarResult` con los specs extraídos; el front confirma antes de
  persistir vía `PUT /admin/equipos/{id}/specs` (la extracción NUNCA persiste sola).
- **Motor determinístico único**: `services.specs_ingesta.extract_from_html(html, categoria_hint)` —
  fuente única para este endpoint Y para el CLI offline (`services/specs_ingesta/cli.py`, misma
  compu del dueño), verificado byte-idéntico sobre el mismo HTML. Manual técnico completo (arquitectura,
  split de runtime, gotchas) → [`backend/services/specs_ingesta/CLAUDE.md`](../backend/services/specs_ingesta/CLAUDE.md);
  historia de la consolidación → [`docs/PLAN_SPECS_INGESTA.md`](PLAN_SPECS_INGESTA.md).
- **Dispatcher por categoría**: detecta Cámaras / Lentes / Adaptadores / Filtros / Modificadores /
  Iluminación por título + JSON-LD (o usa `categoria_hint` si el admin ya la eligió) y rutea al parser
  bespoke de esa categoría (labels canónicos → `spec_key` del registry, ficha limpia). Sin categoría
  reconocida → extractor genérico: extrae **todos** los pares label/value del HTML y los resuelve
  contra el índice de aliases del registry — lo que no matchea se muestra "sin template" en vez de
  descartarse en silencio.
- **Asume estructura B&H** (JSON-LD `Product.additionalProperty` + atributos `data-selenium`). Un
  HTML de otro sitio (eBay, la página del fabricante) da specs pobres o vacías con el motor
  determinístico — no hay fallback a LLM en este endpoint. Suplir esos casos (y proponer specs/
  aliases nuevos al registry) es la capa offline-only planeada en `specs_ingesta` (F7, todavía no
  construida).

---

## 2. Dataset y seed por categoría (bulk inicial)

> **Cuándo se usa:** poblar una categoría entera del catálogo de una sola pasada — typically el
> setup inicial o cuando entra un sub-segmento nuevo. **NO confundir** con autocompletar (que es por
> equipo, on-demand desde el form). Coexisten: el seed pone la base, autocompletar agrega ad-hoc o
> re-enriquece.

**Por qué un archivo por categoría (no unificado):** cada categoría tiene specs muy distintas (cámaras: `lens_mount`, `fps_max`; lentes: `distancia_focal`, `apertura`; luces: `consumo_w`, `color_modes`). Forzar un schema unificado pierde tipado fuerte. Per-categoría: cada archivo enfocado, pequeño, con su propio parser/seed/doc. Git history limpio. Escala bien (categoría nueva = archivo nuevo, no riesgo de romper las existentes).

**Por qué el naming dropea `bh_`:** B&H es la fuente primaria pero no la única. ARRI y Mole vienen de sus sitios fabricante (vía WebFetch). Futuras categorías van a usar Adorama, screenshots manuales, PDFs, etc. El dataset es **agnóstico de fuente** — la fuente queda registrada en `url_source` y `_meta.fuentes` de cada producto.

**Workflow:**

1. **Capturar HTMLs** de B&H (o site fabricante para casos como ARRI/Mole) → `$RAMBLA_HTMLS_DIR/<Categoria>/` (default `~/Desktop/Paginas/<Categoria>/`).
2. **Parsear con `tools/bh_<categoria>_parser.py`** — extrae DOM + JSON-LD structured data, salida raw a `docs/bh_<categoria>_relevamiento.json` y curada a `docs/bh_<categoria>_curado.json`.
3. **Curar manualmente** lo que el parser no puede inferir (overrides en `tools/bh_<categoria>_patches.py` — usado para sitios fabricante o HTMLs incompletos).
4. **Normalizar** marcas/modelos/IDs con `tools/bh_<categoria>_normalizar.py` (canonicaliza brand, modelo limpio, IDs estables).
5. **Importar** vía `backend/seeds/<categoria>.py` — idempotente, popula `spec_definitions` + `categoria_spec_templates` + sub-categorías + `equipos` + `equipo_specs` en una pasada.

**Convenciones del dataset curado** (los 3 niveles por producto):

- **`specs`**: campos canónicos para filtros/comparación. Todos numéricos o enum estrictos. Ej: `consumo_w: 410`, `temperatura_k: {min: 1800, max: 20000}`, `color_modes: ["RGB","Daylight","Tungsten"]`. Unidades en field name (`_w`, `_g`, `_k`).
- **`extras`**: ficha técnica detallada. Strings descriptivos + algunos numéricos estructurados (ej. `dimensiones_cm: {largo_cm, ancho_cm, alto_cm}`, `noise_db: {silent, medium, high}`).
- **`ficha`**: raw del scrape (todas las secciones B&H tal cual). Para renderizar ficha técnica completa sin perder data.

**Convenciones cross-cutting:**

- Métrico como base de DB (g, cm, m, K, W). UI computa imperial desde el base.
- Excepción: pins/studs/accessory diameter en imperial-native (5/8″, 6.6″) — estándar industria cine.
- Marcas canónicas con casing fijo (`ARRI`, `Amaran`, `Mole-Richardson`, `Nanlite`, etc.) — definido en `bh_<categoria>_normalizar.py::BRAND_CANON`.
- IDs estables `marca_modelo` snake_case (ej. `aputure_nova_ii_2x1`).
- Ausencia = `null` o campo ausente. NO usar strings `"N/A"`, `"None"`, `"—"`.

**Estado del dataset por categoría** (conteos exactos de equipos: ver la DB / back-office, no este doc):

| Categoría | Estado | Doc |
|---|---|---|
| Iluminación | Listo — seed funcional, HTML upload wireado al admin | [`docs/DATASET_ILUMINACION.md`](DATASET_ILUMINACION.md) |
| Cámaras | Listo — seed funcional. **HTML upload UI aún apunta solo a iluminacion_html_extractor** — falta dispatcher por categoría | [`docs/DATASET_CAMARAS.md`](DATASET_CAMARAS.md) |
| Lentes | Listo — seed funcional. Taxonomía por TIPO (Zoom/Fijo/Vintage/Especiales) + monturas on-the-fly. HTML upload pendiente del dispatcher | [`docs/DATASET_LENTES.md`](DATASET_LENTES.md) |
| Adaptadores | Listo — seed funcional. Categoría raíz independiente; sub-cats por montura (Montura E/RF/EF) on-the-fly | [`docs/DATASET_LENTES.md`](DATASET_LENTES.md) |
| Filtros | Listo — seed funcional. Categoría raíz independiente; sub-cats por diámetro (82mm/77mm) on-the-fly | [`docs/DATASET_LENTES.md`](DATASET_LENTES.md) |
| Modificadores | Listo — seed funcional. Categoría raíz; 4 sub-cats fijas (Softbox/Fresnel/Spotlight/Difusión-Frame). Se acoplan a una luz vía `montura_luz` | [`docs/DATASET_MODIFICADORES.md`](DATASET_MODIFICADORES.md) |
| (otras) | Pendiente | — |

**Por qué el seed coexiste con `categoria_spec_templates`:** ese table sigue siendo necesario porque define UI metadata (qué specs van en card/filtros/nombre, prioridad de display) — eso no se deriva del dato del equipo. Lo que el seed automatiza es que el admin no la pueble a mano: el script lo hace en una pasada idempotente.

**Back-office después del seed:** una vez corrido, el dataset JSON queda como bootstrap/archivo (no se consulta en runtime). La DB es la fuente de verdad. Todo lo importado se ve y se edita desde el back-office existente:

- **Equipos** (`/admin/equipos`) — lista admin, form `EquipoFormDialogV2`. Edita precio_jornada, foto_url, marca, modelo, nombre_publico, etc.
- **Specs values por equipo** — en la sección Specs del form admin del equipo.
- **Spec definitions globales** (`/admin/equipos/specs`) — catálogo de specs (consumo_w, cri, etc.). Edita label, enum_options, ayuda.
- **Categorías** — admin las gestiona en la UI existente de categorías.

**Quién edita qué (operativa diaria):**

| Acción | Sin Claude | Con Claude |
|---|---|---|
| Agregar equipo nuevo (cualquier categoría con parser bespoke) — categoría existente | Sí — admin UI: guardar el HTML de B&H (Cmd+S) y subirlo (§1); calidad seed automática | — |
| Agregar equipo de categoría sin parser bespoke, o de un sitio no-B&H | Sí — admin UI (extractor genérico, calidad menor: labels "sin template" a confirmar a mano) | Sí — CLI offline + capa LLM (F7, no construida todavía) para mejor calidad |
| Editar precio / foto / nombre / spec value | Sí — admin UI | — |
| Agregar spec key nueva al catálogo global | Sí — `/admin/equipos/specs` | — |
| Importar bulk de una categoría NUEVA (ej. cámaras) — primera vez | — | Sí — curar HTMLs + parser específico + seed |
| Refactor del schema (ej. partir `peso` en sub-campos) | — | Sí — plan + migration |

**Limitaciones (estado actual, post F5 de `specs_ingesta` — ver §1):**
- El dispatcher por categoría ya existe y cubre Cámaras/Lentes/Adaptadores/Filtros/Modificadores/
  Iluminación con parser bespoke; el resto cae al extractor genérico (sin descartes silenciosos, pero
  con menos curación).
- El parser asume estructura B&H (JSON-LD + `data-selenium`). Un HTML de otro sitio (eBay, la página
  del fabricante) da specs pobres o vacías — no hay fallback a LLM en este endpoint (a diferencia de
  una versión anterior de este flujo). Suplirlo es la capa offline-only planeada (F7, no construida).
- No hay scraping en vivo por URL — el admin siempre sube el `.html` guardado a mano.

El JSON del dataset NO se edita post-seed (es dev artifact). Para cambios puntuales: admin UI. Para reseed masivo (raro): editar JSON + re-correr seed (idempotente, no pisa campos manuales como `precio_jornada`).

**El JSON queda "congelado" después del seed.** Si querés un export del estado actual de la DB → JSON otra vez (por backup o re-importar a otro ambiente), se arma un script `dump_<categoria>.py` cuando haga falta. Por defecto no es necesario.

---

## 3. Compatibilidades cross-categoría

Los equipos se relacionan entre sí por **specs compartidos** — el motor de compatibilidad (`backend/routes/specs/compatibilidad.py`) decide si dos equipos son compatibles, parciales o incompatibles según sus valores en specs marcadas con `es_compatibilidad=TRUE`. El motor no se movió al paquete `services/specs/` (#1163): es lógica de matching, no CRUD, y sigue leyendo specs ya persistidas.

**Specs compartidos** (declarados en el **registry de specs** — [`backend/services/specs/registry/shared/`](../backend/services/specs/registry/shared/); el `rol_compatibilidad` de Cámaras/Lentes vive en [`backend/services/specs/registry/catalogo/`](../backend/services/specs/registry/catalogo/)):

| Spec | Modo | Aplica a | Resuelve |
|---|---|---|---|
| `lens_mount` | exacta | Cámaras, Lentes, Adaptadores | "¿La rosca del lente entra en el body / adaptador?" |
| `diametro_filtro` | exacta | Lentes, Filtros | "¿Este filtro 82mm rosquea en este lente?" |
| `formato` | jerarquia | Cámaras (rol contenido), Lentes (rol contenedor) | "¿Cubre el lente todo el sensor o queda crop / viñetea?" |
| `montura_luz` | exacta | Iluminación, Modificadores | "¿Este modificador acopla en esta luz?" |

**Cómo se conecta** (operativa):

1. Las specs compartidas declaran `es_compatibilidad=True` + `compatibilidad_modo` (y `enum_options` ordenadas si son jerárquicas) en el **registry** (`backend/services/specs/registry/shared/`). `services/specs/commands/seed.py` las **upserta** en `spec_definitions` con esas columnas al sembrar el registry.
2. Lentes y Cámaras declaran además `rol_compatibilidad` (`contenedor` o `contenido`) en `backend/services/specs/registry/catalogo/{lentes,camaras}.py` → el mismo seeder lo persiste, para que el motor sepa quién proyecta y quién recibe.
3. El endpoint `GET /admin/equipos/{id}/compatibles` cruza specs de ambos equipos y devuelve overall ∈ `{compatible, compatible_con_crop, parcial, incompatible, requiere_adaptador, sin_relacion}` + razones por spec.

**Casos típicos resueltos automáticamente** (sin tocar el motor):

- Sony FX3 (E) + Sony GM 24-70 (E) → `compatible` ✓ (lens_mount match exacto)
- Sony FX3 (E) + Sigma 50 Art (EF) → `sin_relacion` directo, pero como ambos tienen lens_mount, queda `incompatible` por mismatch — UI puede sugerir adaptadores con `lens_mount=E, lens_mount_out=EF` (Sigma MC-11).
- Sony 24-70 GM (Full-frame) + Sony a7V (Full-frame) → `compatible` (formato match exacto en jerarquía).
- Sony 24-70 GM (Full-frame) + cámara APS-C → `compatible_con_crop` (lente proyecta más grande, sensor usa crop central).
- Sigma 18-35 Art (APS-C) + Sony a7V (Full-frame) → `parcial` con `partial_vignette` (lente APS-C no cubre sensor FF).
- Tiffen 82mm Variable ND + Sony GM 24-70 (diametro_filtro=82) → `compatible` (diametro_filtro match).
- Tiffen 82mm + Sigma 35 Art (diametro_filtro=67) → `incompatible` (diámetros distintos).

**Override manual** (`equipo_compatibilidad` table): para casos que el auto no maneja bien — ej. "este combo viñetea solo a f/1.4 abierto" → marca como `parcial` con nota custom.

**Lo que NO está auto hoy** (pendiente):

- Sugerencia automática de "requiere_adaptador" cuando A.lens_mount ≠ B.lens_mount pero existe un adaptador que conecta los dos. Hoy requiere `equipo_compatibilidad` manual con `adaptador_id`. El skill IA `gear-compatibility` (propuestas pendientes) lo cubre parcialmente.
- UI del catálogo público — las compatibilidades se ven solo en admin (`/admin/gear-compatibility` + tab por equipo).

---

## 4. Display templates por spec (placeholders del nombre público)

> **Cuándo aplica:** cuando un spec se usa en una plantilla de nombre público vía `{spec:Label}`. El
> sistema mapea el label → spec_key → display template para mostrar el valor con formato bonito en
> vez del valor crudo.

**Dos variantes por spec:**

- **`short`** (default): para nombres públicos, conciso, sin contexto extra.
- **`long`**: para ficha técnica / comparador, con contexto explícito.

**Sintaxis de placeholder:**

```
{spec:Label}        → variante short (default — nombres concisos)
{spec:Label:long}   → variante long  (con contexto, para ficha)
```

**Ejemplo:**

```
DB value:           lumens_at_5600k = 19389 (int)

{spec:Lúmenes (5600K)}       → "19389 lumen"           (short)
{spec:Lúmenes (5600K):long}  → "19389 lm a 5600K"      (long)
```

**Dónde vive:** `backend/services/nombre_builder.py`:
- `SPEC_DISPLAY_TEMPLATES`: dict `spec_key → str | {"short": ..., "long": ...}` o handler
- `LABEL_TO_SPEC_KEY`: dict label normalizado → spec_key
- `render_spec_value(spec_key, value, variant="short")` → string formateado

**Formato de cada template:**

```python
# a) String con {value} → interpolación directa
"consumo_w":  "{value}W"               # 1000 → "1000W"

# b) Dict short/long → variantes distintas
"lumens_at_5600k": {
    "short": "{value} lumen",            # 19389 → "19389 lumen"
    "long":  "{value} lm a 5600K",       #       → "19389 lm a 5600K"
}

# c) String literal (sin {value}) → label-when-true para booleans
"gps":              "GPS"                # true → "GPS"; false → ""
"netflix_approved": {"short": "Netflix", "long": "Netflix approved"}

# d) Handler especial (string que empieza con "_") → función dedicada
"peso_g":           "_smart_kg"          # 390 → "390g"; 3300 → "3.3 kg"
"temperatura_k":    "_rango_k"           # {min:1800,max:20000} → "1800-20000K"
"iso_nativo":       "_iso_short"         # {min:80,max:102400} → "ISO 80-102400"
```

**Templates implementados:**

| Spec | short | long |
|---|---|---|
| `consumo_w` | `"1000W"` | idem |
| `lumens_at_5600k` | `"19389 lumen"` | `"19389 lm a 5600K"` |
| `lumens_at_3200k` | `"17000 lumen (tungsten)"` | `"17000 lm a 3200K"` |
| `lux_at_1m_5600k` | `"11600 lux"` | `"11600 lux a 1m (5600K)"` |
| `cri` / `tlci` / `r9` | `"CRI 95"` / `"TLCI 98"` / `"R9 90"` | idem |
| `temperatura_k` | `"1800-20000K"` / `"3200K"` si fixed | idem |
| `peso_g` | `"390g"` / `"3.3 kg"` smart | idem |
| `dimming` (bool) | `"Dimmer"` o `""` | idem |
| `megapixels` | `"33.0MP"` | idem |
| `fps_max` | `"120fps"` | idem |
| `continuous_shooting_fps` | `"30fps"` | `"30fps (ráfaga)"` |
| `iso_nativo` | `"ISO 80-102400"` | idem |
| `iso_extendido` | `"ISO 80-409600 (ext)"` | idem |
| `rango_dinamico_stops` | `"15 stops"` | idem |
| `max_aperture` | `"f/2.5"` | idem |
| `sensor_crop` | `"1.5x"` | idem |
| `estabilizacion` (bool) | `"IBIS"` o `""` | idem |
| `autofocus` (bool) | `"AF"` o `""` | idem |
| `fast_slow_motion` (bool) | `"S&Q"` | `"Slow/Fast motion"` |
| `lens_communication` (bool) | `"AF lente"` | `"Comunicación electrónica lente"` |
| `gps` (bool) | `"GPS"` o `""` | idem |
| `ip_streaming` (bool) | `"Streaming IP"` | `"IP Streaming"` |
| `netflix_approved` (bool) | `"Netflix"` | `"Netflix approved"` |

**Sin template (devuelven valor crudo):** enums simples (`tipo`, `lens_mount`, `formato`, `resolucion_max`, `montaje`), multi-enums (`color_modes`, `control_inalambrico`, `alimentacion` → join con `", "`), strings libres (`codecs`).

**Convenciones de naming:**
- Nombres cortos y claros (la ficha técnica completa muestra el detalle)
- Sin `@` — usar `"a"` en español (`"a 5600K"` no `"@ 5600K"`)
- Unidades en palabra cuando es más legible (`"lumen"` vs `"lm"` en short)
- Sin contexto redundante en short — la temp ya está implícita en el contexto del producto
- Boolean true → label corto descriptivo (`"GPS"`, `"IBIS"`, `"AF"`, `"Netflix"`)
- Boolean false → string vacío (se elimina del nombre)
- **Spec no aplica al producto** (ej. `lens_mount` en GoPro/Insta360) → guardar `null` en `equipo_specs`. El placeholder `{spec:Lens mount}` se omite automáticamente del nombre **junto con sus separadores** (sin double-spaces ni guiones sueltos). Mismo template funciona para productos con y sin la spec.

---

## 5. Workflow al agregar una sub-categoría nueva

La taxonomía de sub-categorías por categoría raíz vive en `backend/seeds/<categoria>.py`. **Es código, no JSON** — porque tiene lógica de asignación (`categorize()`) además de la estructura.

**Para agregar una sub-categoría hoja** (ej. una nueva montura bajo Cámaras/Video):

1. Editar la lista `SUBCATEGORIAS_NIVEL2_VIDEO` en `backend/seeds/camaras.py` → agregar tupla `("Montura X", prioridad)`.
2. Si requiere lógica nueva de asignación: extender `categorize()` con el caso.
3. Re-correr el seed: `python -m backend.seeds.camaras`.

El seed es idempotente:
- Sub-categorías que ya existían se respetan (ON CONFLICT DO NOTHING)
- Sub-categorías nuevas se crean
- Equipos se RE-asignan según las reglas actuales de `categorize()` (ON CONFLICT DO NOTHING en `equipo_categorias`)

**Para agregar un nivel de profundidad** (ej. sub-sub-categoría):
- Agregar `SUBCATEGORIAS_NIVEL3` con su parent
- Extender `seed_<categoria>()` con un loop adicional usando `_upsert_subcat(name, prio, parent_nivel2)`
- El schema soporta árbol arbitrario via `categorias.parent_id`

**Para crear sub-categorías ad-hoc desde la UI admin** (sin tocar código):
- Sí, posible vía `/admin/categorias`
- Crear ahí → quedan en DB, pero NO en el seed
- Si se borran y se re-corre seed, el seed las recrea según su definición
- Si querés que sean permanentes: agregar al seed después

**Auto-creación on-the-fly**: si `categorize()` devuelve un nombre de sub-categoría que no está pre-definida (ej. una montura nueva), el seed la crea con `prio=99` automáticamente como child del parent intermedio. Evita que productos queden huérfanos.

---

## 6. Workflow al agregar un spec nuevo

Cuando agregamos un spec_key nuevo a una categoría (en seed `backend/seeds/<categoria>.py`):

1. **Definir en `spec_definitions`** vía el seed: `(spec_key, label, tipo, unidad, enum_options, ayuda)`.
2. **Decidir si necesita display template**: si es para placeholder en nombre público, agregar entrada a `SPEC_DISPLAY_TEMPLATES` en `backend/services/nombre_builder.py`. Default: si va a aparecer en nombres, sí necesita template; si solo en ficha técnica, opcional (la web puede formatear con su propia lógica).
3. **Agregar el label normalizado** en `LABEL_TO_SPEC_KEY` para que `{spec:Label}` resuelva al spec_key correcto (sin tildes, lowercase).
4. **Elegir variantes** short / long según uso:
   - Solo nombres → string plano
   - Nombre + ficha distintas → dict `{short, long}`
   - Boolean → string literal (label-when-true)
   - Numérico con conversión → handler especial

**Futuro opcional:** mover `display_template_short` y `display_template_long` a columnas de `spec_definitions` para edición admin via UI. El patrón actual con dicts en código alcanza para todas las categorías que armemos.

---

## 7. Sistema de specs consolidado (fuente de verdad)

> **Fecha**: 2026-05-17. Reemplaza el borrador histórico `docs/archive/DISEÑO_SPECS.md`.
> Cuando hay duda, esto manda.

### Single source of truth: `backend/services/specs/`

Pydantic v2 registry. Todas las cats y specs están declaradas en un solo lugar
(modular: una categoría por archivo en `backend/services/specs/registry/catalogo/`).
Cada `CategoriaRegistry` solo declara `nombre` (ancla a una categoría real del
catálogo) + `specs` — no navegación ni jerarquía visual (desenredo
categorías↔specs, #1163 F6: `sub_categorias`/`grupo_visual`/`prioridad` a nivel
categoría se sacaron por muertos — el seeder solo los pasaba a una función que
los ignoraba). Cualquier consumer (seed, parsers, API, UI metadata) importa
del barrel:

```python
from services.specs import REGISTRY, get_categoria, get_spec, validate_dataset
```

**Cambios estructurales (PR feat/specs-registry, histórico)**:
- Borrados: `seeds/spec_templates.py::TEMPLATES`, `seeds/<cat>.py::SPECS_X` (eran duplicados — generaban drift)
- DB: `spec_definitions` ahora tiene UNIQUE `(categoria_raiz_id, spec_key)` (antes era UNIQUE global → colisión "tipo" cross-cat)
- Cada cat tiene su `<cat>_subtipo` propio (camera_subtipo, iluminacion_subtipo, adaptador_subtipo, filtro_subtipo)
- Datasets validan contra el registry en parse-time (`services.specs.queries.validation.validate_dataset` — sin caller en vivo hoy, ver `services/specs/CLAUDE.md`)

**Rediseño a CQRS-lite (#1163, F0-F6)**: el paquete se reorganizó espejando
`services/categorias/` (`registry/` declarativo, `commands/` = única puerta de
escritura, `queries/` nunca mutan) y se agregó el **embudo de alias de valor**
(`normalize/value_funnel.py::mapear_valor` — normaliza 'FF'→'Full-frame' al
persistir, gratis para compat y búsqueda) + **búsqueda derivada de specs en
vivo** (`queries/search_source.py`). Detalle → [`docs/PLAN_SPECS_REDISENO.md`](PLAN_SPECS_REDISENO.md)
y [`services/specs/CLAUDE.md`](../backend/services/specs/CLAUDE.md).

### El stack en una imagen

```
backend/services/specs/__init__.py  (barrel: REGISTRY, seed_all_categorias, persistir_specs, ...)
    │
    ├──► services/specs/commands/seed.py  → DB (spec_definitions + categoria_spec_templates)
    │                                        ↑ idempotente, walks REGISTRY, corre en cada boot
    │
    ├──► services/specs/commands/persist.py  → equipo_specs (choke-point único de escritura,
    │                                            pasa por el embudo de alias de valor)
    │
    └──► services/specs/queries/validation.py  → valida docs/<cat>.json en parse (sin caller en vivo)

HTMLs B&H ($RAMBLA_HTMLS_DIR/<categoría>/, default ~/Desktop/Paginas/<categoría>/)
    │ tools/<categoría>_parser.py  (emite keys del registry)
    ▼
docs/<categoría>.json  (dataset canónico, validado contra registry)
    │
    ▼
tools/specs_import_preview.py + dataio.cli import  (reemplaza a los seeders
    │                                                 por-categoría, eliminados en Fase C)
    ▼
DB Postgres
```

### Specs por categoría (6 activas)

> Conteos de specs: snapshot orientativo. La verdad está en `backend/services/specs/registry/catalogo/<cat>.py`.

| Categoría | # specs | Subtipo canónico | Specs core |
|---|---|---|---|
| Cámaras | 22 | `camera_subtipo` | lens_mount, formato, resolucion_max, fps_max, codecs, iso_*, peso_g |
| Lentes | 15 | — | lens_mount, distancia_focal (rango), apertura (rango), formato, linea, diametro_filtro |
| Adaptadores | 7 | `adaptador_subtipo` | lens_mount, lens_mount_out, electronica, magnificacion |
| Filtros | 6 | `filtro_subtipo` | diametro_filtro, densidad, material, grade |
| Iluminación | 17 | `iluminacion_subtipo` | consumo_w, color_modes (multi_enum), temperatura_k (rango), cri, alimentacion (multi_enum) |
| Modificadores | 12 | `modificador_subtipo` | forma, diametro_cm, dimensions_mm, montura_luz, light_loss_stops, beam_angle, peso_g |

**Specs compartidas semánticamente** (mismo `spec_key` declarado en varias cats con metadata idéntica):
- `lens_mount` — Cámaras ↔ Lentes ↔ Adaptadores (match exacto)
- `formato` — Cámaras ↔ Lentes (jerárquico: FF > Super 35 > APS-C > MFT)
- `diametro_filtro` — Lentes ↔ Filtros (match exacto)
- `montura_luz` — Iluminación ↔ Modificadores (match exacto)
- `peso_g` — todas

El motor de compat matchea por **string-equality del spec_key + value**. La composite key en DB las separa físicamente (cada cat es dueña de su fila) pero conceptualmente representan la misma propiedad. Esto elimina la colisión que tenía la arquitectura vieja sin sacrificar el matching cross-categoría.

**Single source de enum jerárquico** (`specs.FORMATO_ENUM`):
```
1" → MFT → M4/3 → APS-C → Super 35 → Full-frame → Medium Format
```

**Roles de compat (jerarquía)**:
- Lentes.formato = `contenedor` (proyecta sobre el sensor)
- Cámaras.formato = `contenido` (recibe el círculo de imagen)

**Convenciones de naming**:
- `peso_g`: int gramos
- Rangos (`distancia_focal`, `apertura`, `angulo_vision`, `iso_nativo`, `temperatura_k`): listas — `[v]` fijo, `[min, max]` variable
- `multi_enum`: JSON array. Usados en `color_modes`, `control_inalambrico`, `alimentacion`
- IDs estables del dataset: `marca_modelo_apertura[_linea]`

### Sub-categorías por raíz — 100% manual, desenredada de specs (#1163 F6)

El árbol de sub-categorías bajo cada raíz (Foto/Video, Zoom/Fijo, Softbox/Fresnel,
etc.) ya **no se declara en el registry de specs** — el registry de una categoría
(`CategoriaRegistry`) solo tiene `nombre` + `specs`. El árbol completo (incluida
la raíz misma) lo maneja el dueño **100% a mano** desde `/admin/categorias`
(motor único `services/categorias/`, decisión 2026-05-30). El seeder de specs
(`services/specs/commands/seed.py`) solo **resuelve por nombre** una raíz ya
existente para colgarle `spec_definitions` — nunca crea ni edita la categoría
ni sus hijas; si el dueño la borró, esa categoría del registry se saltea en
silencio (`categoria_ausente` en el resultado del seed).

En el catálogo público (`CategorySidebar.tsx`), Lentes + Adaptadores + Filtros
se agrupan visualmente bajo **"Óptica"** vía `categorias.grupo_visual` (columna
real de la tabla `categorias`, editable desde el admin — no relacionada con el
campo homónimo que el registry de specs llegó a tener y que #1163 F6 sacó por
muerto).

### Keywords automáticas

`nombre_builder.compute_keywords(specs)` genera 6–12 keywords canónicas por equipo desde `SPEC_KEYWORDS_TEMPLATES`. Reemplaza al LLM-output legacy (que daba strings raros). Ejemplos:

- Sony FX3 → `E, E-mount, montura E, Full-frame, FF, full frame, 35mm, 4K, UHD, video 4K, Cinema Camera`
- Tiffen 82mm Variable ND → `Filtro variable, 82mm, filter 82, ND 2 to 8-Stop`

### Merge dataset ↔ DB existente (preservar pedidos)

`docs/equipos_match.json` mapea `dataset_id → equipo.id` con action:
- `update`: el seed pisa specs/keywords/categorías sobre el equipo existente
- `create`: insert nuevo (el equipo no existe)
- `skip`: no tocar (ej. kit Zeiss, equipos no aplicables)
- `override_marca/override_modelo`: corregir DB mal-etiquetada (5 casos detectados)

Esto garantiza **0 duplicados, 0 pedidos huérfanos**.

### Flow operativo

```bash
# 1. Bulk inicial / re-importar dataset entero
bash tools/<categoría>_rebuild.sh                  # parser → docs/<cat>.json
python -m tools.equipos_match_preview              # opcional: fuzzy match contra DB
# editar docs/equipos_match.json (manual)
python -m tools.specs_reset --dry-run              # ver qué se borraría
python -m tools.specs_reset --apply                # limpia specs/keywords viejas
python -m backend.seeds.{camaras,lentes,adaptadores,filtros,iluminacion}

# 2. Agregar 1 equipo nuevo a categoría existente (cuando esté wireado)
# Admin sube HTML B&H → endpoint usa el mismo parser → inserta canónico
```

### Agregar specs a una categoría (las sub-cats se crean a mano en `/admin/categorias`, no acá)

1. **Editar** la categoría en `backend/services/specs/registry/catalogo/<cat>.py` (la registra `backend/services/specs/registry/__init__.py`)
2. **Validar** localmente: `python -m pytest backend/tests/test_specs_registry.py`
3. **Reseed**: el lifecycle de la app corre `seed_all_categorias()` en cada boot (`main.py::_seed_registry`) — no hace falta un comando manual.

Si una spec_key debe ser compartida con otra cat (compat matching): declararla idénticamente en ambas (mismo `tipo`, mismas `enum_options`, misma `unidad`). El test `test_shared_keys_consistentes_entre_cats` lo enforcea.

### Cuando se rompa o falte algo

| Síntoma | Dónde mirar |
|---|---|
| Specs no aparecen como compatibilidad | `SpecDef.es_compatibilidad` en el registry; reseed |
| Match jerárquico no funciona | `SpecDef.compatibilidad_modo` + `rol_compatibilidad` en el registry |
| Dataset rompe seed con error de validación | Output de `services.specs.queries.validation.validate_dataset()` — el dataset desalineó del registry |
| Equipos duplicados al re-seed | `docs/equipos_match.json` debe tener entry con `action: update` |
| Keywords salen mal | `SPEC_KEYWORDS_TEMPLATES` en `nombre_builder.py` |
| Falta una sub-categoría en el sidebar | El árbol es 100% manual (`/admin/categorias`) desde #1163 F6 — no hay creación on-the-fly por specs |
| Categoría del registry no siembra nada (`categoria_ausente`) | El seeder solo RESUELVE por nombre — la raíz no existe (o el dueño la borró/renombró) en `categorias` |
| Spec "tipo" cruza enums entre cats | No debería ocurrir: cada cat tiene `<cat>_subtipo`. Si pasa, el registry tiene drift |
