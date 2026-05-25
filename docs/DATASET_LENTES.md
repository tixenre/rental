# Dataset de Lentes + Adaptadores + Filtros — Guía y Convenciones

Mismo patrón que `DATASET_ILUMINACION.md` y `DATASET_CAMARAS.md`. Las convenciones
cross-cutting (IDs, unidades, ausencia de datos) están en `docs/SISTEMA_SPECS.md` §2.

**Particularidad de este dataset:** una sola carpeta de HTMLs
(`~/Desktop/Paginas/Lentes/`) genera **TRES datasets** porque corresponden a
**TRES categorías raíz** independientes (cada una con sus specs nativos):

- `docs/lentes.json` → categoría "Lentes" (12 productos)
- `docs/adaptadores.json` → categoría "Adaptadores" (4 productos) — se vinculan a la **cámara** (lens_mount body)
- `docs/filtros.json` → categoría "Filtros" (4 productos) — se vinculan al **frente del lente** (diametro_mm)

El parser clasifica cada HTML por heurística (presencia de `Aperture`/`Focal
Length` → lente; `Item Type: Lens Mount Adapter` → adaptador; `Filter Type` →
filtro). En el menú del catálogo público las tres categorías se **agrupan
visualmente bajo "Óptica"** (ver `CategorySidebar.tsx`), pero en el modelo de
datos siguen siendo categorías independientes con specs distintos.

**Por qué Adaptadores ≠ Filtros (categorías raíz separadas):**

- Un **adaptador** se vincula a la cámara — su spec primario es `lens_mount`
  (lado body) y `lens_mount_out` (lado lente). Especificaciones: electrónica,
  iris incluido, magnificación (speedbooster).
- Un **filtro** se vincula al frente del lente — su spec primario es
  `diametro_mm`. Especificaciones: densidad ND, material, grado de difusión.

Forzar un schema único llenaba de campos vacíos cada equipo. Categorías
separadas → specs nativos y limpios.

## Archivos

- `docs/lentes.json` / `_raw.json` — lentes curados + raw
- `docs/adaptadores.json` / `_raw.json` — adaptadores curados + raw
- `docs/filtros.json` / `_raw.json` — filtros curados + raw
- `tools/lentes_parser.py` — extractor B&H (DOM + JSON-LD); detecta eBay y los saltea; emite los 3 buckets
- `tools/lentes_patches.py` — overrides manuales (Zeiss vintage M42 desde eBay)
- `tools/lentes_normalizar.py` — canoniza marcas/modelos/IDs/extras; normaliza los 3 JSONs
- `tools/lentes_rebuild.sh` — pipeline completo (parse → patch → normalize)
- `backend/seeds/lentes.py` — seed de Lentes (sub-cats por tipo + monturas on-the-fly)
- `backend/seeds/adaptadores.py` — seed de Adaptadores (sub-cats por montura body)
- `backend/seeds/filtros.py` — seed de Filtros (sub-cats por diámetro)

## `specs` de Lentes — 15 campos comparables

| Campo | Tipo | Cobertura | Notas |
|---|---|---|---|
| `lens_mount` | enum | 100% | E / RF / EF / L / Z / X / MFT / PL / BMD / B4 / M42 |
| `distancia_focal` | **list[mm]** | 100% | `[50]` fijo · `[24, 70]` zoom |
| `apertura` | **list[f-stop]** | 100% | `[2.8]` fija · `[2.8, 4]` variable |
| `formato` | enum | 100% | Full-frame / APS-C / Super 35 / MFT / Medium Format |
| `diametro_filtro` | int (mm) | parcial | Rosca front (67 / 77 / 82); algunos lentes usan filtros rear |
| `linea` | string | parcial | Art / GM / GM II / L / Cinema / Probe / Pancolar / Flektogon |
| `angulo_vision` | list[°] | 100% | `[63.4]` fijo · `[34, 84]` zoom (orden ascendente) |
| `distancia_minima_m` | float (cm) | 100% | El nombre dice "m" pero la unidad real es cm — legacy |
| `magnificacion` | string | parcial | Ej. "0.32x" |
| `hojas_diafragma` | int | 100% | Cantidad de hojas del iris |
| `estabilizacion` | bool | 100% | OSS/IS/OS/VC presente |
| `autofocus` | bool | 100% | False = manual focus only (todos los vintage M42) |
| `construccion_optica` | string | 100% | "20 elementos / 15 grupos" |
| `peso_g` | int (g) | 100% | Lente solo, sin caps ni hood |
| `dimensiones` | string | 100% | "Ø87.8 × 119.9 mm" |

