# Bugs — roadmap de fixes

> Auditoría hecha el **2026-05-10** sobre la branch `claude/local-database-testing-o6pXj`.
> Convención: `[ ]` por hacer, `[x]` arreglado. Tachá a medida que vayas avanzando.

---

## CRÍTICO — rompen producción / pierden datos / vulnerabilidades

- [x] **`<Toaster />` no estaba montado** — `src/routes/__root.tsx`. Se usaba `toast()` en 14+ archivos pero nunca se renderizaba. Por eso muchos botones parecían "no hacer nada" (en realidad mostraban toasts invisibles). **FIX aplicado en este commit**: agregado `<Toaster richColors position="top-right" />` en el root.

- [x] **Secuencias de Postgres desincronizadas** — `equipos.id_seq` estaba en 9 con 163 filas, `etiquetas.id_seq` en 206 con 293. Cualquier `INSERT` sin `id` explícito fallaba con 500. **FIX aplicado**: (1) `setval()` a `MAX(id)` en runtime. (2) Causa raíz arreglada en `migrate_to_postgres.py`: agregado bloque que hace `setval()` para todas las tablas (`equipos`, `clientes`, `alquileres`, `etiquetas`, `categorias`, `usuarios`) al final de la migración. La próxima vez que corra ese script no se va a volver a romper.

- [x] **Typo `foto_candidate` vs `foto_candidates`** — `backend/routes/equipos.py:1491`. **FIX aplicado**: corregido a `"foto_candidates"` (plural). Ahora la condición `needs_alt` evalúa correctamente y se activa el fallback a Adorama/sitios oficiales cuando B&H no devuelve fotos.

- [x] **Mezcla `?` / `%s` en SQL** — `backend/routes/equipos.py`. **NOTA**: no era un bug funcional (el wrapper `PGCursor.execute` reemplaza `?`→`%s` antes de psycopg2), era solo inconsistencia de estilo. **FIX aplicado**: (1) reemplazadas 30+ ocurrencias de `%s` por `?` en `equipos.py` para mantener la convención del archivo. (2) Documentado el wrapper en `database.py:70-77` para que quede claro por qué existe y cuál es la convención. La migración completa está OK — todo el stack es Postgres puro, el `?` es solo legacy del wrapper de compatibilidad para no reescribir cientos de queries de la migración SQLite→PG. **Decisión**: NO se hizo el refactor masivo a `%s` nativo — riesgo alto (hay `?` en regex/URLs en varios archivos) por beneficio puramente cosmético. Si se hace, debe ser archivo por archivo con tests.

---

## ALTO — bug real, afecta UX

- [x] **`uploadExternalUrlToBucket("nuevo", url)` en CREATE mode** — **FIX aplicado**: refactor del flow completo de `submit()` en `EquipoFormDialog.tsx`. El equipo se crea/actualiza primero (con la URL externa o `null` si hay archivo pendiente), después se sube a R2 con el `id` real seguido de un PATCH del equipo. Para archivos locales en CREATE mode se introdujo el state `pendingFile` + `pendingFilePreview` (blob URL) que se sube post-create. Mismo fix replicado en `elegirFoto` y `handleUpload`.

- [ ] **`CLIENTE_REDIRECT_URI` hardcodeado a producción** — `backend/routes/auth.py:28-31`. En dev local, el OAuth del cliente redirige a Railway. **Fix**: leer de env var con fallback local.

- [x] **`form.handleSubmit` sin try/catch global** — **FIX aplicado**: el nuevo `submit()` envuelve el flow en try/catch. Si el create/update falla, `toast.error` y el dialog queda abierto para reintentar sin perder el form. Errores parciales (foto/ficha/categorías) se acumulan en el array `fallidos` y se reportan en un único `toast.warning` al final con detalle.

- [x] **`aplicarEnriquecimiento` race con `onSuccess`** — **FIX aplicado**: en `routes/admin/equipos.tsx`, `saveMut` cambió de `onSuccess` (con close + toast) a `onSettled` (sólo invalida queries). El form maneja el cierre y los toasts al **final** del flow completo, después de foto + ficha + ficha extendida + categorías. El dialog ya no se cierra con requests en vuelo.

