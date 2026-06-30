---
name: gear-compatibility
model: sonnet
last-reviewed: 2026-06-23
version: 1.0
description: Generates automatic equipment compatibility relationships between AV gear (cameras, lenses, monitors, recorders, lights, etc.) using existing specs as a baseline plus reasoning over scraped product data. Includes a spec resolver/normalizer that maps incoming labels to canonical specs and proposes new specs/options when warranted. Always operates against a backend API — never modifies the DB directly. Specs proposals never auto-apply; they queue for human approval.
---

# Gear Compatibility Skill

This skill computes equipment compatibility for an AV rental inventory. It complements (does not replace) the deterministic `_compute_compat` algorithm that matches via spec drivers — this skill handles the cases the deterministic algorithm marks as `sin_relacion` or `parcial`, and proposes catalog improvements as a side effect.

## Triggers

The user invokes the skill with one of:

- `/gear-compat <id_a> <id_b>` — analyze one specific pair (most precise, lowest cost)
- `/gear-compat new` — process all equipment with `compat_analizado_at IS NULL` or modified after last analysis (consume the queue)
- `/gear-compat all` — recompute compatibility for the entire inventory (most expensive — confirm before running on large catalogs)

When invoked, follow the flow in SECTION B. Apply the knowledge from SECTION A as reasoning input.

---

## SECTION A — AV Domain Knowledge (PORTABLE)

This section is portable — it can be lifted into another repository/project without modification. It encodes the dominio audiovisual: how AV gear physically interacts, the canonical vocabulary of connections, the hierarchy of sensor sizes, etc.

### Critical modeling rule for specs

Specs that capture **a range of correlated values** must be modeled as ONE spec with the appropriate type. NEVER propose splitting them.

| Real-world concept            | Correct type     | Example value           | NEVER propose                          |
|-------------------------------|------------------|-------------------------|----------------------------------------|
| Focal length (zoom lens)      | `rango`          | `"24-70"` mm            | ❌ `focal_min` + `focal_max`           |
| Focal length (prime lens)     | `rango`          | `"50"` mm               | ❌ split or `number`                   |
| Variable aperture             | `rango`          | `"f/2.8-4"`             | ❌ `apertura_min` + `apertura_max`     |
| ISO range                     | `rango`          | `"100-25600"`           | ❌ `iso_min` + `iso_max`               |
| Shutter speed range           | `rango`          | `"1/8000-30"` s         | ❌ split                               |
| Stand height min/max          | `rango`          | `"0.5-3.5"` m           | ❌ `altura_min` + `altura_max`         |
| Resolution (2D)               | `wxh`            | `"6144×3240"` px        | ❌ `width` + `height`                  |
| Physical dimensions (3D)      | `wxhxd`          | `"130×85×78"` mm        | ❌ split into 3 specs                  |
| Multiple connectors           | `multi_enum`     | `["HDMI", "SDI"]`       | ❌ one spec per connector              |

Reason: this mirrors how the gear is cataloged in real product pages (B&H, Adorama, manufacturer manuals), the frontend has dedicated input components for each, and the public name builder (`{spec:Focal length}`) resolves directly to `"24-70mm"`. Splitting causes schema explosion and breaks the builder.

When you find raw data like `"Focal Length Range: 24-70mm"` or `"Min Focal: 24, Max Focal: 70"`, you must consolidate to a single `distancia_focal` spec with value `"24-70"`. Same for shutter speed, ISO, aperture, and dimensions.

### Specs typically used as compatibility drivers

| Concept           | Mode           | Typical roles                              | Notes                          |
|-------------------|----------------|--------------------------------------------|--------------------------------|
| Mount             | `exacta`       | (none, symmetric)                          | E, RF, EF, MFT, PL, F, L       |
| Sensor format     | `jerarquia`    | Camera=`contenido`, Lens=`contenedor`      | Order: MFT < APS-C < S35 < FF < MF |
| Video output      | `exacta`       | (none) `multi_enum`                        | HDMI variants, SDI variants    |
| Power/battery     | `exacta`       | Battery=`contenedor`, Equipment=`contenido` | V-Mount, Gold Mount, NP-F, Sony L-series, Canon LP-E6 |
| Storage media     | `exacta`       | (none) `multi_enum`                        | CFexpress A/B, SD UHS-II, CFast 2.0 |
| Recording codec   | `exacta`       | (none) `multi_enum`                        | ProRes flavors, H.264/H.265, REDCODE, BRAW |