**Convención de rangos**: `distancia_focal` y `apertura` son **listas**. Un solo
elemento = valor fijo. Dos elementos = rango (zoom o apertura variable). Esto
permite uniformizar fijos y zooms en el mismo campo (que era el bug que cerramos
en el pre-audit). El render template lee la lista y elige `"50mm"` vs `"24-70mm"`.

## `specs` de Adaptadores — 7 campos

| Campo | Tipo | Notas |
|---|---|---|
| `tipo` | enum | Adaptador montura / Speedbooster / Macro tube |
| `lens_mount` | enum | Lado body (cámara) — E/RF/EF/L/Z/X/MFT/PL/BMD/B4/M42 |
| `lens_mount_out` | enum | Lado lente (otro sistema). Ej. Sigma MC-11: `lens_mount=E, lens_mount_out=EF` |
| `electronica` | bool | Transmite AF/aperture del lente al body |
| `incluye_iris` | bool | Drop-In adapters con filtro ND variable interno (Canon EF→RF) |
| `magnificacion` | string | Solo speedboosters (ej. "0.71x" reduce focal y gana 1 stop) |
| `peso_g` | int (g) | Cuando B&H lo lista |

## `specs` de Filtros — 6 campos

| Campo | Tipo | Notas |
|---|---|---|
| `tipo` | enum | Filtro ND / polarizador / UV / variable / difusión |
| `diametro_mm` | int (mm) | Obligatorio — define la sub-cat (82mm, 77mm, etc.) |
| `densidad` | string | Solo ND/variable. Ej. "1.2-Stop", "2 to 8-Stop" |
| `material` | enum | Vidrio / Resina / Polímero |
| `grade` | string | Solo difusión: 1/8, 1/4, 1/2, 1, 2 (más alto = más difusión) |
| `peso_g` | int (g) | Cuando B&H lo lista |

## Sub-categorías

### Lentes (raíz)
```
Lentes
├─ Zoom        — Sony GM (12-24, 24-70 II, 70-200 II) + Sigma Art (18-35, 24-70) + Canon 70-200 L
├─ Fijos       — Sigma 35 Art, Sigma 50 Art, Laowa 24 Probe (multi-cat con Especiales)
├─ Vintage     — Zeiss Jena M42 (Pancolar 50, Flektogon 35, Sonnar 135)
└─ Especiales  — Laowa Probe (multi-cat) + reservada para cinema PL / anamorphic / macro
```

**Diseño**: 4 sub-cats por **tipo de lente** (no por montura). La montura se filtra
con el spec `lens_mount` en el sidebar — así un cliente que tiene cuerpo E filtra
Zoom + montura E para ver solo los compatibles. Esto evita el problema de
sub-cats que mezclaban criterios (`Zoom EF` vs `Zoom E-mount`) y deja huecos
para monturas futuras (L, RF, Z) sin tocar la taxonomía.

Lógica en `seeds/lentes.py::categorize_lente()`:

| Condición | Sub-cats |
|---|---|
| `lens_mount = M42` | Vintage |
| zoom (focal con rango) | Zoom |
| fijo | Fijos |
| + `linea` contiene "probe", "macro", "cinema", "master prime" | + Especiales (multi-cat) |

Una lente con `linea="Probe"` o `"Cinema"` aparece en **ambas**: su tipo (Zoom o
Fijos) Y Especiales — descubrible desde los dos lados del catálogo.

### Adaptadores (raíz)
```
Adaptadores
├─ Montura E    — adaptadores cuyo body engancha a Sony E (Sigma MC-11, Vello M42→E)
├─ Montura RF   — adaptadores a Canon R (Meike speedbooster, Canon Drop-In)
└─ Montura {X}  — on-the-fly según stock real (EF, L, Z, etc.)
```

Lógica en `seeds/adaptadores.py::categorize_adaptador()`: sub-cat única por
`lens_mount` (lado body). Las sub-cats se crean dinámicamente al primer
adaptador con esa montura — no hace falta predefinirlas.

### Filtros (raíz)
```
Filtros
└─ 82mm   — Tiffen (CPL, Variable ND, Pro-Mist 1/4, 1/8)
   ... (otros diámetros on-the-fly al primer filtro de cada tamaño)
```

Lógica en `seeds/filtros.py::categorize_filtro()`: sub-cat única por
`diametro_mm`. La sub-cat se llama directamente "82mm", "77mm", etc.

## Display templates (render del nombre)

Definidos en `backend/services/nombre_builder.py`:

