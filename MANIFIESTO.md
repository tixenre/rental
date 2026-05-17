# Manifiesto — Rambla Rental

> **Memoria para Claude.** Este archivo es el prompt que se carga al inicio de
> cualquier sesión con Claude. Acá vive lo que necesita saber para no
> arrancar desde cero: qué es el proyecto, cómo trabajamos, decisiones tomadas,
> qué está pendiente.
>
> Si algo cambia (workflow, decisión, herramienta), se actualiza acá.
> El [`README.md`](README.md) cubre la cara de GitHub (setup, stack, links). Este archivo cubre el contexto.

---

## 1. Qué es el proyecto

**Rambla Rental** — plataforma de alquiler de equipos audiovisuales.

3 superficies:

- **Catálogo público** (`/`) — clientes ven equipos, arman cotización.
- **Portal cliente** (`/cliente/*`) — login, ver mis pedidos, perfil.
- **Back-office admin** (`/admin/*`) — gestión total: equipos, pedidos, clientes, mantenimiento, dashboard de uso, etc.

Un único dueño/operador maneja el back-office. Inventario chico-mediano (cientos de equipos), volumen de alquileres mensual moderado.

---

## 2. Stack

| Capa | Tech |
|---|---|
| Frontend | React 19 + Vite + TanStack Router (file-based) + TanStack Query + Tailwind v4 + shadcn/Radix UI |
| Backend | FastAPI + psycopg2 + PostgreSQL (pool de conexiones) |
| Auth | Google OAuth via Supabase Auth (admin + portal cliente) |
| Storage | Cloudflare R2 (S3-compatible) para fotos |
| Drag-and-drop | `@dnd-kit/*` |
| Form state | `react-hook-form` + `zod` para validación |
| Deploy | Railway (backend + frontend en un mismo servicio Docker) |

Detalles de setup en [`README.md`](README.md). Detalles de Railway en [`docs/DEPLOY_RAILWAY.md`](docs/DEPLOY_RAILWAY.md).

---

## 3. Cómo trabajamos

### Workflow

**Modo default: desarrollo local-first sobre `main`.**

Claude trabaja directamente en `/Users/tincho/rental` (sin worktree, sin branch intermedia), commiteando atómico a `main` local. El dev server refleja los cambios al instante en localhost. Cada tanto, cuando hay un chunk listo, se pushea `main` a GitHub.

```
Edit → commit atómico en main local → ver en localhost → (N veces) → push main a GitHub
```

**La memoria del proyecto vive en GitHub vía:**

- **Commit history**: cada commit es Conventional Commits en español (`fix(scope):`, `feat(scope):`). `git log --grep="^fix"` ya es el registro de bugs; `git log --grep="^feat"` el de features. GitHub lo renderiza buscable y permanente.
- **GitHub Issues**: para trabajo planeado o bugs con discusión / contexto largo. No es obligatorio para cada commit — solo cuando hace falta tracking explícito.

**Cuándo abrir PR en vez de pushear directo a `main`:**

- Cambio sensible que quiere review humana antes de mergear.
- Iniciativa grande con múltiples commits que quiero revisar como bloque.
- Cambio arquitectónico / decisión de diseño que deja registro discutible.

Para esos casos, sí: branch dedicada + PR contra `main` (workflow histórico, descrito abajo).

Excepciones al local-first:

- **Decisiones de arquitectura / diseño** → docs en `docs/` (ej. `DISEÑO_SPECS.md`).
- **Ideas tempranas sin compromiso** → issue con `priority:low` (o conversación con el dueño antes de abrirlo).

### Planes multi-fase → issues

Cuando Claude diseña un plan que se ejecuta en varias fases (refactor grande, feature con backend + frontend, migración por pasos), **cada fase es un GitHub issue independiente**. El plan no vive en un archivo markdown ni en la memoria de una sesión.

Por qué:

- **Sesión-agnóstico**: cualquier sesión nueva puede tomar una fase pendiente y avanzarla sin contexto perdido.
- **Tracking real**: el estado del trabajo se ve en `gh issue list`, no releyendo conversaciones viejas.
- **Reordenar prioridades**: si una fase queda obsoleta o cambia de prioridad, se edita / cierra el issue, no se reescribe el plan entero.

