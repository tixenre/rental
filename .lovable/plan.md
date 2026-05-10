## Contexto

Tres bugs concretos + una visión más grande ("gestor de equipos").

1. **Búsqueda del kit no encuentra "sony"**: el backend usa `LIKE` (case-sensitive en Postgres). "Sony" matchea, "sony" no.
2. **Foto enriquecida no se guarda ni se ve en la web**: el dialog de IA guarda la URL externa de B&H/Adorama. Esos hosts bloquean hotlinking → la `<img>` queda rota. Además queda atada al sitio externo, no al equipo.
3. **Specs/descripción no se guardan**: el dialog de IA las muestra como "informativas" y no escribe en `equipo_fichas`, aunque las columnas ya existen (`descripcion`, `notas`, `specs_json`).

Y la idea de fondo: que el equipo sea **una sola entidad consistente** — datos básicos + ficha + foto propia + componentes — y que tanto el back-office como la web consuman el mismo modelo.

## Plan

### 1. Fix búsqueda fuzzy (case-insensitive)

`backend/routes/equipos.py` → `LIKE` por `ILIKE` en el filtro `q` de `GET /equipos`. Una línea, sin migración. Resuelve la búsqueda del editor de kit y cualquier otra búsqueda.

### 2. Fotos: pasar siempre por storage propio

Hoy la foto enriquecida se guarda como URL externa (B&H bloquea hotlinking → no se ve en la web).

- En `EnriquecerEquipoDialog`, al "Aplicar al equipo": si `foto_url` no es del bucket `equipos-fotos`, descargarla con el proxy `/api/admin/proxy-image` (ya existe), subirla a `equipos-fotos/equipos/{id}/foto-{ts}.{ext}` y guardar la URL pública del bucket.
- Mismo helper reutilizable (`uploadExternalPhotoToBucket`) lo puede usar también el botón "Subir" del editor cuando se pega una URL externa.
- Resultado: foto vive en el equipo, no en una función específica, y se ve en la web.

### 3. Persistir ficha (descripción + specs) desde IA

En `EnriquecerEquipoDialog`:
- Nuevos toggles "Aplicar descripción" y "Aplicar specs (N)" debajo de los actuales.
- Al aplicar, además del `updateEquipo`, hacer `adminApi.setFicha(id, { descripcion, specs_json: JSON.stringify(specs) })` con `Promise.all`.
- Toast de éxito ya lista los campos aplicados (incluye ahora "descripción" y "N specs").
- Quitar la nota "todavía no tiene campos para specs".

### 4. "Gestor de equipos" — consolidación ligera

Sin re-arquitectura grande, dejar el modelo unificado:

- `src/lib/equipment/` (nuevo módulo):
  - `types.ts` — re-exporta `BackendEquipo`, `Equipment`, `Ficha`, `Categoria`.
  - `mapping.ts` — mueve `buildPublicName` + `backendToEquipment` desde `useEquipos.ts`.
  - `photos.ts` — `uploadExternalPhotoToBucket(file|url, equipoId)` reutilizable.
- `useEquipos.ts` queda como hook delgado que importa de ahí.
- Web (cards/rows/detalle) sigue consumiendo `Equipment` igual; sin breaking changes.

Beneficio: cuando agregues fichas técnicas más ricas (pesos, conectores, accesorios sugeridos), un solo lugar para extender el modelo y la web lo refleja.

## Detalles técnicos

- Backend: cambio puntual en `routes/equipos.py` (filtro `q`). Sin migración.
- Frontend:
  - `EnriquecerEquipoDialog.tsx`: 2 checkboxes nuevos, llamada a `setFicha`, bajada de foto al storage previo a `updateEquipo`.
  - `useEquipos.ts`: extraer helpers (refactor mecánico, sin cambios de comportamiento).
  - Nuevo `src/lib/equipment/photos.ts` con la helper de subida (usa `supabase.storage.from('equipos-fotos')` y el proxy `/api/admin/proxy-image` para URLs externas).
- DB: nada nuevo, todo existe.

## Fuera de alcance (avisar)

- Rediseño de la card de equipo en la web para mostrar ficha técnica/specs — lo hacemos después, cuando arranques con las "fichas de cada equipo".
- Re-clasificación masiva de fotos viejas que ya están guardadas como URL externa (lo dejamos para una migración aparte si querés).
