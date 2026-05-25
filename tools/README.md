# `tools/` — pipeline B&H → DB

Scripts para extraer specs estructurados desde HTMLs de B&H Photo Video
y cargarlos a la DB. Una categoría por pipeline:

| Categoría | Parser | Rebuild |
|---|---|---|
| Cámaras | `camaras_parser.py` | `camaras_rebuild.sh` |
| Lentes (incl. Adaptadores, Filtros) | `lentes_parser.py` | `lentes_rebuild.sh` |
| Iluminación | `iluminacion_parser.py` | `iluminacion_rebuild.sh` |
| Modificadores (Softbox, Fresnel, etc.) | `modificadores_parser.py` | `modificadores_rebuild.sh` |

## Flujo end-to-end

```
HTMLs B&H        →  Parser   →  Patches            →  Normalizer    →  Dataset curado
~/Desktop/...       parser.py   {cat}_patches.py      _normalizar.py    docs/{cat}.json
                    (extrae)    (overrides manual)    (canoniza)        (commiteable)

                                    ↓

Match con DB     →  Preview          →  Dataio import   →  DB
docs/equipos_      tools/specs_         backend/dataio     equipo_specs
match.json         import_preview.py    cli import         spec_definitions
                                                           categoria_spec_templates
```

## Pasos por categoría (ejemplo Cámaras)

1. **Guardá los HTMLs** en tu carpeta de capturas (default `~/Desktop/Paginas/Camaras/`; override con la variable de entorno `RAMBLA_HTMLS_DIR`).
2. **Regenerá el dataset**:
   ```bash
   bash tools/camaras_rebuild.sh
   ```
   Produce: `docs/camaras.json` + `docs/camaras_raw.json`.
3. **Validá contra el registry**:
   ```bash
   cd backend && pytest tests/test_specs_registry.py -k "camaras"
   ```
4. **Si el HTML no se parsea** (sitio del fabricante, eBay, etc.):
   - Agregá overrides en `tools/camaras_patches.py` con `specs={...}` curados a mano.
   - Re-correr el rebuild.
5. **Si un equipo nuevo no matchea con DB**:
   - Agregá entry en `docs/equipos_match.json` con `{action: "update", equipo_id: N}` o `{action: "create"}`.
   - `action: "skip"` si querés excluirlo (ej. kits).

## Pasar de dataset a DB

```bash
# 1. Generar preview (no toca DB)
python tools/specs_import_preview.py

# 2. Mover archivos generados al directorio que dataio lee
mkdir -p data/catalog
cp /tmp/import_preview/equipos.json /tmp/import_preview/equipo_specs.json data/catalog/

# 3. Dry-run para ver qué cambiaría
python -m backend.dataio.cli import --only equipo_specs --dry-run

# 4. Aplicar
python -m backend.dataio.cli import --only equipo_specs

# 5. Limpiar
rm -rf data/catalog
```

## Convenciones del dataset

- **`docs/{cat}.json`**: dataset curado, **commiteable** (validado contra registry).
- **`docs/{cat}_raw.json`**: secciones B&H originales. Se regenera al correr el parser. Para debugging.
- **`docs/equipos_match.json`**: mapeo dataset → equipo_id en DB. Se edita a mano cuando aparece un equipo nuevo o un override.

## Comparten primitives

Los parsers de Lentes/Modificadores reusan helpers de `iluminacion_parser`
(`BHSpecsParser`, `_find_value`, `_extract_brand`, etc.). Los normalizers
canonizan marcas/modelos/slugs y reordenan keys según el orden del registry.

Si agregás una categoría nueva:
1. Declarar en `backend/specs/categorias/{cat}.py`.
2. Crear `tools/{cat}_parser.py` + `_rebuild.sh`.
3. Agregar a `DATASETS` en `tools/specs_import_preview.py`.
4. Agregar al test `test_dataset_valida_contra_registry`.

## Helper para resetear specs

`tools/specs_reset.py` limpia `equipo_specs` + `spec_definitions` +
`categoria_spec_templates` antes de un re-seed completo. Solo correr
manualmente cuando cambien los enums del registry y haya que re-poblar.
