# Dataset de Luces — Guía y Convenciones

Fuente fundamental para construir el catálogo de iluminación en la web.
**16 productos curados** (LED + tungsteno + flash) con specs comparables y
ficha técnica completa.

Archivos:
- `docs/iluminacion_dataset.json` — fuente de verdad (specs + extras + ficha + image)
- `docs/iluminacion_raw.json` — raw del scrape original (auditoría)
- `tools/iluminacion_parser.py` — extractor desde HTMLs B&H (DOM + JSON-LD)
- `tools/iluminacion_patches.py` — overrides manuales para productos no parseables
- `tools/iluminacion_normalizar.py` — canonicaliza marcas/modelos/IDs
- `tools/iluminacion_rebuild.sh` — pipeline completo (rm → parse → patch → normalize)

## Estructura por producto

```json
{
  "marca": "Aputure",               // canónica (ver lista abajo)
  "modelo": "NOVA II 2x1",          // limpio, sin "LED Light Panel" etc.
  "url_source": "https://...",      // canonical product URL
  "image_url": "https://...",       // imagen principal del producto
  "specs": { ... },                 // 11+ campos comparables/filtrables
  "extras": { ... },                // ~20 campos ficha técnica
  "ficha": { ... }                  // raw B&H secciones (todo lo que vino)
}
```

## `specs` — campos comparables

| Campo | Tipo | Cobertura | Notas |
|---|---|---|---|
| `tipo` | enum | 100% | Flash / Bulb-Lamp / Panel / Tube Light / Flexible Mat / Monolight / COB Monolight / Fresnel |
| `potencia_w` | int (W) | 94% | Falta solo en flash (usa Guide Number) |
| `lumens_at_5600k` / `lumens_at_3200k` | int (lm) | 25% | Pocos fabricantes publican lúmenes totales |
| `lux_at_1m_5600k` / `lux_at_1m_3200k` | int (lx) | 50% | Estándar cine. Más común que lumens en B&H |
| `cri` | int (0-100) | 94% | Color Rendering Index |
| `tlci` | int (0-100) | 63% | Broadcast standard |
| `r9` | int (0-100) | 0% | Deep red — pocos lo publican |
| `temperatura_k` | `{min, max}` | 94% | Si fijo: `{min:3200, max:3200}` |
| `color_modes` | array enum | 100% | RGB / Daylight / Tungsten / HSI |
| `dimming` | bool | 100% | |
| `control_inalambrico` | array enum | 63% | Bluetooth / DMX / RDM / Wi-Fi / CRMX / Lumenradio |
| `alimentacion` | array enum | 100% | AC / V-mount / NP-F / D-Tap / USB-C / Batería integrada |
| `montaje` | enum | 81% | Bowens / Propietario / Fresnel / Profoto / Elinchrom |
| `peso_g` | int (g) | 100% | UI computa kg/lb |

## `extras` — ficha técnica

Campos opcionales pero útiles. Los más relevantes:

- `beam_angle`: `{min, max}` en grados
- `noise_db`: `{silent, medium, high}` para luces con fan modes
- `cooling`: `Fan` / `Passive`
- `ip_rating`: `IP54`, `IP65`, etc.
- `dimensiones_cm`: `{largo_cm, ancho_cm, alto_cm}`
- `has_display` + `display_type`: bool + LCD/OLED/LED
- `app_compatible` + `app_platforms`: bool + [Android, iOS]
- `tm30_rf` / `tm30_rg` / `ssi`: métricas modernas de color
- `photometrics_full`: array de líneas con todas las temps × ángulos × modificadores
- `wireless_range_m`, `voltaje_v`, `vida_util_h`: numéricos
- `included_accessories`: array de modificadores que vienen con el producto
- `io`: array de I/O ports (XLR, USB-C DMX, powerCON, etc.)

## Convenciones

**IDs**: `{marca}_{modelo}` snake_case
- `aputure_nova_ii_2x1`, `godox_vl300ii`, `nanlite_forza_500`, `nanlite_forza_60b`

**Marcas canónicas** (case-sensitive):
- `Amaran` (amaran en lowercase oficial pero capitalizado por consistencia)
- `ARRI` (mayúsculas)
- `Aputure`
- `Godox`
- `Mole-Richardson` (con guión)
- `Nanlite`

**Unidades**:
- Métrico primero como base de DB (g, cm, m, W, K)
- Imperial: la UI lo computa desde la base métrica
- Excepciones imperial-native: pin sizes (5/8" stud), accessory diameters de Fresnels (6.6")

**Ausencia de datos**:
- `null` o campo ausente = "no aplica" o "no publicado"
- NO usar strings como `"N/A"`, `"None"`, `"—"` — el parser ya los filtra

## Cómo agregar una luz nueva