Cada issue describe la fase con: contexto, scope (checklist accionable), cómo (pasos concretos), verificación, y por qué de los labels.

### Una iniciativa = una rama = una PR

**Default**: el trabajo de una iniciativa entera (aunque tenga N fases / N issues) va en **una sola rama con N commits adentro**, y se mergea como **una sola PR** que cierra todos los issues con varios `Closes #N`.

Por qué: minimiza el costo de review + merge + deploy. Una iniciativa = 1 review, 1 merge, 1 deploy — no N.

Cada commit dentro de la rama es atómico y revertible. La PR los publica en bloque.

**Excepción explícita**: para algo chico y aislado (typo, una decisión de label puntual, un bug fix de 5 líneas que no está atado a una iniciativa más grande), pedir abrir una **PR separada** de forma explícita. Sin esa indicación, default es agregar al branch en curso.

### Branches

- `main` — siempre estable, deployable.
- `claude/<descripcion>` — una rama por **iniciativa** (no por fase / no por commit). Múltiples commits dentro.
- `bugs` / `features` — branches long-lived legacy del workflow viejo. **NO usar para nuevo trabajo**; quedaron porque hay docs que las mencionan.

Después de mergear: **borrar la branch local** (`git branch -d`) **y remota** (`git push origin --delete`). Sin colgadas.

### Commits

Estilo `tipo(scope): descripción en español, lowercase, sin punto final`.

Tipos: `feat`, `fix`, `refactor`, `chore`, `docs`, `perf`, `test`.

Body explica el **por qué**, no el **qué**. Bullets si hay varios efectos.

### PRs

- Título: igual al commit principal.
- Body: 3 secciones — Summary / Cambios / Test plan.
- Linkear el issue con `Closes #N`.
- CI debe estar verde antes de mergear (TypeScript typecheck, Python tests, Build frontend, mobile-smoke).
- **Auto-merge habilitado por default**: cada PR que Claude crea queda con auto-merge enabled. Cuando CI verde → GitHub mergea sola, borra la branch, listo. El dueño no tiene que clickear "Merge" en cada PR.
  - **Gate humano**: si una PR no debería mergearse sin revisión visual (cambio sensible, decisión arquitectónica, UI grande), dejarla como **draft**. GitHub no auto-mergea drafts.
  - **Opt-out por PR**: pedir explícitamente "no auto-merge esta" — Claude la deja sin habilitar.
- Conflicts con main: rebase / merge desde el branch (no force-push a main).

Detalle completo del flow en [`docs/PROTOCOLO.md`](docs/PROTOCOLO.md).

### Issues — labels

**Cada issue se etiqueta en 3 dimensiones** + opcionales cross-cutting. Sin las 3 dimensiones la issue queda incompleta y no se prioriza.

1. **Tipo** (1, obligatoria): `bug` / `feature` / `design` / `refactor` / `documentation` / `security`.
2. **Prioridad** (1, obligatoria): `priority:critical` / `priority:high` / `priority:medium` / `priority:low`.
3. **Complejidad** (1, obligatoria): `complexity:trivial` / `complexity:small` / `complexity:medium` / `complexity:large` / `complexity:epic`.

**Cross-cutting** (0+, opcionales): `mobile`, `dx`, `infrastructure`, `performance`, `launch-blocker`, `backend`, `admin`.

Regla del `mobile`: aplicar **además** del tipo, no en lugar de. Aplica si la issue afecta rutas cliente o admin prioritario (`/admin/pedidos`, `/admin/dashboard`). Resto del admin = desktop-first.

Convención completa + cómo elegir issues por capacidad de la sesión en [`docs/ISSUE_LABELS.md`](docs/ISSUE_LABELS.md).

**Al crear un issue nuevo**: aplicar las 3 dimensiones siempre. Si no estás seguro de la prioridad, `priority:medium`. Si no estás seguro de la complejidad, mirar el body — > 1 día = `complexity:medium`, sino `complexity:small`.

### Mobile como criterio

