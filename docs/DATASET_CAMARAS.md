# Dataset de Cámaras — Guía y Convenciones

Sigue el mismo patrón que `DATASET_ILUMINACION.md`. Esta doc registra solo lo
específico de cámaras; las convenciones cross-cutting (IDs, unidades, ausencia
de datos, etc.) están en el manifiesto.

Archivos:
- `docs/camaras.json` — fuente de verdad (specs + extras + ficha + image)
- `docs/camaras_raw.json` — raw del scrape (auditoría)
- `tools/camaras_parser.py` — extractor (DOM + JSON-LD)
- `tools/camaras_patches.py` — overrides manuales (vacío inicialmente)
- `tools/camaras_normalizar.py` — canonicaliza marcas/modelos/IDs
- `tools/camaras_rebuild.sh` — pipeline completo

## `specs` — campos comparables

| Campo | Tipo | Cobertura | Notas |
|---|---|---|---|
| `tipo` | enum | 100% | Cinema Camera / Mirrorless / DSLR / Vlogging / Action Camera / Compact / Medium Format |
| `lens_mount` | enum | 100% | E / RF / EF / L / Z / X / MFT / PL / BMD / B4 / Fixed (action) |
| `formato` | enum | 100% | Full-frame / Super 35 / APS-C / MFT / Medium Format / 1" |
| `resolucion_max` | enum | 100% | FHD / 2K / 4K / 5K / 5.7K / 6K / 8K / 12K |
| `fps_max` | int (fps) | 100% | Max frame rate en cualquier res |
| `megapixels` | float (MP) | 100% | Effective sensor resolution |
| `codecs` | string | 100% | Lista compacta: "REDCODE RAW, ProRes 4444", "XAVC S-I 4:2:2, H.265 HEVC" |
| `iso_nativo` | `{min, max}` | parcial | Rango ISO sin boost |
| `iso_extendido` | `{min, max}` | parcial | Rango con boost activado |
| `rango_dinamico_stops` | int (stops) | parcial | Latitud declarada por fabricante |
| `estabilizacion` | bool | 100% | IBIS/sensor-shift presente |
| `autofocus` | bool | 100% | |
| `netflix_approved` | bool | parcial | Solo cinema-tier |
| `peso_g` | int (g) | 100% | Body only, sin batería ni media |

## `extras` — ficha técnica

Campos opcionales descriptivos:
- `sensor`: "Full-Frame — 10.2 Megapixel"
- `tipo_estabilizacion`: "Sensor-Shift" / "Optical IBIS"
- `af_puntos`: int (phase + contrast detection)
- `memoria_tipo`: "Dual Slot: CFexpress Type A / SDXC"
- `salida_video`: "HDMI Type-A, 12G-SDI"
- `audio_io`, `power_io`, `other_io`: arrays de puertos
- `bateria`: "NP-FZ100" / "BP-A30N"
- `consumo_w`: float (W)
- `pantalla`, `visor_evf`, `shutter_type`, `shutter_speed`
- `white_balance`, `gamma_curve`, `bit_depth`, `aspect_ratio`
- `dimensiones_cm`: `{largo_cm, ancho_cm, alto_cm}`
- `tripod_mount`, `shoe_mount`, `built_in_nd`
- `materiales`, `operating_temp`
- `wireless`, `app_compatible_raw`

## Sub-categorías (taxonomía de catálogo)

Estructura de 2 niveles, **multi-categorización M2M** (un equipo en N categorías):

```
Cámaras
├─ Foto                      — DSLRs, Medium Format, híbridas que también disparan stills
├─ Video                     — contenedor (sin productos directos)
│   ├─ Montura E             — Sony cinema/mirrorless (FX3A, FX6/9/30, a7V, a7S, ZV-E1)
│   ├─ Montura RF            — Canon R + RED KOMODO RF
│   ├─ Montura EF            — Canon EF cine (C200, C300, etc.)
│   ├─ Montura L             — Panasonic S, Sigma fp, Leica
│   ├─ Montura Z             — Nikon Z
│   ├─ Montura PL            — cine PL (Alexa, Sony Venice, RED PL)
│   └─ Montura BMD           — Blackmagic Pocket
└─ Acción                    — GoPro, Insta360, DJI Action
```

**Decisiones de diseño:**

