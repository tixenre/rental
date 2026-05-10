# Enriquecer equipos sin LOVABLE_API_KEY

## Objetivo

Que el botón ✨ "Enriquecer con IA" en `/admin/equipos` funcione **solo con Firecrawl** (que ya tenés configurado y andando). Cero dependencia del `LOVABLE_API_KEY` que no se puede copiar a Railway.

## Por qué se puede

Firecrawl tiene un formato `json` con extracción estructurada vía LLM **incluido en su propio servicio**. Le pasás un schema (marca, modelo, foto_url, descripción, specs) y un prompt, y te devuelve el JSON ya parseado. La IA la corre Firecrawl internamente — vos solo necesitás `FIRECRAWL_API_KEY`, que ya está.

Hoy el flujo hace dos llamadas: Firecrawl scrape → Lovable AI Gateway para extraer. Lo colapsamos a una sola llamada Firecrawl con `formats: [{type: "json", schema, prompt}]`.

## Cambios

### Backend (`backend/routes/equipos.py`, endpoint `/admin/equipos/enriquecer`)

1. Eliminar el chequeo y uso de `LOVABLE_API_KEY`.
2. En la llamada a `/v2/scrape` de Firecrawl, agregar `formats: [{type: "json", schema: {...}, prompt: "Extraé marca, modelo, foto principal, descripción corta y specs clave de esta ficha de producto"}]`.
3. Leer el resultado de `data.json` que devuelve Firecrawl (en vez de scrapear markdown y mandarlo a Lovable AI).
4. Mantener intacta la búsqueda inicial en B&H/Adorama y la respuesta `EnriquecerResult` (mismos campos que ya consume el frontend).

### Frontend

Sin cambios. `EnriquecerEquipoDialog` recibe el mismo shape de respuesta.

### Railway

- **Quitar** `LOVABLE_API_KEY` de las variables (ya no hace falta).
- Confirmar que `FIRECRAWL_API_KEY` siga seteado.

## Resultado

- Cargás equipos uno por uno con el botón ✨ y te autocompleta marca/modelo/foto/specs.
- No hay que pelearse más con keys de Lovable.
- Si el día de mañana Firecrawl se queda corto, queda fácil cambiar a OpenAI/Gemini directos (un solo lugar en el backend).

## Notas técnicas

- La extracción JSON de Firecrawl usa créditos extra por scrape (multiplicador conocido, no gratis pero está dentro de su plan).
- Si una ficha viene mal parseada, el dialog ya muestra los campos editables antes de aplicar — no se rompe nada.
- Tiempo por equipo: 10–25 s (igual que ahora, no cambia porque Firecrawl ya hace el grueso del trabajo).