**Cada ruta debe tener un layout mobile pensado a propósito, no solo un escalado responsive automático.** No alcanza con "se ve más o menos OK en celu" — necesitamos un patrón visible (dual render `md:hidden`/`hidden md:block`, sticky bar, sheet fullscreen, lista card-based) y validación manual en viewport 375×667 (iPhone SE).

Gate de merge: cualquier PR que toque rutas de cliente (`/`, `/equipo/*`, `/cliente/*`, `/estudio`) o admin prioritario (`/admin/pedidos`, `/admin/dashboard`) requiere mobile pass antes de mergear.

El wrapper [`<PublicLayout>`](src/components/rental/PublicLayout.tsx) provee TopBar + Footer mobile-aware, pero **no garantiza el criterio** — el contenido de cada ruta tiene que cumplirlo por su cuenta.

Definición completa del criterio, checklist y status por ruta en [`docs/MOBILE_AUDIT.md`](docs/MOBILE_AUDIT.md). Procedimiento en [`docs/PROTOCOLO.md`](docs/PROTOCOLO.md).

---

## 4. Glossary

Cuatro nociones que se cruzan a lo largo del producto. Distinguirlas evita confusión:

- **Categoría** — árbol jerárquico de hasta 3 niveles (ej. Cámara → Cinema → FX3). Cada equipo pertenece a una o más. Determina el filtro principal del catálogo público y dispara el spec template + plantilla de nombre.
- **Etiqueta** — tag libre, plano (sin jerarquía). Atraviesa categorías (ej. "Sony E mount" puede aplicar a cámaras y a lentes). Filtro secundario.
- **Spec** — fila clave-valor adjunta a un equipo (`Sensor: Full Frame`). Lo técnico que se ve en la ficha. Tipo `text` o `number` (con unidad).
- **Spec Template** — norma de specs **por categoría**. Define qué labels deben existir en cada equipo de esa categoría, en qué orden, con qué tipo y unidad. Heredan automáticamente al crear un equipo nuevo. "AI sugiere, humano cura" → el autocompletar respeta el template como hint.

---

## 5. Mapa del código

Puntos de entrada para no grepear:

| Qué | Dónde |
|---|---|
| Rutas frontend (file-based) | `src/routes/` |
| Componentes admin | `src/components/admin/` |
| Form V2 de equipos | `src/components/admin/equipo-form-v2/` |
| Lógica reusable / utilities UI | `src/lib/` |
| Endpoints backend | `backend/routes/` (`equipos.py`, `clientes.py`, `dashboard.py`, etc.) |
| Schema base + pool DB | `backend/database.py` |
| Migrations Alembic | `backend/migrations/versions/` |
| Auth admin | `backend/admin_guard.py` |
| Auth cliente | `backend/routes/auth.py` |
| Storage R2 + scrape + optimize foto | dentro de `backend/routes/equipos.py` |

---

## 6. Decisiones del proyecto

> Lecciones aprendidas y elecciones arquitectónicas. Útil para no re-discutir cosas.

### Auth

- **Admin**: Google OAuth → sesión cookie firmada. `require_admin(request)` en cada endpoint admin.
- **Cliente**: Google OAuth separado → cookie `cliente_session` distinta. `require_cliente(request)` valida `role: "cliente"` (no acepta sesiones admin).
- **Dev mode**: `ADMIN_BYPASS_AUTH=1` en `.env.local` saltea la validación. Lo usan los tests E2E (con `PLAYWRIGHT_ADMIN=1`).

### Base de datos

- **Postgres puro** (migró de SQLite). El wrapper `PGCursor` traduce placeholders `?`→`%s` para no reescribir cientos de queries.
- **Migraciones**: schema base con `CREATE IF NOT EXISTS` en `backend/database.py::init_db()`. Cambios incrementales con Alembic (`backend/migrations/versions/`).
- **Soft delete**: equipos tienen `eliminado_at TIMESTAMP NULL`. Las listas filtran `IS NULL` por default. Endpoint `POST /equipos/:id/restore`. Vista "papelera" en lista admin. Bulk delete en papelera = hard delete (action `delete_permanent`).

### Storage de fotos

