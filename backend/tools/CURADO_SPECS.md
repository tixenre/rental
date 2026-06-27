# Curado de specs — canon de la industria vs. visibilidad web

> **Qué es esto.** Curado de los labels que B&H trae por categoría, clasificados en tiers de
> visibilidad (qué se muestra en la web/IG vs. qué se guarda interno). Es el insumo para:
> (a) qué specs/aliases agregar al registry (`specs/categorias/*.py`), y (b) cómo defaultear
> `visible_web` cuando se construya el Stream B (extras por-equipo en `equipo_fichas`).
>
> **Método.** Curado por un LLM (criterio de dominio audiovisual) sobre el dataset real de HTMLs
> (`tests/fixtures/html/dataset/`), cruzado con el registry actual. **Propone — el dueño aprueba.**
> Determinístico el extractor; el curado es offline, no toca el runtime.
>
> **Estado:** muestra inicial sobre 5 HTMLs (2 cámaras, 2 lentes, 1 adaptador). Se amplía con el
> dataset completo. Tracking: #1072.

## Hallazgo central

| Categoría | Cómo extrae hoy | Rinde? | Dónde aporta el curado |
| --- | --- | --- | --- |
| **Cámaras** | parser dedicado (`camaras_parser`) | ✅ 29–41 specs canon, ruido ya afuera | marginal — alguna spec menor + clasificar visibilidad |
| **Lentes** | parser dedicado (`lentes_parser`) | ✅ 15 specs canon | marginal |
| **Adaptadores** | ⚠️ **cae en genérico** (detección rota) → alias-index (solo 2 specs) | ❌ specs crudas en inglés | **alto** — fix detección + specs + aliases |
| **Ruido (todas)** | se descarta (no entra a la ficha) | — | guardar con `visible_web=false` (Stream B) |

**Conclusión:** el motor ya es bueno para el grueso del catálogo (cámaras/lentes). Las 3 palancas
reales son: (1) arreglar adaptadores, (2) guardar-no-descartar el ruido con visibilidad off,
(3) clasificar qué specs canon son destacadas (web/IG) vs. ficha.

---

## Tiers de visibilidad (definición)

- **T1 · DESTACADA** → `favorito=true`. Aparece en card pública + quick-facts + candidata a post IG.
- **T2 · FICHA** → pública en la ficha extendida, no destacada.
- **T3 · INTERNA** → `visible_web=false`. Se guarda (rigging, I/O detallado, condiciones) pero no se muestra al cliente.
- **T4 · PACKAGING/RUIDO** → extras `visible_web=false`, nunca candidata a público (peso/dimensiones de la caja de envío).

Estado vs. registry: `✓` ya capturado · `+alias` existe la spec, falta el alias de B&H · `⚠ falta` no existe la spec.

---

## Cámaras

Parser dedicado ya captura las T1/T2. El curado acá es sobre todo **clasificar visibilidad** y
sumar aliases al registry para reforzar el path genérico (por si una cámara no dispara el parser).

### T1 — Destacada (web/IG)
| Label B&H | spec_key | Estado |
| --- | --- | --- |
| Image Sensor | `formato` | +alias (`Image Sensor`) |
| Lens Mount | `lens_mount` | +alias (`Lens Mount`) |
| Max Video Resolution / Resolution | `resolucion_max` | ✓ |
| Frame Rate | `fps_max` | ✓ |
| Effective Sensor Resolution | `megapixels` | +alias (`Effective Sensor Resolution`) |
| ISO/Gain Sensitivity | `iso_nativo`/`iso_extendido` | +alias |
| Advertised Dynamic Range | `rango_dinamico_stops` | +alias (`Advertised Dynamic Range`) |
| Gamma Curve | `gamma_curve` | +alias (`Gamma Curve`) |
| Built-In ND Filter | `built_in_nd` | +alias (`Built-In ND Filter`) |
| Netflix Approved | `netflix_approved` | +alias (`Netflix Approved`) |

### T2 — Ficha
| Label B&H | spec_key | Estado |
| --- | --- | --- |
| Image Stabilization | `estabilizacion` | ✓ |
| Capture Type | `capture_type` | +alias |
| Shutter Type | `shutter_type` | ✓ |
| Shutter Speed | `shutter_speed` | +alias |
| Media/Memory Card Slot | `media_card_slots` | +alias |
| Internal Recording | `internal_recording` | +alias |
| Codecs / Max Recording Modes | `codecs` | +alias (`Max Recording Modes`) |
| Battery | `battery` | +alias (`Battery`) |
| Weight | `peso_g` | ✓ |
| Dimensions (W x H x D) | `dimensions_mm` | +alias |
| Display Type | `display_type` | +alias |
| Lens Communication | `lens_communication` | +alias |
| Fast-/Slow-Motion Support | `fast_slow_motion` | +alias |
| Audio Recording | `audio_recording` | +alias |
| Built-In Microphone | `built_in_microphone` | +alias |
| IP Streaming | `ip_streaming` | +alias |
| Wireless / Mobile App Compatible | `wireless`/`mobile_app_compatible` | +alias |
| White Balance | `white_balance` | +alias |
| Materials | `materials` | +alias |

