# Sistema de fotos / media — manual técnico

> **Fuente única de "cómo funcionan las fotos" en Rambla Rental.** Describe la arquitectura y el flujo
> (estable); los **paths** son los puntos de entrada al código. Las **reglas de criterio + el porqué** NO
> se duplican acá — viven en [`MEMORIA.md`](MEMORIA.md) / [`DECISIONES.md`](DECISIONES.md) y se linkean.
> Si tocás un motor y este manual queda viejo, actualizalo en el mismo cambio (el supervisor lo marca).

## El panorama: dos capas

Toda foto del sistema pasa por dos capas independientes:

1. **Procesar** (backend, el "motor") — toma la foto que sube el dueño y **genera las versiones**: original
   intacto + variantes (display/sm/thumb) en **webp**, **AVIF** y la **OG en JPEG** (crawlers), más el **LQIP**
   (blur-up). Es no-destructivo: el original se conserva.
2. **Mostrar** (frontend) — agarra esas versiones y las **dibuja**, eligiendo cuál según el dispositivo. Hay
   **tres caminos** según de dónde vienen los datos (ver §4).

El motor es **único y agnóstico de la entidad** (sirve a equipos, estudio, instructores, marca). No hay un
pipeline de fotos por feature — todo pasa por `backend/services/media/`.

---

## 1 · El motor (procesar) — `backend/services/media/`

| Módulo | Rol |
|---|---|
| `service.py` | Orquesta el pipeline: `store_upload()` (la puerta única de ingreso) + `derive_and_finalize()` (modo background). |
| `specs.py` | Catálogo de variantes (`DeriveSpec`) + el conjunto canónico **`EQUIPO_DERIVE_SPECS`**. |
| `processing.py` | Puro: strip EXIF, `_optimize_image()` (resize/cuadrar/formato), `generate_lqip()`, fallback de codec. |
| `storage.py` | Cloudflare R2 (boto3): `put()` público (immutable), `put_private()` (original), `get_original()`, `delete_object()`. |
| `repository.py` | Acceso a `media_assets` / `media_variants`: insert/update/`find_by_hash` (dedup). |
| `gc.py` | `reconcile_media()` (huérfanos, dry-run) + `rederive_variants()` (regenerar desde el original). |
| `validation.py` / `security.py` | Magic-bytes, decompression-bomb, y SSRF+allowlist para URLs externas. |
| `models.py` / `errors.py` | Dataclasses (`DeriveSpec`, `MediaVariant`, `MediaAsset`) + excepciones tipadas. |

### Flujo de `store_upload()` (la puerta única)
1. Valida `kind` + la imagen (magic-bytes, bomba de descompresión).
2. **Strip EXIF** (privacidad: GPS, device, timestamps).
3. Genera **LQIP** (4×4px → JPEG q20 → data-URI base64, ~100 bytes).
4. **Dedup por `content_hash`** (`find_by_hash`): si ya existe ese asset, lo reusa (no re-sube bytes).
5. INSERT en `media_assets`.
6. PUT del **original privado** en R2 (`put_private`, no público, no CDN).
7. **Deriva cada variante** del spec set: `_optimize_image` → PUT pública (`put`) → INSERT en `media_variants`.
8. Retorna el `MediaAsset` con sus `variants`.

Modo `background=True`: hace 1-6, el caller commitea, y `derive_and_finalize()` deriva las variantes async.

### Las variantes (`specs.py`)
Cada upload de **equipo** usa **`EQUIPO_DERIVE_SPECS`** (fuente única) = 7 variantes:
`display` / `display-sm` / `display-thumb` (webp 1200/600/160px) + las mismas 3 en **AVIF** + `og` (JPEG 1200²).
El estudio usa el set keep-aspect (`DISPLAY_KEEP_ASPECT*` webp + avif).