- R2 (S3-compatible). Cada foto se sube con upload server-side desde una URL externa o un archivo local.
- Allowlist anti-SSRF para URLs externas (`_validate_external_image_url`). Hosts conocidos (B&H, Adorama, manufacturer domains, CDNs).
- Las fotos se procesan con `_optimize_image`: auto-crop de whitespace, padding 6%, resize a 1200×1200, ratio cuadrado.

### Form de equipos

- **EquipoFormDialogV2** es EL form. Sin tabs, scroll lineal con secciones colapsables. Mismo flow CREATE / EDIT.
- El form viejo (`EquipoFormDialog.tsx`) fue borrado — no resucitar.

### Autocompletar de specs (admin UI, por equipo)

> **Cuándo se usa:** admin agrega un equipo nuevo individual en el form y pega la URL B&H. Equipo a equipo, on-demand, vía UI. **NO confundir** con el seed bulk inicial (ver "Dataset y seed por categoría" más abajo).

- **URL única** en la autocompletar bar: bindeada al campo `bh_url` del form, con botones copy/abrir inline.
- **Backend**: endpoint canónico `POST /admin/equipos/autocompletar` (alias deprecated `/enriquecer`). Scrape con Firecrawl + extract con LLM. Devuelve `AutocompletarResult` normalizado.
- **Normalizer de specs**: backend traduce labels EN→ES (Weight→Peso, Lens Mount→Montura, etc.) y convierte unidades (lbs→kg, in→cm, °F→°C, ranges, dimensiones N×N×N).
- **Cache del scrape**: el `AutocompletarResult` completo se guarda en `equipo_fichas.raw_json`. Habilita botones ✨ por sección en el form V2 que re-aplican campos sin volver a scrapear.
- **Batch**: `POST /admin/equipos/batch-enriquecer` procesa hasta 3 equipos por request (cap defensivo, max 50 ids en body). Frontend re-batchea hasta terminar. Resultado se persiste en raw_json (cache). Sleep 1s entre scrapes para no rate-limitear B&H.
- **Parser determinístico embebido (URL path)**: el endpoint URL existente ahora pide `rawHtml` a Firecrawl además del `json` extract. Si el rawHtml tiene JSON-LD estructurado (B&H lo siempre tiene), se corre `services/luces_html_extractor.py` (el MISMO pipeline del seed). Cuando el parser detecta ≥3 specs canónicos, OVERRIDE marca/modelo/specs/foto del LLM extract con la versión normalizada. Si no detecta nada (no es lighting, parser falla), se mantiene el flujo LLM intacto. → **Resultado: URL paste ahora también da calidad seed para luces sin tocar la UX**.
- **HTML upload (fallback / cuando Firecrawl falla)**: `POST /admin/equipos/autocompletar-from-html` acepta un `.html` guardado manualmente (Cmd+S → Webpage Complete desde B&H/manufacturer) y corre el mismo pipeline directo sobre el HTML, sin Firecrawl. Sirve cuando B&H bloquea Firecrawl con bot-detection o cuando la URL no es accesible. UI: botón "Subir HTML guardado" en el diálogo de autocompletar.
- **Paridad URL ↔ HTML upload**: ambos paths llaman a `luces_html_extractor.extract_from_html()` que reusa `tools/iluminacion_parser.py` + `iluminacion_normalizar.py`. Cualquier mejora al parser/normalizer mejora los TRES paths (seed bulk + URL autocompletar + HTML upload) automáticamente.

### Dataset y seed por categoría (bulk inicial)

> **Cuándo se usa:** poblar una categoría entera del catálogo de una sola pasada — typically el setup inicial o cuando entra un sub-segmento nuevo. **NO confundir** con autocompletar (que es por equipo, on-demand desde el form). Coexisten: el seed pone la base, autocompletar agrega ad-hoc o re-enriquece.

**Por qué un archivo por categoría (no unificado):** cada categoría tiene specs muy distintas (cámaras: `lens_mount`, `fps_max`; lentes: `distancia_focal`, `apertura`; luces: `potencia_w`, `color_modes`). Forzar un schema unificado pierde tipado fuerte. Per-categoría: cada archivo enfocado, pequeño, con su propio parser/seed/doc. Git history limpio. Escala bien (categoría nueva = archivo nuevo, no riesgo de romper las existentes).