### Canonical hierarchical orderings (for `compatibilidad_modo='jerarquia'` specs)

- Sensor format: `["MFT", "4/3", "APS-C", "Super 35", "Full-frame", "Medium Format"]`
- Recording resolution: `["HD", "2K", "4K UHD", "4K DCI", "6K", "8K"]`
- Color depth: `["8-bit", "10-bit", "12-bit", "14-bit", "16-bit"]`

### Video connectivity model: video_out + video_in + signal_routing

The system has three specs that together model video connectivity:

**1. `video_out`** (multi_enum, es_compatibilidad=true) — output connectors. Equipment that PRODUCES a video signal: cameras, monitor loop-outs, recorder outputs, transmitter outputs. Options ordered by family + speed: `["HDMI 1.4", "HDMI 2.0", "HDMI 2.1", "SDI 3G", "SDI 6G", "SDI 12G"]`.

**2. `video_in`** (multi_enum, es_compatibilidad=true) — input connectors. Equipment that CONSUMES a video signal: monitors, recorders, switchers, transmitter inputs. Same option list as video_out.

**3. `signal_routing`** (multi_enum, es_compatibilidad=false) — internal path routing for equipment that has BOTH inputs and outputs. NOT a compat driver — it's metadata for the IA skill to use during 3-hop discovery (finding a converter in inventory that bridges incompatible pairs). Options: `["HDMI→HDMI", "SDI→SDI", "HDMI→SDI", "SDI→HDMI", "HDMI→Wireless", "SDI→Wireless", "Wireless→HDMI", "Wireless→SDI", "HDMI→USB", "SDI→USB", "HDMI→Ethernet", "SDI→Ethernet"]`.

**Cross-spec match (deterministic, already implemented in `_compute_compat`):**
For any pair A↔B, the system compares A's `video_out` against B's `video_in` (and vice-versa). If they share a connector exactly, or share a family with the minimum common version (HDMI 2.1 ↔ HDMI 2.0 → both can talk at HDMI 2.0), it's `match`. If they don't share family, it's `mismatch` (the skill should propose adapter/converter resolution).

**Examples of signal_routing values:**
| Equipment                                    | video_in              | video_out             | signal_routing                                                     |
|----------------------------------------------|-----------------------|-----------------------|---------------------------------------------------------------------|
| Camera (e.g. Sony FX3)                       | —                     | `[HDMI 2.0, SDI ..]`  | — (only out, no internal routing)                                  |
| Atomos Ninja V (recorder + monitor loop-out) | `[HDMI 2.0, SDI 12G]` | `[HDMI 2.0, SDI 12G]` | `[HDMI→HDMI, SDI→SDI]` (passthrough, no cross)                     |
| Decimator MD-HX (converter)                  | `[HDMI 2.0, SDI 12G]` | `[HDMI 2.0, SDI 12G]` | `[HDMI→HDMI, SDI→SDI, HDMI→SDI, SDI→HDMI]` (cross-family converter) |
| DJI transmitter (wireless tx)                | `[HDMI 2.0, SDI 12G]` | —                     | `[HDMI→Wireless, SDI→Wireless]` (one input active at a time)       |
| DJI receiver (wireless rx)                   | —                     | `[HDMI 2.0, SDI 12G]` | `[Wireless→HDMI, Wireless→SDI]` (both outputs active)              |
| Viltrox cross-converter (no family cross)    | `[HDMI 2.0, SDI 12G]` | `[HDMI 2.0, SDI 12G]` | `[HDMI→HDMI, SDI→SDI]` (NOT [HDMI→SDI] — distinguishing trait!)    |