### Gotchas del motor
- **Fallback de codec AVIF→webp**: si Pillow no tiene libavif en runtime, la variante `*-avif` se genera como
  webp **en silencio** (mismo nombre, content-type webp). Pillow 12.x trae el codec, pero el guardrail real es
  chequear el `content_type`, no solo que la variante exista.
- **`rederive` debe incluir AVIF**: la lista de re-derivación del admin (`media_admin.py::_ALL_DERIVE_SPECS`)
  tiene que incluir las specs AVIF, o re-derivar pierde el AVIF. Regresión cazada en
  [#1054](https://github.com/tixenre/rental/issues/1054) (test: `test_media_admin_derive_specs.py`).

---

## 2 · Almacenamiento y datos

**Tablas** (`backend/database/schema.py`):
- `media_assets` — un asset único; dedup por `UNIQUE(kind, content_hash)`; guarda `lqip`, `status` (pending/ready/failed).
- `media_variants` — las versiones de un asset; `UNIQUE(asset_id, name)`; cada una con `url`, `content_type`, `width`, `height`.
- `equipo_fotos` — galería de equipo; tiene `media_id` (FK, `ON DELETE SET NULL` → fallback legacy) + `url`/`orden`/`es_principal`.
- `estudio_fotos` — fotos del estudio; `media_id` + columnas **denormalizadas** (`url_sm`, `url_avif`, `url_sm_avif`).

**Denormalización en `equipos`** (cache de la foto **principal**, para que el catálogo no haga un fetch por equipo):
`foto_url`, `foto_url_sm`, `foto_url_thumb`, `foto_url_avif`, `foto_url_sm_avif`, `foto_url_thumb_avif`, `foto_lqip`.
Se sincronizan en **un solo UPDATE** vía el helper único `_sync_principal_denorm(conn, equipo_id)` en
`routes/equipos/fotos.py` (corre al subir/borrar/reordenar la principal).

**Nomenclatura en R2**: original privado `media/{kind}/{asset_id}/original.{ext}`; variante pública
`media/{kind}/{asset_id}/{variant}.{ext}`. La URL pública es `{R2_PUBLIC_BASE}/{key}` (`R2_PUBLIC_BASE` en config;
las imágenes salen por Cloudflare delante de R2).

---

## 3 · La API (endpoints)

| Endpoint | Archivo | Rol |
|---|---|---|
| `POST /admin/equipos/{id}/upload-foto[-from-url]` | `routes/equipos/fotos.py` | Subir/ingerir la foto principal → motor → denorm. |
| `GET/POST/DELETE/PATCH /admin/equipos/{id}/fotos[...]` | `routes/equipos/fotos.py` | Galería de equipo (listar/agregar/borrar/reordenar). |
| `POST /admin/estudio/upload-foto[-from-url]` | `routes/estudio.py` | Fotos del estudio (hero + galería). |
| `GET /api/media/entity/{kind}/{id}` | `routes/media_api.py` | **Público**: devuelve `{assets:[{...,variants[]}]}`. Fallback legacy: foto sin `media_id` → variante sintética `display`. Lo consume la galería de la ficha. |
| `GET /admin/media/stats` · `POST /admin/media/gc` · `POST /admin/media/rederive/{id}` | `routes/media_admin.py` | Dashboard de media: métricas, reconciliación, re-derivación. |

---

## 4 · Mostrar (frontend) — 3 caminos según el shape de datos

La regla de oro: **un componente por shape de datos** (no reimplementar el `<picture>` a mano).

| Camino | Componente | Datos | Por qué |
|---|---|---|---|
| **Catálogo** (cards/filas/thumbs) | **`EquipoFoto`** (`components/rental/EquipoFoto.tsx`) | **columnas denorm** del payload de `/api/equipos` | El listado trae 127 equipos; un fetch por card sería letal. Las columnas ya vienen en el payload. |
| **Galería de la ficha** | **`ResponsiveImage`** + `MediaGallery` (`components/common/`), hook `useEntityMedia` | **`variants[]`** de `/api/media/entity/` | Una entidad, varias fotos → un fetch por entidad es barato y trae width/height (anti-CLS). |
| **Hero del home** (LCP) | **`heroImgProps`** (`lib/studio/hero-photos.ts`), en `HeroSection`/`HeroBanner` | `useHeroPhotos()` (de `/api/estudio`) | `<img src=avif>` **directo**, NO `<picture>` — para que el preload AVIF matchee (ver §5). |

- **Builders de srcset** (`lib/srcset.ts`): `buildFotoSrcSet` / `buildAvifSrcSet` (shape denorm) y `buildSrcSet` (shape `variants[]`).
- **Preload del hero**: `backend/main.py::_inject_hero_preload` inyecta `<link rel=preload as=image type=image/avif>`
  de la foto principal del estudio en el HTML servido, para que el LCP sea descubrible sin esperar a React.

---

## 5 · Reglas y gotchas (el porqué vive en MEMORIA — acá solo el puntero)

- **El motor es la fuente única** (no hay pipeline por feature). Patrón análogo al de marca →
  _2026-06-06 — `backend/services/branding/` = motor único de assets de marca_.
- **Hero = AVIF-directo + preload; el resto usa `<picture>`** → _2026-06-25 — Hero (LCP) = AVIF-directo + preload
  AVIF; el resto usa `picture`; SSR descartado_. **Gotcha clave:** el preload (backend) y el `<img>` (front)
  deben elegir la **misma foto principal** — ambos ordenan `es_principal DESC, orden ASC, id ASC`. Si cambiás
  el orden en el endpoint del estudio, revisá que sigan coincidiendo, o vuelve la doble descarga.
- **`EquipoFoto` (catálogo, denorm) vs `ResponsiveImage` (galería, variants[])**: dos componentes por dos
  shapes; el supervisor marca un `<picture>` de foto de equipo hecho a mano fuera de esos dos (#1056).
- **webp NO se elimina**: es el fallback del `onError` (hero) y del `<picture>` (catálogo). El JPEG (`og`) es
  solo para crawlers de redes (WhatsApp no renderiza webp confiable).

---

## 6 · Scripts de backfill — `backend/scripts/`

Idempotentes, best-effort, commitean por asset. Reusan el motor (no re-suben bytes si ya existe el hash).

| Script | Rol |
|---|---|
| `backfill_ingest_legacy.py` | Migra fotos sin `media_id` al motor. **Tier B** (R2 propio, vía boto3) + **Tier C** (URLs externas con allowlist SSRF). Flags `--dry-run`, `--solo-tier=b|c`. |
| `backfill_display_sm.py` / `_thumb.py` / `_avif.py` / `backfill_og_fotos.py` | Generan la variante que falta (sm 600 / thumb 160 / AVIF / OG JPEG) para assets que no la tienen. |
| `backfill_estudio_sm.py` | `display-sm` para `estudio_fotos`. |

---

## 7 · Cómo extenderlo
- **Nueva variante** (ej. otro ancho): agregar el `DeriveSpec` en `specs.py`, sumarlo al set canónico
  (`EQUIPO_DERIVE_SPECS`) **y** a `_ALL_DERIVE_SPECS` del re-derive (`media_admin.py`), y correr el backfill.
- **Nueva entidad** (ej. fotos de X): subir vía `store_upload(kind="x", ...)`; exponer en `/api/media/entity/x/{id}`;
  consumir con `useEntityMedia("x", id)` + `ResponsiveImage`/`MediaGallery`.
- **Nueva superficie de catálogo**: usar `EquipoFoto` (nunca reimplementar el `<picture>`).

## 8 · Estado / pendientes
- **Galería de la ficha al path canónico** + miniaturas optimizadas → [#1056](https://github.com/tixenre/rental/issues/1056).
- **Fotos externas pesadas (Tier C) al motor** (bhphotovideo) → cruza con [#1051](https://github.com/tixenre/rental/issues/1051); el backfill ya existe.