**Por qué el naming dropea `bh_`:** B&H es la fuente primaria pero no la única. ARRI y Mole vienen de sus sitios fabricante (vía WebFetch). Futuras categorías van a usar Adorama, screenshots manuales, PDFs, etc. El dataset es **agnóstico de fuente** — la fuente queda registrada en `url_source` y `_meta.fuentes` de cada producto.

**Workflow:**

1. **Capturar HTMLs** de B&H (o site fabricante para casos como ARRI/Mole) → `~/Desktop/Paginas/Inventario/<Categoria>/`.
2. **Parsear con `tools/bh_<categoria>_parser.py`** — extrae DOM + JSON-LD structured data, salida raw a `docs/bh_<categoria>_relevamiento.json` y curada a `docs/bh_<categoria>_curado.json`.
3. **Curar manualmente** lo que el parser no puede inferir (overrides en `tools/bh_<categoria>_patches.py` — usado para sitios fabricante o HTMLs incompletos).
4. **Normalizar** marcas/modelos/IDs con `tools/bh_<categoria>_normalizar.py` (canonicaliza brand, modelo limpio, IDs estables).
5. **Importar** vía `backend/seeds/<categoria>.py` — idempotente, popula `spec_definitions` + `categoria_spec_templates` + sub-categorías + `equipos` + `equipo_specs` en una pasada.

**Convenciones del dataset curado** (los 3 niveles por producto):

- **`specs`**: campos canónicos para filtros/comparación. Todos numéricos o enum estrictos. Ej: `potencia_w: 410`, `temperatura_k: {min: 1800, max: 20000}`, `color_modes: ["RGB","Daylight","Tungsten"]`. Unidades en field name (`_w`, `_g`, `_k`).
- **`extras`**: ficha técnica detallada. Strings descriptivos + algunos numéricos estructurados (ej. `dimensiones_cm: {largo_cm, ancho_cm, alto_cm}`, `noise_db: {silent, medium, high}`).
- **`ficha`**: raw del scrape (todas las secciones B&H tal cual). Para renderizar ficha técnica completa sin perder data.

**Convenciones cross-cutting:**

- Métrico como base de DB (g, cm, m, K, W). UI computa imperial desde el base.
- Excepción: pins/studs/accessory diameter en imperial-native (5/8″, 6.6″) — estándar industria cine.
- Marcas canónicas con casing fijo (`ARRI`, `Amaran`, `Mole-Richardson`, `Nanlite`, etc.) — definido en `bh_<categoria>_normalizar.py::BRAND_CANON`.
- IDs estables `marca_modelo` snake_case (ej. `aputure_nova_ii_2x1`).
- Ausencia = `null` o campo ausente. NO usar strings `"N/A"`, `"None"`, `"—"`.

**Estado del dataset por categoría:**

| Categoría | Estado | Doc |
|---|---|---|
| Iluminación | ✅ 16 luces curadas, seed listo, HTML upload wireado al admin | [`docs/DATASET_ILUMINACION.md`](docs/DATASET_ILUMINACION.md) |
| Cámaras | ✅ 6 cámaras curadas + seed listo. **HTML upload UI aún apunta solo a iluminacion_html_extractor** — falta dispatcher por categoría | [`docs/DATASET_CAMARAS.md`](docs/DATASET_CAMARAS.md) |
| Lentes | ⏳ pendiente | — |
| (otras) | ⏳ pendiente | — |

**Por qué el seed coexiste con `categoria_spec_templates`:** ese table sigue siendo necesario porque define UI metadata (qué specs van en card/filtros/nombre, prioridad de display) — eso no se deriva del dato del equipo. Lo que el seed automatiza es que el admin no la pueble a mano: el script lo hace en una pasada idempotente.

**Back-office después del seed:** una vez corrido, el dataset JSON queda como bootstrap/archivo (no se consulta en runtime). La DB es la fuente de verdad. Todo lo importado se ve y se edita desde el back-office existente:

- **Equipos** (`/admin/equipos`) — lista admin, form `EquipoFormDialogV2`. Edita precio_jornada, foto_url, marca, modelo, nombre_publico, etc.
- **Specs values por equipo** — en la sección Specs del form admin del equipo.
- **Spec definitions globales** (`/admin/equipos/specs`) — catálogo de specs (potencia_w, cri, etc.). Edita label, enum_options, ayuda.
- **Categorías** — admin las gestiona en la UI existente de categorías.

**Quién edita qué (operativa diaria):**

| Acción | Sin Claude | Con Claude |
|---|---|---|
| Agregar 1 luz nueva — URL paste (Firecrawl OK) | ✅ Calidad seed automática (parser embebido) | — |
| Agregar 1 luz nueva — URL paste falla (Firecrawl rate-limit / bot-detection) | ✅ Subir HTML guardado (Cmd+S → upload) | — |
| Agregar equipo no-luz (cámara, lente) — categoría existente | ✅ Admin UI + autocompletar (LLM extract) | — |
| Editar precio / foto / nombre / spec value | ✅ Admin UI | — |
| Agregar spec key nueva al catálogo global | ✅ `/admin/equipos/specs` | — |
| Importar bulk de una categoría NUEVA (ej. cámaras) — primera vez | — | ✅ Curar HTMLs + parser específico + seed |
| Refactor del schema (ej. partir `peso` en sub-campos) | — | ✅ Plan + migration |

**Limitaciones:**
- El parser determinístico hoy solo cubre **luces** (`iluminacion_parser`). Para cámaras/lentes/etc. el URL paste cae al LLM extract hasta que armemos el parser específico por categoría (`camaras_parser.py`, etc. — patrón replicable).
- El parser asume estructura B&H. Otros sites (Adorama, manufacturer pages) caen al LLM extract.
- Si Firecrawl no puede acceder al URL (bot-detection más agresivo de B&H, sitio caído), fallback a HTML upload.

El JSON del dataset NO se edita post-seed (es dev artifact). Para cambios puntuales: admin UI. Para reseed masivo (raro): editar JSON + re-correr seed (idempotente, no pisa campos manuales como `precio_jornada`).

**El JSON queda "congelado" después del seed.** Si querés un export del estado actual de la DB → JSON otra vez (por backup o re-importar a otro ambiente), se arma un script `dump_<categoria>.py` cuando haga falta. Por defecto no es necesario.

### Display templates por spec (placeholders del nombre público)

> **Cuándo aplica:** cuando un spec se usa en una plantilla de nombre público vía `{spec:Label}`. El sistema mapea el label → spec_key → display template para mostrar el valor con formato bonito en vez del valor crudo.

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

**Templates disponibles:**

```
spec_key                      short                       long
─────────────────────────────────────────────────────────────────────────────
potencia_w                    "1000W"                     "1000W"
lumens_at_5600k               "19389 lumen"               "19389 lm a 5600K"
lumens_at_3200k               "17000 lumen (tungsten)"    "17000 lm a 3200K"
lux_at_1m_5600k               "11600 lux"                 "11600 lux a 1m (5600K)"
cri                           "CRI 95"                    "CRI 95"
tlci                          "TLCI 98"                   "TLCI 98"
temperatura_k                 "1800-20000K" / "3200K"     idem
peso_g                        "390g" / "3.3 kg"           idem
megapixels                    "33.0MP"                    idem
fps_max                       "120fps"                    idem
continuous_shooting_fps       "30fps"                     "30fps (ráfaga)"
iso_nativo                    "ISO 80-102400"             idem
rango_dinamico_stops          "15 stops"                  idem
```

**Convenciones de naming en nombres públicos:**
- Nombres cortos y claros (la ficha técnica completa muestra el detalle)
- Sin "@" — usar "a" en español ("a 5600K" no "@ 5600K")
- Unidades en palabra cuando es más legible ("lumen" vs "lm" en short)
- Sin contexto redundante en short (la temp ya está implícita en el contexto general del producto)

**Para agregar un display template nuevo:** editar `SPEC_DISPLAY_TEMPLATES` en `nombre_builder.py`. Si el label difiere del spec_key, agregar también el mapping en `LABEL_TO_SPEC_KEY`.