**Skill use of signal_routing for 3-hop discovery:**
When camera A has only SDI out and monitor B has only HDMI in (deterministic = `mismatch`), iterate over inventory: find an equipo C with `SDI in` AND `signal_routing` that includes `SDI→HDMI` AND `HDMI out`. If found, mark A↔B as `requiere_adaptador` with `adaptador_id=C`. If not found, leave `adaptador_id=null` and propose in `razon_ia` what converter type would be needed (e.g. "Decimator MD-HX or AJA Hi5-12G").

### Other resolver vocabulary

- `audio_output` (multi_enum): "Audio Output", "Headphone Output", "Salida de audio"
- `audio_input` (multi_enum): "Audio Input", "Microphone Input", "XLR Input", "Entrada de micrófono"
- `data_io` (multi_enum): "USB", "Ethernet", "Thunderbolt", "FireWire", "Genlock", "Timecode"
- `wireless_io` (multi_enum): "Wi-Fi", "Bluetooth", "NFC"
- `power_input` (enum): "Power", "DC Input", "Battery", "Battery Mount", "Tipo de batería", "Alimentación"
- `storage_media` (multi_enum): "Storage", "Memory Card", "Media", "Recording Media", "Tipo de tarjeta"
- `recording_codec` (multi_enum): "Recording Format", "Codec", "Video Codec", "Compression"

### Resolver vocabulary — ranges (synonyms)

- `distancia_focal` (rango, mm): "Focal Length", "Focal Length Range", "Distancia focal", "Focal", "mm range". If you see `"Min Focal: X, Max Focal: Y"` → consolidate to `"X-Y"`.
- `apertura` (rango, f/): "Aperture", "Maximum Aperture", "Aperture Range", "Diafragma", "f-stop", "f-stop range". For variable aperture zooms: `"f/2.8-4"`.
- `iso_rango` (rango): "ISO Range", "ISO Sensitivity", "Native ISO", "Sensibilidad ISO", "Dual Native ISO" (consolidate two values to range).
- `shutter_range` (rango, s): "Shutter Speed", "Shutter Speed Range", "Velocidad de obturación".
- `altura_rango` (rango, m or cm): "Min/Max Height", "Altura mín/máx", "Height Range" (for stands, tripods, light stands).

### Resolver vocabulary — physical attributes

- `resolucion_sensor` (wxh, px): "Resolution", "Effective Pixels", "Sensor Resolution", "Resolución".
- `dimensiones` (wxhxd, mm): "Dimensions", "Size", "Body Dimensions", "Dimensiones".
- `peso` (number, kg or g): "Weight", "Peso".
- `montura` (enum): "Mount", "Lens Mount", "Montura". Values: E, RF, EF, MFT, PL, F, L, X, K, Z.
- `formato_sensor` (enum, jerarquia): "Sensor Format", "Sensor Size", "Formato del sensor".

### Known adapters and their function

These adapters bridge specific incompatibilities. If two equipos can't talk directly, check if an adapter from this list (when present in the inventory) acts as a nexus:

- **Sigma MC-11** — EF → E mount (allows Canon EF lenses on Sony E-mount cameras)
- **Sigma MC-21** — EF → L mount
- **Metabones Speed Booster** — EF → MFT/E with 0.71x focal multiplier (also reduces vignetting in some cases)
- **Decimator MD-HX** — HDMI ↔ SDI bidirectional converter
- **AJA Hi5-12G** — HDMI 2.0 → SDI 12G converter (one-way)
- **Atomos AtomX SDI module** — adds SDI I/O to Atomos Ninja V monitor
- **V-Mount → Gold Mount adapter plate** — physical battery mount swap
- **D-Tap to LEMO/Sony NPF/etc.** — power cables (multiple variants)

When proposing `tipo='requiere_adaptador'` between two equipos, look in `contexto.equipos_disponibles` (or the global inventory snapshot) for an existing item that matches the role. If found, link via `adaptador_id`. If not, leave `adaptador_id=null` and explain in `nota` what adapter would be needed.

### Reasoning patterns for non-obvious cases

**Pattern: Camera + External recorder**
- Both must share at least one video output/input combination at compatible signal level.
- E.g.: Camera SDI 12G + Recorder SDI 12G ⇒ `compatible` (cable BNC).
- E.g.: Camera HDMI 2.0 4K60 + Recorder HDMI 2.0 4K60 ⇒ `compatible`.
- E.g.: Camera SDI only + Recorder HDMI only ⇒ `requiere_adaptador` (Decimator MD-HX or similar).