1. **Video sub-divide por MONTURA** (no por form factor) — el cliente cine busca
   "necesito una cámara que use mis lentes Sigma EF" o "tengo lentes Sony E".
   La montura es el criterio #1 de compatibilidad práctica.

2. **Multi-categorización** — equipos pueden estar en N categorías a la vez
   (`equipo_categorias` ya es M2M en el schema). Las híbridas tipo Sony a7V
   aparecen en **Foto + Video/Montura E** porque sirven para los dos casos.

3. **"Video" es parent intermedio** — sin productos directos, solo agrupa
   sub-categorías de montura. El cliente entra a Video y ve cuáles montaras
   están disponibles en el inventario.

Lógica en `seeds/camaras.py::categorize()`:

| tipo (del producto) | Aparece en |
|---|---|
| `Action Camera` | `["Acción"]` |
| `DSLR` / `Medium Format` / `Compact` | `["Foto", "Montura {X}"]` si tiene mount |
| `Cinema Camera` | `["Montura {X}"]` solo (no Foto) |
| `Mirrorless` / `Vlogging` / default | `["Foto", "Montura {X}"]` |

Donde `{X}` es el `lens_mount` del producto.

**Ejemplo distribución actual:**

```
Foto (2):           Sony a7V, Sony ZV-E1
Video / Montura E (3):   Sony FX3A, Sony a7V, Sony ZV-E1
Video / Montura RF (1):  RED KOMODO-X
Video / Montura EF (1):  Canon EOS C200
Acción (1):         GoPro HERO12 Black
```

Notar que **a7V y ZV-E1 aparecen 2 veces** (Foto + Video/Montura E) — es lo
esperado para híbridas. El catálogo muestra un equipo único pero filtrable
desde ambas categorías.

## Marcas canónicas

`Sony`, `Canon`, `Nikon`, `Panasonic`, `Fujifilm`, `OM System`, `Leica`,
`Hasselblad`, `Blackmagic Design`, `RED`, `ARRI`, `Z CAM`, `Kinefinity`,
`GoPro`, `DJI`, `Insta360`.

Definidas en `tools/camaras_normalizar.py::BRAND_CANON`.

## Workflow para agregar 1 cámara nueva

**Sin Claude** (mismo flow que luces, una vez wireado el endpoint):
1. En B&H: Cmd+S → "Webpage, Complete" → `~/Desktop/Paginas/Camaras/`
2. En `/admin/equipos` → Auto-completar → "Subir HTML guardado"
3. Form se llena con specs canónicos

NOTA: hoy el endpoint `/admin/equipos/autocompletar-from-html` está cableado
solo a `iluminacion_html_extractor`. Para que también funcione con cámaras,
falta extender el extractor a un dispatcher por categoría (TODO).

**Con Claude** (categoría nueva, refactor):
- Bulk inicial: igual que luces, usar `tools/camaras_rebuild.sh`
- Cuando entre una cámara que el parser no maneja, agregar override en
  `tools/camaras_patches.py`

## Decisiones específicas de cámaras

**¿Por qué `lens_mount` es enum con `"Fixed (action)"`?**
Las action cameras (GoPro) no tienen lens mount intercambiable — el lente
es fijo y solidario al body. En vez de `null` (que sería ambiguo con "no se
detectó"), usamos un valor enum explícito.

**¿Por qué `iso_nativo` y `iso_extendido` separados?**
Los DPs piden ISO nativo (base sensitivity sin boost) cuando comparan ruido.
El extendido (boost) es marketing. Conservar ambos permite filtrar por uno.

**¿Por qué `fps_max` como int global, no por resolución?**
La info de "fps a 4K vs fps a 2K vs fps a FHD" vive en `ficha` raw. Para
filtros del catálogo, el FPS máximo absoluto es la métrica útil (filtrar
"cámaras que graban ≥120fps").

**¿Por qué `peso_g` int en gramos?**
Single source of truth numérico. UI computa kg / lb según preferencia.

## Lo que NO se mapea (queda en `ficha` raw)

- Detalle de Internal Recording per-codec (qué codec a qué res a qué fps)
- White balance presets completos
- Gamma curves disponibles (S-Log 3, V-Log, etc.) — solo se guarda el primero
- Specs físicos detallados como diopter range, eye point, magnification (solo si hay viewfinder)
- Box / packaging dimensions

Todo eso está en `ficha` para renderizar la página de detalle del producto,
no se usa para filtrar/comparar.