### T3 — Interna (visible_web=false)
| Label B&H | spec_key | Nota |
| --- | --- | --- |
| Video I/O / Audio I/O / Power I/O / Other I/O | `video_io`/`audio_io`/`power_io`/`other_io` | conectividad detallada — útil interno |
| Tripod Mount / Shoe Mount / Accessory Mounting Thread | `tripod_mount`/`shoe_mount`/⚠ | rigging |
| Power Consumption | `consumo_w` | ✓ (interno/logística) |
| Operating Conditions / Storage Conditions | `operating_conditions`/⚠ | ambiente |
| Focus Mode / Autofocus Points | ⚠/`focus_points` | técnico |
| Internal Storage / Internal Filter Holder / Built-In CC Filter | `internal_storage`/`internal_filter_holder`/`built_in_cc` | +alias |
| GPS / Signal-to-Noise Ratio | `gps`/⚠ | técnico |

### T4 — Packaging/Ruido
`Package Weight`, `Box Dimensions (LxWxH)`, `Type` (= "Optional, Not Included"), `Resolution` (cuando es de pantalla). → extras, nunca público.

---

## Lentes

Parser dedicado captura las T1/T2. Registry de lentes (17 specs) ya cubre lo esencial.

### T1 — Destacada
| Label B&H | spec_key | Estado |
| --- | --- | --- |
| Focal Length | `distancia_focal` | ✓ |
| Aperture | `apertura` | ✓ |
| Lens Mount | `lens_mount` | ✓ |
| Lens Format Coverage | `formato` | +alias (`Lens Format Coverage`) |
| Filter Size | `diametro_filtro` | ✓ |

### T2 — Ficha
| Label B&H | spec_key | Estado |
| --- | --- | --- |
| Angle of View | `angulo_vision` | ✓ |
| Minimum Focus Distance | `distancia_minima_cm` | +alias (`Minimum Focus Distance`) |
| Magnification | `magnificacion` | +alias (`Magnification`) |
| Optical Design | `construccion_optica` | +alias (`Optical Design`) |
| Aperture/Iris Blades | `hojas_diafragma` | +alias (`Aperture/Iris Blades`) |
| Image Stabilization | `estabilizacion` | ✓ |
| Focus Type | `autofocus` | +alias (`Focus Type`) |
| Weight | `peso_g` | ✓ |
| Dimensions | `dimensions_mm` | +alias (`Dimensions`) |

### T4 — Packaging/Ruido
`Package Weight`, `Box Dimensions (LxWxH)`. → extras.

---

## Adaptadores ⚠️ (la palanca real)

**Bug primero:** `_detect_categoria` no reconoce "Canon Mount Adapter EF-EOS R" como adaptador
(la regex exige `lens mount adapter`; el título dice solo "Mount Adapter"). Cae en genérico y el
registry de adaptadores tiene solo 2 specs → la mitad sale cruda en inglés. **Fix:** ampliar la
regex a `\b(mount\s+adapter|lens\s+adapter|mount\s+converter|speed\s?booster)\b`.

Specs canon de adaptadores (a sumar al registry de la categoría):
| Label B&H | spec_key propuesta | Tier | Estado |
| --- | --- | --- | --- |
| Lens Compatibility | `lens_mount_in` (montura entrada) | T1 | ⚠ falta/revisar |
| Camera Compatibility | `lens_mount_out` (montura salida) | T1 | ⚠ (sale crudo `camera_compatibility`) |
| Magnification | `magnification` (0.71x = focal reducer) | T1 | ⚠ falta como canon |
| Exposure Change | `exposure_change` (1-Stop Light Gain) | T2 | parcial |
| Electronic Communication | `electronic_communication` | T2 | ⚠ (sale crudo) |
| Materials | `materials` | T3 | ✓ |
| Item Type | — | T4 | ruido |
| Package Weight / Box Dimensions | — | T4 | packaging |

---

## Acciones derivadas (para #1072)

1. **Fix detección de adaptadores** — 1 línea de regex en `_detect_categoria`. Alto impacto.
2. **Aliases de cámaras/lentes** — el bloque `+alias` de arriba al registry. Refuerza el path genérico (las cámaras que no disparen el parser dedicado).
3. **Registry de adaptadores** — sumar las specs canon de la tabla de adaptadores.
4. **Stream B (extras por-equipo)** — para que T3/T4 se *guarden* con `visible_web=false` en vez de descartarse. Default por tier: T1→favorito, T2→ficha, T3/T4→`visible_web=false`.
5. **Limpieza del `modelo`** — el título entra con sufijo del sitio (`… B&H Photo VideoAccessibility`); limpiar en el parser. Afecta todo el catálogo.