**Pattern: Camera + Lens via mount + sensor format**
- Determined by deterministic algorithm if both have `montura` and `formato_sensor` as drivers. Don't re-compute unless the deterministic says `sin_relacion`.

**Pattern: Light + Stand**
- Stand `capacidad_carga_kg` must be ≥ light `peso`. If `capacidad_carga_kg` not modeled, propose creating it as `number` spec for stands.

**Pattern: Battery + Camera/Light**
- `power_input` of the equipment must match `tipo_montura_bateria` of the battery (V-Mount, Gold, NP-F, etc.). If not present as a spec but evident from descriptions, propose the spec.

### Confidence thresholds

- Confidence ≥ 0.85: persist as `auto_generado=true` compat.
- Confidence 0.70–0.85: persist but flag in `razon_ia` that it's a heuristic guess.
- Confidence < 0.70: do NOT persist. Log it for the user.

---

## SECTION B — I/O Protocol (REPO-SPECIFIC)

This section is specific to the `tincho/rental` backend. If lifted to another repo, this section needs to be rewritten to match the new I/O contract.

### Backend endpoints used

Base URL: same host the user is running the backend on (typically `http://localhost:8000`). All endpoints require admin auth (the user's session — the skill runs as the user).

- `GET /api/admin/equipos/pendientes-compat?limit=N` — equipos that need analysis (queue consumer for `/gear-compat new`).
- `GET /api/admin/equipos/{id}/contexto-compat` — full payload for reasoning: nombre, marca, modelo, categorías, specs (con metadata de spec_definitions: tipo/unidad/enum_options/es_compatibilidad/modo/rol), ficha.raw_json (B&H scrape cache), compat_manuales existentes.
- `GET /api/admin/spec-definitions` — global spec catalog (for matching incoming labels).
- `POST /api/admin/compat/bulk` — write generated compatibilities. Body:
  ```json
  {
    "equipos_procesados": [int],
    "items": [
      {"equipo_a_id": int, "equipo_b_id": int, "tipo": "compatible|incompatible|requiere_adaptador",
       "nota": "string?", "adaptador_id": int?, "razon_ia": "string?", "confianza": 0.0..1.0?}
    ]
  }
  ```
  Backend deletes auto-generated compat for `equipos_procesados` first, then inserts. Manuals are never touched. Stamps `equipos.compat_analizado_at = now()`.
- `POST /api/admin/specs/proponer` — submit resolver findings as proposals. Body:
  ```json
  {
    "items": [
      {"tipo": "enum_option|spec_nueva|merge_specs",
       "payload": {...},
       "origen": "gear-compatibility skill v1",
       "confianza": 0.0..1.0}
    ]
  }
  ```
  Proposals queue for user approval — they DO NOT auto-apply.

### Payload shapes for proposals

**`enum_option`** — extend `enum_options` of an existing spec:
```json
{"spec_def_id": 47, "options": ["HDMI 2.0", "SDI 12G"], "razon": "encontrado en 3 equipos"}
```

**`spec_nueva`** — create a new spec_definition:
```json
{
  "spec_key": "capacidad_carga_kg",
  "label": "Capacidad de carga",
  "tipo": "number",
  "unidad": "kg",
  "enum_options": null,
  "ayuda": "Peso máximo soportado",
  "es_compatibilidad": false,
  "compatibilidad_modo": "exacta",
  "razon": "encontrado en 5 stands sin spec asignada",
  "categorias_sugeridas": ["Stands", "Tripodes"]
}
```

For ranges (focal length, ISO, etc.), `tipo` MUST be `"rango"` with a single spec — never propose two separate min/max specs. See Section A "Critical modeling rule".

**`merge_specs`** — consolidate duplicate specs:
```json
{
  "keep_spec_def_id": 12,
  "merge_spec_def_ids": [27, 31],
  "razon": "fps_max, max_framerate, frame_rate_max referencian el mismo concepto"
}
```

### Execution flow

Given the trigger, do the following:

#### For `/gear-compat <id_a> <id_b>`

1. `GET /api/admin/spec-definitions` → cache the global spec catalog (you need it for the resolver).
2. `GET /api/admin/equipos/{id_a}/contexto-compat` and `GET /api/admin/equipos/{id_b}/contexto-compat` in parallel.
3. Run the spec resolver/normalizer over `ficha.raw_json` of each equipo:
   - Identify keys not matched to any existing spec_def → candidates for `spec_nueva` proposals.
   - Identify values in `multi_enum`/`enum` that are not yet in `enum_options` → candidates for `enum_option` proposals.
   - Apply the modeling rule (Section A): rangos = single spec.
4. Reason about the pair using SECTION A patterns + raw_json + descriptions. Decide on a `tipo` and `nota`.
5. If you propose `requiere_adaptador`, search the inventory (you may need to GET /api/equipos with a query like `marca=Sigma` or `q=adapter` if not provided) for a matching adapter. Link via `adaptador_id` if found.
6. `POST /api/admin/compat/bulk` with `equipos_procesados=[id_a, id_b]` and `items=[result]` (single item).
7. `POST /api/admin/specs/proponer` if there are proposals.
8. Print a short summary to the user: overall verdict + key reasons + count of proposals queued.

#### For `/gear-compat new`

1. `GET /api/admin/equipos/pendientes-compat?limit=20` (start small — confirm with user before larger batches).
2. `GET /api/admin/spec-definitions` (once, cache).
3. For each pending equipo, follow the `<id_a> <id_b>` flow but pair it against all reasonable candidates from the inventory. "Reasonable" = same `categoria` group OR share at least one spec marked `es_compatibilidad=true` OR appear in the AV pattern (e.g., a camera should be paired with lenses, monitors, recorders, batteries — not with backdrops).
4. Aggregate all `items` and POST them in a single `compat/bulk` call when possible (batches of ~50 max).
5. Print summary.

#### For `/gear-compat all`

1. Confirm with the user: "This will analyze N equipos against the full inventory (~M pairs). Estimated cost: $X. Proceed?"
2. If confirmed, run `/gear-compat new` logic across the whole inventory in batches.
3. Print final summary with totals.

### Hard restrictions

- NEVER call backend write endpoints other than `POST /api/admin/compat/bulk` and `POST /api/admin/specs/proponer`.
- NEVER modify spec_definitions directly (no `POST/PATCH /api/admin/spec-definitions`). Always go through proposals.
- NEVER touch manual compatibilidades (`auto_generado=false`). The backend protects this but assume good faith too.
- NEVER persist compat with confidence < 0.70. Skip and log.
- For ranges, NEVER propose `_min` + `_max` specs. Single `tipo="rango"` only.
- If unsure, output the analysis as plain text for the user and ask before persisting. Quality > quantity.

### Output format to the user

After execution, print:

```
Gear Compatibility — analysis summary
─────────────────────────────────────
Equipos procesados: 12
Compat generadas:   34 (8 compatible, 4 con_crop, 15 parcial, 7 requiere_adaptador)
Saltadas (manual):  3
Skipped (low conf): 2

Propuestas IA pendientes de aprobación:
  - 5 nuevas opciones de enum (video_output: HDMI 2.0, SDI 12G, etc.)
  - 2 specs nuevas sugeridas (capacidad_carga_kg, tipo_montura_bateria)
  - 1 merge sugerido (fps_max ← max_framerate + frame_rate_max)

Revisalas en /admin/specs/propuestas para aprobar/descartar.
```

## Auto-mejora (correr al cerrar cada uso)

Preguntate, crítico: ¿alguna regla me desorientó o quedó vieja porque el repo cambió? ¿pegué un
gotcha que merece ser "caso testigo"? ¿overlap con otro skill? ¿repetí a mano un paso que debería
estar codificado acá?

Si **SÍ** → anotá la propuesta en [`docs/PROPUESTAS_SKILLS.md`](../../../docs/PROPUESTAS_SKILLS.md)
(formato: `fecha · skill · qué cambiar · por qué`). Proponés, no aplicás — el dueño aprueba, igual
que la memoria; el supervisor puede validar.

Si **NO** → no fabriques churn. **Honestidad > actividad.**
