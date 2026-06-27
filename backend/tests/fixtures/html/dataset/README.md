# Dataset local de HTMLs para el extractor

Carpeta **gitignored** para el dataset de páginas reales (B&H / eBay / fabricantes)
con el que se itera el extractor de specs. Los `.html` **no** se commitean
(copyright de terceros + peso + repo público).

## Uso

1. Guardá la página del producto como HTML completo (Cmd/Ctrl+S → "Página web completa").
2. Dejá el `.html` en esta carpeta.
3. Corré el diagnóstico:

   ```bash
   cd backend
   python tools/diagnose_extractor.py tests/fixtures/html/dataset/*.html
   ```

El reporte muestra, por archivo: categoría detectada, cuántas specs trae la
página, cuántas resuelve el alias-index, cobertura %, y la lista de **labels
perdidos** (candidatos a agregar como `aliases` en `specs/categorias/*.py`).

## Para fixtures de regresión

Si querés fijar un caso como test, extraé un **fixture mínimo sintético** (como
los `*_minimal.html` que ya existen en `tests/fixtures/html/`) con solo el
JSON-LD / tabla relevante — no el HTML completo de terceros.