1. Guardar la página B&H del producto:
   ```
   Browser → Cmd+S → "Webpage, Complete" → ~/Desktop/Paginas/Inventario/
   ```

2. Si NO está en B&H (manufacturer-only como ARRI):
   - Buscar su spec sheet oficial
   - Agregar entrada manual en `tools/iluminacion_patches.py`

3. Agregar la ruta del HTML en `tools/iluminacion_rebuild.sh`

4. Correr el pipeline:
   ```bash
   bash tools/iluminacion_rebuild.sh
   ```

5. Verificar en `docs/iluminacion_dataset.json` que:
   - Marca aparece en la lista canónica (sino, agregar a `BRAND_CANON` en `iluminacion_normalizar.py`)
   - Modelo está limpio (sin "LED Light", "(Gray)", SKUs duplicados)
   - `tipo` está bien clasificado
   - `color_modes` matchea lo real
   - Specs numéricos están como número, no string

## Decisiones de schema explicadas

**¿Por qué `color_modes` array en vez de `bicolor`/`rgb` bools?**
- Matchea 1:1 con B&H "Color Modes: RGB, Daylight, Tungsten"
- Extensible (HSI, GM Shift, modos nuevos)
- Bicolor y RGB son **derivables** en la UI:
  ```js
  const isBicolor = modes.includes("Daylight") && modes.includes("Tungsten")
  const isRGB = modes.includes("RGB")
  ```

**¿Por qué `temperatura_k: {min, max}` en vez de string?**
- Permite filtrar por rango (ej. "luces que cubran 3200K")
- Si es fijo, `min == max` (ej. ARRI tungsteno: `{min:3200, max:3200}`)
- En DB se puede serializar como `"1800-20000"` (tipo `rango` que el proyecto ya soporta)

**¿Por qué `peso_g` y no `{kg, lb}`?**
- Una sola fuente de verdad numérica. UI computa la display.
- Sortable y filtrable directamente.

**¿Por qué `noise_db: {silent, medium, high}`?**
- Las luces con fan tienen varios modos
- Un único número engañaría (¿silent o high?)

**¿Por qué `image_url` y no array de imágenes?**
- Por ahora la imagen principal alcanza para el catálogo
- Si más adelante se necesita galería, se cambia a array sin breaking change
  (mover string → array es trivial)

## Mapeo a la DB del proyecto

```sql
-- spec_definitions (catálogo global)
INSERT INTO spec_definitions (spec_key, label, tipo, unidad, enum_options)
VALUES
  ('tipo',           'Tipo',                'enum',       NULL, '["Flash","Panel","Monolight",...]'),
  ('potencia_w',     'Potencia',            'number',     'W',  NULL),
  ('lumens_at_5600k','Lúmenes a 5600K',     'number',     'lm', NULL),
  ('cri',            'CRI',                 'number',     NULL, NULL),
  ('tlci',           'TLCI',                'number',     NULL, NULL),
  ('temperatura_k',  'Temperatura color',   'rango',      'K',  NULL),
  ('color_modes',    'Modos de color',      'multi_enum', NULL, '["RGB","Daylight","Tungsten","HSI"]'),
  ('control_inalambrico','Control inalámbrico','multi_enum', NULL, '["Bluetooth","DMX","RDM","Wi-Fi","CRMX","Lumenradio"]'),
  ('alimentacion',   'Alimentación',        'multi_enum', NULL, '["AC","V-mount","NP-F","D-Tap","USB-C","Batería integrada"]'),
  ('peso',           'Peso',                'number',     'g',  NULL);

-- categoria_spec_templates (asignación a categoría Iluminación)
INSERT INTO categoria_spec_templates (categoria_id, spec_def_id, prioridad, visible_en_card, visible_en_filtros, visible_en_nombre)
VALUES
  (Iluminación, tipo,          10,  true, true, true),
  (Iluminación, potencia_w,    20,  true, true, true),
  (Iluminación, cri,           30,  true, true, false),
  (Iluminación, temperatura_k, 40,  true, true, false),
  (Iluminación, color_modes,   50,  true, true, false),
  ...

-- equipo_specs (valores por equipo)
INSERT INTO equipo_specs (equipo_id, spec_def_id, value) VALUES
  (NOVA_II_id, tipo_id,            'Panel'),
  (NOVA_II_id, potencia_w_id,      '1000'),
  (NOVA_II_id, cri_id,             '95'),
  (NOVA_II_id, temperatura_k_id,   '1800-20000'),  -- formato rango
  (NOVA_II_id, color_modes_id,     '["RGB","Daylight","Tungsten"]'),  -- JSON array
  ...
```

Cuando llegue el momento de importar a la DB, escribir
`backend/seeds/seed_iluminacion_from_dataset.py` que lee el JSON y hace los INSERTs.
