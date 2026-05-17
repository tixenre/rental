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

```
Cámaras
├─ Cinema      (FX3A, KOMODO-X, C200)
├─ Mirrorless  (a7V)
├─ Vlogging    (ZV-E1)
├─ Action      (HERO12)
├─ DSLR        (futuro)
└─ Medium Format (futuro)
```

Lógica de categorización: `seeds/camaras.py::categorize()` mapea por `tipo`:
- `Cinema Camera` → Cinema
- `Mirrorless` → Mirrorless
- `Vlogging` → Vlogging
- `Action Camera` → Action
- Fallback → Mirrorless

## Marcas canónicas

`Sony`, `Canon`, `Nikon`, `Panasonic`, `Fujifilm`, `OM System`, `Leica`,
`Hasselblad`, `Blackmagic Design`, `RED`, `ARRI`, `Z CAM`, `Kinefinity`,
`GoPro`, `DJI`, `Insta360`.

Definidas en `tools/camaras_normalizar.py::BRAND_CANON`.

## Workflow para agregar 1 cámara nueva

**Sin Claude** (mismo flow que luces, una vez wireado el endpoint):
1. En B&H: Cmd+S → "Webpage, Complete" → `~/Desktop/Paginas/Camaras/`
2. En `/admin/equipos` → ✨ Auto-completar → "Subir HTML guardado"
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
