# Dataset de Modificadores de luz — Guía y Convenciones

Mismo patrón que `DATASET_LENTES.md` / `DATASET_ILUMINACION.md` /
`DATASET_CAMARAS.md`. Las convenciones cross-cutting (IDs, unidades,
ausencia de datos) están en `docs/SISTEMA_SPECS.md` §2.

**Particularidad:** los modificadores son acoplados a una luz (no
auto-iluminan). Categoría raíz **Modificadores** con 4 sub-cats fijas:

- **Softbox** (id=22) — softboxes hexa/parabolic/octa/lantern
- **Fresnel** (id=9891) — fresnel lenses para LEDs (Forza, etc.)
- **Spotlight** (id=9892) — spotlight lens kits (proyectores tipo Source Four)
- **Difusión / Frame** (id=14195) — frames de difusión, banderas negras, reflectores

A diferencia de Filtros (donde el diámetro genera sub-cats on-the-fly),
acá la taxonomía es **cerrada** — el seeder NO crea sub-cats nuevas.

## Archivos

- `docs/modificadores.json` / `_raw.json` — productos curados + raw
- `tools/modificadores_parser.py` — extractor B&H (DOM scrape, hereda
  `BHSpecsParser` de `iluminacion_parser`); detecta no-B&H y los saltea
- `tools/modificadores_rebuild.sh` — pipeline (parse 7 HTMLs de
  `~/Desktop/Paginas/Modificadores_Luz/`)
- `backend/seeds/modificadores.py` — seed (crea spec_definitions desde
  el registry y persiste equipo_specs)
- `backend/services/specs/registry/catalogo/modificadores.py` — el `CAT` (CategoriaRegistry) con las 12 specs

## `specs` de Modificadores — 12 campos

| Campo | Tipo | Aplica a | Notas |
|---|---|---|---|
| `modificador_subtipo` | enum | TODOS | **Función** del modificador: Softbox / Spotlight / Fresnel / Difusor / Bandera Negra / Reflector. La forma geométrica va aparte en `forma`. |
| `forma` | enum | Softbox | Octagonal / Parabolic / Hexadecagon / Lantern Round / Strip / Square / Rectangle / Deep / Oval. Un Softbox Lantern es subtipo=Softbox + forma=Lantern Round. |
| `diametro_cm` | number (cm) | Softbox/Fresnel/Bola china | Para los redondos. Octogonales se miden por diámetro mayor. |
| `dimensions_mm` | string | TODOS | Parte métrica de B&H. Ej: `"ø: 89 x H: 60 cm (Open)"`. Convención cross-cat con Cámaras/Iluminación/Adaptadores. |
| `montura_luz` | enum | Softbox/Spotlight/Fresnel | Bowens S / Elinchrom / Profoto / Nanlite Forza / Sin montura. Compatibilidad: matchea con el `montura_luz` de la luz (exacta). |
| `incluye_grid` | bool | Softbox | **Semántica:** viene CON grid en el kit. `"Yes (Included)"` → True. `"Yes (Not Included)"` → **False** (acepta pero se vende aparte, no lo tenemos). `"No"` → False. |
| `incluye_difusor` | bool | Softbox | "Interior Baffle: Yes" → True. El baffle es la capa difusora removible. |
| `plegable` | bool | Softbox | "Quick Open Type: Foldable / Click/Locking" → True. "Fixed" → False. |
| `light_loss_stops` | number (stops) | Softbox | Pérdida con difusor. `"1-Stop Loss"` → `1.0`. `"No"` → `0.0`. `null` si el HTML no lo declara. |
| `materials` | string | TODOS | Texto de B&H (Fabric / Fabric, Steel / Glass, Metal). Convención cross-cat. |
| `beam_angle` | **rango** (°) | Spotlight/Fresnel | `[36]` fijo, `[10, 45]` variable (zoom Fresnel). Mismo patrón que `angulo_vision` de Lentes. |
| `peso_g` | number (g) | TODOS | Solo modificador, sin packaging. |

**Tipos consistentes con el resto del registry**: `light_loss_stops` es
`number` (en stops) en vez de string libre; `beam_angle` es `rango`
(lista de 1 o 2 floats) igual que `angulo_vision` en Lentes. Las keys
compartidas con otras categorías usan el mismo nombre (`peso_g`,
`dimensions_mm`, `materials`) para que el motor de compatibilidad pueda
matchear cross-cat sin alias.

## Cobertura del dataset

6 productos del scrape B&H (de 7 HTMLs en
`~/Desktop/Paginas/Modificadores_Luz/`; el Reflector Plegable Godox tiene
HTML solo del fabricante — sin parse, queda para curado manual a futuro).

| dataset_id | producto | match en DB |
|---|---|---|
| `angler_quickopen` | Angler Quick-Open Deep Parabolic 48" | id=69 |
| `aputure_aa07060383` | Aputure Quick Dome 60 | id=70 (Mini II) |
| `aputure_aa07060382` | Aputure Quick Dome 90 | id=68 (Light Dome III) |
| `godox_collapsible` | Godox Collapsible Lantern 33.5" | id=71 (CS-85D) |
| `nanlite_fresnel` | Nanlite Fresnel Lens FL-20G | id=74 |
| `amaran_spotlight` | Amaran Spotlight SE 36° Lens Kit | id=75 |

## Rebuild

```bash
bash tools/modificadores_rebuild.sh
```

## Validación

`backend/tests/test_specs_registry.py::test_dataset_valida_contra_registry[Modificadores-modificadores.json]`
valida que cada spec del dataset esté declarado en el registry, los
valores enum estén en `enum_options`, y los tipos sean coherentes.

## Import a DB

Vía dataio (genera/copia archivos desde el preview):

```bash
python tools/specs_import_preview.py
mkdir -p data/catalog
cp /tmp/import_preview/equipos.json /tmp/import_preview/equipo_specs.json data/catalog/
python -m backend.dataio.cli import --only equipo_specs --dry-run    # verificar
python -m backend.dataio.cli import --only equipo_specs              # aplicar
```

O vía seed directo (registra spec_definitions + sub-cats + persiste equipo_specs):

```bash
python -m backend.seeds.modificadores --dry-run    # ver qué haría
python -m backend.seeds.modificadores              # aplicar
```