- `distancia_focal`: `_rango_mm` → `[24, 70]` → `"24-70mm"` · `[50]` → `"50mm"`
- `apertura`: `_rango_apertura` → `[2.8]` → `"f/2.8"` · `[2.8, 4]` → `"f/2.8-4"`
- `angulo_vision`: `_rango_grados` → `[34, 84]` → `"34°-84°"`
- `diametro_filtro`: `"Ø{value}mm"` → 82 → `"Ø82mm"`
- `diametro_mm`: `"{value}mm"` → 82 → `"82mm"`
- `lens_mount`: `"Montura {value}"` → "E" → `"Montura E"`
- `peso_g`: `_smart_kg` → 695 → `"695g"`; 1500 → `"1.5 kg"`

Los formatters `_fmt_lente` y `_fmt_adaptador` consumen estos render templates
y construyen los nombres públicos del catálogo:

- `"Lente Zoom Sony FE 24-70mm f/2.8 GM II Montura E"`
- `"Lente Prime Carl Zeiss Jena Pancolar 50mm f/1.8 M42 (Thorium)"`
- `"Adaptador montura Sigma MC-11 EF → E"`
- `"Filtro polarizador Tiffen Polarizador circular 82mm"`

## Marcas canónicas

`Sony`, `Canon`, `Sigma`, `Tamron`, `Carl Zeiss`, `Leica`, `Tiffen`, `Hoya`,
`B+W`, `NiSi`, `PolarPro`, `Meike`, `Vello`, `Viltrox`, `Metabones`, `Fotodiox`,
`Kipon`, `Novoflex`, `Fujifilm`.

Definidas en `tools/lentes_normalizar.py::BRAND_CANON`.

## Workflow para agregar 1 lente o accesorio nuevo

**Bulk inicial / categoría nueva** (con Claude):
1. Guardar HTMLs en `~/Desktop/Paginas/Lentes/` (Cmd+S → Webpage Complete)
2. Agregar rutas a `tools/lentes_rebuild.sh`
3. Correr `bash tools/lentes_rebuild.sh`
4. Si el HTML no es de B&H (eBay, sitio fabricante), agregar override en `tools/lentes_patches.py`

**Lente nueva desde admin** (futuro, una vez wired):
- Mismo flow que iluminación — `/admin/equipos/autocompletar-from-html` con dispatcher por categoría.
- TODO: extender el extractor para soportar lentes y accesorios (hoy solo iluminación).

## Decisiones específicas

**¿Por qué `distancia_focal` y `apertura` como listas en vez de min/max separados?**
Las dos categorías de lente (fijo y zoom) viven en el mismo dataset. Con
`focal_min` + `focal_max` (separados), un fijo necesitaba `focal_min = focal_max =
50`, que se sentía artificial y forzaba al UI a deduplicar al renderizar. Con
una lista, `[50]` y `[24, 70]` son tan naturales como su nombre dice. El render
template hace lo correcto en cada caso.

**¿Por qué `Carl Zeiss` y no `Zeiss`?**
El B&H y la mayoría de catálogos usan "Carl Zeiss" como marca canónica. Los M42
vintage son específicamente "Carl Zeiss Jena" (DDR / alemán oriental), pero
"Jena" es modelo, no marca.

**¿Por qué los Zeiss vintage tienen patches manuales?**
Los HTMLs disponibles son de eBay, que no tiene tabla técnica estructurada
(`data-selenium` no existe). Las specs son estables (lentes de los 70s/80s, no
cambian), curadas desde:
- allphotolenses.com
- Pentax Forums Lens Database
- MIR Photography in Malaysia
- Carl Zeiss historical product sheets

Documentado en `_nota` de cada producto.

**¿Por qué la Laowa Probe está en "Especiales" y no "Fijos EF"?**
La Laowa 24mm f/14 Probe es una lente macro de uso muy específico (introducirse
en escenas, ratón-cam, comida, miniaturas). Es EF y técnicamente fija — pero
el cliente que busca "lentes fijos EF" no espera esto: espera 35mm/50mm/85mm
para retrato/general. La heurística `linea contiene "probe"` la manda a
"Especiales".

**¿Por qué `lens_mount_out` y no `lens_mount_in`?**
Convención: `lens_mount` siempre es el lado body (la cámara recibe el
accesorio). `lens_mount_out` es el lado opuesto (el lente del otro sistema
"sale" del adaptador hacia el body via la rosca interna). Así un adaptador
Sigma MC-11 EF→E tiene `lens_mount=E, lens_mount_out=EF`: cámara con E, lente
EF.

## Lo que NO se mapea (queda en `ficha`)

- Cobertura de IS / dual-IS modes (queda en `extras.estabilizacion_sistema` raw)
- Patrones de bokeh / aberración / breathing
- Compatibilidad detallada con cuerpos específicos
- Box / packaging dimensions / package weight
- Accesorios incluidos (caps, hood, pouch)

Eso vive en `ficha` para la página de detalle, no para filtrar.