- [ ] **`importarDesdeUrl` sin validación de URL** — `EquipoFormDialog.tsx:221`. Acepta cualquier string. **Fix**: validar `new URL(u)` antes del fetch.

---

## MEDIO — bugs latentes, edge cases

- [ ] **`authedJson` mensaje de error pobre** — `src/lib/authedFetch.ts:24-28`. Cuando la respuesta no es JSON, el mensaje queda como `"GET /path → 500"` sin contexto. **Fix**: leer body como text si JSON falla.

- [ ] **`buscarFotos` sin timeout** — `EquipoFormDialog.tsx:145`. Si el fetch tarda más de lo esperado, `photoSearching` puede quedar en `true`. **Fix**: `AbortController` con timeout de 30s.

- [ ] **`extracted` dict vacío `{}` pasa el check** — `backend/routes/equipos.py:1514`. `if not extracted` es false para `{}`. **Fix**: `if not extracted or not any(extracted.values())`.

- [ ] **boto3 client se crea por upload** — `_upload_to_r2` en `equipos.py:2295`. Sin pooling, costoso bajo carga. **Fix**: cliente singleton a nivel módulo.

- [ ] **`PGCursor.execute` no valida SQL** — `backend/database.py:77`. Si llega SQL sin parámetros y con `?` en el string, el replace puede hacer cualquier cosa. **Fix**: log + assert que params no esté vacío cuando hay `?`.

- [ ] **Diff "cambia" en `FieldRow`** — `EnriquecerEquipoDialog.tsx:787`. Compara `current ?? ""` con `value` pero los strings vacíos pueden venir como `null` desde el backend, mostrando "cambia" cuando no cambió nada.

- [ ] **`/admin/equipos/{id}/upload-foto-from-url` sin validación de host** — backend descarga arbitrariamente cualquier URL que le pasen. **Fix**: allowlist (bhphotovideo, adorama, manufacturer domains, wikimedia, dpreview, fstoppers, etc.).

- [ ] **`saveMut.isPending` no resetea si el dialog se cierra a mitad** — TanStack mutation puede quedar `pending` si la promesa no se resuelve. **Fix**: `onSettled` cleanup.

---

## BAJO — código muerto / deuda técnica

- [ ] **`isBucketUrl` importado pero no usado** — `EnriquecerEquipoDialog.tsx:15`. (de hecho sí se usa en `uploadPhotoWithDiag`, ignorar este — verificar antes de tachar).

- [ ] **`ChevronUp`/`ChevronDown` no usados** — `EquipoFormDialog.tsx:6` (verificar — sí están usados en el spec mover up/down).

- [ ] **`admin_proxy_image()` deprecated** — `backend/routes/equipos.py:2000-2104`. Ya no se usa desde el frontend. **Fix**: eliminar o agregar allowlist.

- [x] **Caché `__pycache__` en git** — **FIX aplicado**: `git rm --cached -r backend/__pycache__ backend/routes/__pycache__` (14 archivos `.pyc` deleteados del tracking). El `.gitignore` ya los ignoraba pero quedaron como legacy de un commit viejo. Ahora `git status` no los muestra más.

- [ ] **Constante `MAX_PHOTO_CANDIDATES` repetida** — `equipos.py:1449` (6) vs `:1588` (8). **Fix**: una sola constante a nivel módulo.

- [ ] **`fuente_de_enriquecimiento` poco granular** — devuelve "firecrawl" genérico para Adorama/Amazon. **Fix**: distinguir `firecrawl-bh / firecrawl-adorama / firecrawl-manufacturer`.

---

## Sugerencia de orden de ataque

1. Los CRÍTICOS restantes (typo `foto_candidate`, SQL `?`/`%s`) — son fixes de pocos minutos.
2. Los ALTOS de UX (`uploadExternalUrlToBucket`, race del onSuccess) — afectan tu testeo diario.
3. Limpiar `__pycache__` del git para que `git status` quede limpio.
4. El resto cuando puedas.
