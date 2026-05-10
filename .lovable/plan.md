# Plan

## 1. Debuggear fotos paso a paso

El enriquecedor encuentra la foto pero no se ve en la web. Voy a instrumentar el flujo para ver exactamente dónde se rompe.

**Qué agrego en `EnriquecerEquipoDialog`:**
- Un panel de "Diagnóstico de foto" debajo del preview que muestra en vivo:
  1. URL externa detectada
  2. Status HTTP del proxy `/api/admin/proxy-image`
  3. Tamaño/tipo del blob descargado
  4. Resultado del upload a `equipos-fotos` (URL final o error exacto de Supabase)
  5. Resultado del `update_equipo` (foto_url guardada vs lo que devuelve el GET)
- Cada paso con check verde / cruz roja, para que veamos juntos en qué eslabón falla.

**Posibles causas que el diagnóstico va a confirmar o descartar:**
- Proxy devuelve 403/404 (B&H bloquea ese endpoint puntual)
- Blob llega vacío o con content-type raro
- Upload a Supabase Storage rechazado (RLS / sesión no autenticada del lado del browser)
- El backend no persiste `foto_url` en el `update_equipo` (improbable pero lo verificamos releyendo)
- La URL queda guardada bien pero el `<img>` del catálogo cachea una versión vieja

Una vez identificado, aplico el fix puntual (ej: si el browser no está autenticado contra Supabase Storage, hago el upload server-side desde el backend; si es cache, agrego cache-buster).

## 2. Reorganizar specs en la ficha pública

**Selección de destacados (3-4):**
- Heurística por categoría del equipo:
  - Cámara → Sensor / Resolución / Montura / ISO
  - Lente → Focal / Apertura / Montura / Estabilización
  - Luz → Potencia / Temperatura color / CRI / Alimentación
  - Audio → Tipo / Patrón / Conexión
  - Default → primeras 4 specs no vacías
- Las destacadas se muestran como **chips grandes** arriba del bloque (label arriba, valor abajo, tipografía display).
- El resto va en un acordeón **"Ver todas las specs"** con tabla key/value.

**Dónde:**
- `EquipmentDetailDialog` (modal de detalle): destacados + acordeón completo.
- `EquipmentRow` expandida y `EquipmentCard`: solo 2 chips destacados pequeños (los más distintivos).

## 3. Tags/keywords libres por equipo (nueva feature)

**Concepto:** cada equipo tiene una lista corta de palabras clave editables que describen su personalidad ("bicolor", "silenciosa", "V-mount", "cine-ready", "global shutter", "weather-sealed"). Distintas de las etiquetas de búsqueda actuales, que son auto-generadas desde marca/modelo/categorías.

**Backend:**
- Nueva columna en `equipo_fichas`: `keywords_json TEXT` (array JSON de strings) — o tabla aparte `equipo_keywords` si preferimos relacional. Voto por JSON simple porque es solo display, no se filtra.
- Endpoints existentes `GET/PUT /equipos/{id}/ficha` ya pasan por `setFicha`; agregar `keywords_json` al modelo Pydantic y al SELECT.
- El público `/api/equipos` ya retorna `ficha`; agregar `keywords` al payload.

**IA:**
- En el prompt del enriquecedor agregar un campo `keywords` (array de 3-6 strings cortos, en español, lowercase, distintivos del equipo, no genéricos).
- En el dialog: mostrar las keywords propuestas como chips toggleables (el admin puede tildar/destildar y editar el texto antes de aplicar).

**UI admin:**
- En el editor de equipo (`EquipoFormDialog` → tab "Ficha técnica"): input tipo "tag input" (chip + Enter para agregar, X para borrar). Esto hace que el admin pueda manejarlas también sin pasar por la IA.

**UI pública:**
- En **card y fila del catálogo**: hasta 2 keywords como chips chiquitos al lado del nombre/precio (las más cortas primero), con un look distinto a las categorías para no confundir.
- En **modal de detalle**: todas las keywords como chips arriba de la descripción.

## 4. Verificación

- Re-enriquecer 1-2 equipos (una luz y una cámara).
- Confirmar que en el diagnóstico la foto aparece check-verde end-to-end.
- Confirmar que el chip de keywords aparece en card y modal.
- Confirmar que los specs destacados son los correctos para esa categoría y el acordeón abre el resto.

## Detalles técnicos

- Migración SQL backend (SQLite/Postgres según corresponda): `ALTER TABLE equipo_fichas ADD COLUMN keywords_json TEXT`.
- `EnriquecerResult` suma `keywords: string[]`.
- `IncludedList` y `EquipmentDetailDialog` reciben `ficha.keywords` y `ficha.specs_json` ya parseados.
- Helper `pickHighlightSpecs(category, specs)` centralizado en `src/lib/equipment/specs.ts`.
- El input de tags reusa `Badge` + `Input` con manejo de Enter/Backspace; nada de libs nuevas.