**Futuro opcional:** mover `display_template_short` y `display_template_long` a columnas de `spec_definitions` para que el admin lo edite desde la UI sin tocar código. Patrón actual con dict en código alcanza para el inicio.

### Bulk actions en lista admin

- En vista normal: las bulk actions son soft (`delete` → marca `eliminado_at`).
- En vista papelera: `delete_permanent` hace hard delete. Es la única forma de borrar irreversible.

### Búsqueda fuzzy

- El parámetro `q` en `GET /equipos` busca en `nombre`, `marca`, `modelo`, `serie`, `descripcion`, `specs_json`, `keywords_json`. Aplicable a admin lista y catálogo público.
- Limitación: LIKE crudo sobre JSON → posibles falsos positivos si buscás field names tipo "label" o "value". Aceptable para inventario chico-mediano.

### Mantenimiento

- Log por equipo (`equipo_mantenimiento`) con tipo, costo y `proxima_revision`. Vencidas se marcan visualmente en la lista admin.

### Dashboard de uso

- Dialog desde la lista admin, no ruta separada — evita ediciones de `routeTree.gen.ts` auto-generado.
- "Por cobrar" excluye `cancelado` y `borrador`. Solo cuenta pedidos con compromiso real de pago.

### Naming conventions

- **Frontend**: ya migró a "autocompletar" como nombre del feature.
- **Backend**: endpoints canónicos `/autocompletar`. Los viejos `/enriquecer` quedan como aliases deprecated.
- **Nombres de funciones internas** (`aplicarEnriquecimiento`, `admin_enriquecer_equipo`, `EnriquecerInput`) siguen con el nombre viejo — rename completo es un follow-up cuando duela.
- **Columna DB `roi_pct`**: nombre técnicamente incorrecto. El valor es "% del valor del equipo cobrado por día" (tarifa diaria). **Label canónico en UI**: `% día` (decisión cerrada — #262). La columna DB sigue como `roi_pct` por costo de migración vs valor — solo lo ve dev en queries. El admin ve "% día".

---

## 7. Dónde encontrar cosas

### Backlog, changelog, decisiones puntuales

**Todo vive en GitHub Issues.** Este manifiesto no duplica el contenido — solo apunta.

| Querés saber… | Comando |
|---|---|
| Qué hay pendiente | `gh issue list --state open` |
| Qué features están en curso | `gh issue list --state open --label feature` |
| Qué bugs hay reportados | `gh issue list --state open --label bug` |
| Qué se entregó (changelog) | `gh issue list --state closed --sort created --order desc` |
| Por qué algo está como está | abrir el issue cerrado de esa iniciativa |

Si una funcionalidad existe en código y no en issues, es un gap → crear el issue retroactivo. Excepción documental: `docs/BUGS.md` conserva la auditoría inicial del 2026-05-10 (precede la convención).

### Docs auxiliares

| Archivo | Cuándo |
|---|---|
| [`docs/PROTOCOLO.md`](docs/PROTOCOLO.md) | Workflow de PRs, auditoría, mobile gate |
| [`docs/DEPLOY_RAILWAY.md`](docs/DEPLOY_RAILWAY.md) | Deploy y rollback |
| [`docs/MOBILE_AUDIT.md`](docs/MOBILE_AUDIT.md) | Checklist mobile + status por ruta |
| [`docs/DISEÑO_SPECS.md`](docs/DISEÑO_SPECS.md) | Sistema de specs / templates |
| [`docs/DATASET_ILUMINACION.md`](docs/DATASET_ILUMINACION.md) | Dataset curado de luces + workflow seed por categoría |
| [`docs/ISSUE_LABELS.md`](docs/ISSUE_LABELS.md) | Convención de labels |

### Cosas que NO existen todavía

Aclaración para no buscarlas en vano: pagos online (Stripe/MercadoPago), notificaciones por email, multi-tenant, dark mode, app mobile nativa.

### Sesión nueva pierde el rumbo

Si Claude se pierde a mitad de sesión: `Releé MANIFIESTO.md y los issues abiertos en https://github.com/tixenre/rental/issues`.
