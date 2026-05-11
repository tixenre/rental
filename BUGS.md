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

- [x] **`CLIENTE_REDIRECT_URI` hardcodeado a producción** — **FIX aplicado**: en `auth.py` se introdujo `_default_oauth_base()` que detecta el entorno via `RAILWAY_ENVIRONMENT`. En Railway usa el dominio prod, en local usa `http://localhost:8000`. La env var (cuando está seteada) tiene prioridad. Aplica tanto a `REDIRECT_URI` (admin) como a `CLIENTE_REDIRECT_URI` (portal cliente).

- [x] **`form.handleSubmit` sin try/catch global** — **FIX aplicado**: el nuevo `submit()` envuelve el flow en try/catch. Si el create/update falla, `toast.error` y el dialog queda abierto para reintentar sin perder el form. Errores parciales (foto/ficha/categorías) se acumulan en el array `fallidos` y se reportan en un único `toast.warning` al final con detalle.

- [x] **`aplicarEnriquecimiento` race con `onSuccess`** — **FIX aplicado**: en `routes/admin/equipos.tsx`, `saveMut` cambió de `onSuccess` (con close + toast) a `onSettled` (sólo invalida queries). El form maneja el cierre y los toasts al **final** del flow completo, después de foto + ficha + ficha extendida + categorías. El dialog ya no se cierra con requests en vuelo.

- [x] **`importarDesdeUrl` sin validación de URL** — **FIX aplicado**: ahora valida con `new URL(u)` que el string sea http(s) antes del fetch. Si no es URL válida, rechaza al instante con toast claro en lugar de esperar timeout del backend (~3s).

---

## MEDIO — bugs latentes, edge cases

- [x] **`authedJson` mensaje de error pobre** — **FIX aplicado**: ahora lee el body como text una sola vez, intenta `JSON.parse` para extraer `.detail` o `.message`, y si falla limpia tags HTML y devuelve los primeros 200 chars del texto. Bonus: maneja correctamente `204 No Content` y respuestas con body vacío (antes rompía con `Unexpected end of JSON input`). Aplica a TODA la app porque `authedJson` se usa en cada call al backend.

- [x] **`buscarFotos` sin timeout** — **FIX aplicado**: `AbortController` con `setTimeout(30_000)`. Si Firecrawl/scraper se cuelga, abortamos con toast informativo en lugar de dejar el spinner pegado para siempre.

- [x] **`extracted` dict vacío `{}` pasa el check** — **FIX aplicado**: cambiado a `if not extracted or not any(extracted.values())`. Caso real cubierto: Firecrawl devuelve el schema completo pero todas las keys en `None`/`""`.

- [x] **boto3 client se crea por upload** — **FIX aplicado**: introducido `_get_r2_client()` con cache global por tupla `(account_id, access_key_id, secret_key)`. Cachea el client después del primer uso y lo invalida sólo si cambian las credenciales. Ahorra ~50ms por upload después del primero.

- [x] **`PGCursor.execute` no valida SQL** — **FIX aplicado**: ambos `PGCursor.execute` y `PGConnection.execute` validan ahora que `sql` sea `str` (TypeError si no) y que si hay `?` en el SQL haya `params` (ValueError si no). Convierte un fallo críptico de psycopg2 (`syntax error at or near %s`) en un error explícito con el SQL en cuestión.

- [x] **Diff "cambia" en `FieldRow`** — **FIX aplicado**: la comparación normaliza con `((current ?? "") as string).trim() !== (value ?? "").trim()`. Antes marcaba "cambia" cuando el actual era `" FX3 "` y el nuevo `"FX3"` (mismo valor con espacios), confundiendo el review en el dialog de Enriquecer.

- [x] **`/admin/equipos/{id}/upload-foto-from-url` sin validación de host (SSRF)** — **FIX aplicado** (era SEGURIDAD, no MEDIO): introducido `_validate_external_image_url()` con (1) allowlist de ~40 hosts conocidos (retailers, Wikipedia, reviews, manufacturer domains, CDNs); (2) `_host_resolves_to_private()` que rechaza hosts que resuelvan a IPs privadas/loopback/link-local/multicast/reserved (defense-in-depth contra dominios del allowlist apuntando a internas); (3) sólo http(s) en puertos 80/443; (4) `max_redirects=3` en `httpx.Client` para limitar blast radius. Llamado al inicio del endpoint y dentro de `_download_image_bytes`. Smoke tests pasan: localhost, 169.254 metadata, hosts random → 403/400; B&H/Adorama → OK.

- [x] **`saveMut.isPending` no resetea si el dialog se cierra a mitad** — **YA CUBIERTO** por el fix del PR `fix/equipo-form-flow`: `saveMut` cambió de `onSuccess` a `onSettled`, que se ejecuta tanto en éxito como en error y siempre invalida queries. `isPending` se resetea correctamente en ambos casos.

---

## BAJO — código muerto / deuda técnica

- [x] **`isBucketUrl` importado pero no usado** — **FALSO POSITIVO**: sí se usa en `uploadPhotoWithDiag` (línea 221). Verificado con `grep`.

- [x] **`ChevronUp`/`ChevronDown` no usados** — **FALSO POSITIVO**: sí se usan en los botones de mover specs up/down en la pestaña "Ficha técnica" (líneas 939, 942). Verificado con `grep`.

- [x] **`admin_proxy_image()` deprecated** — **FIX aplicado**: borrado el endpoint completo (~108 líneas). Ya no se usa desde el frontend desde la migración a R2 + upload server-side. Reduce surface attack (era un endpoint admin sin allowlist de hosts).

- [x] **Caché `__pycache__` en git** — **FIX aplicado**: `git rm --cached -r backend/__pycache__ backend/routes/__pycache__` (14 archivos `.pyc` deleteados del tracking). El `.gitignore` ya los ignoraba pero quedaron como legacy de un commit viejo. Ahora `git status` no los muestra más.

- [x] **Constante `MAX_PHOTO_CANDIDATES` repetida** — **FIX aplicado**: centralizadas 4 constantes bien nombradas al top del módulo (`MAX_PHOTO_CANDIDATES_PER_SCRAPE`, `_TO_VALIDATE`, `_BUSCAR_VALIDATE`, `_BUSCAR_RETURN`). El "duplicado" eran realmente 4 contextos distintos con números mágicos confusos.

- [x] **`fuente_de_enriquecimiento` poco granular** — **FIX aplicado**: nuevo helper `_fuente_for(scrape)` que detecta el host del scrape (B&H, Adorama, Amazon, manufacturer) y devuelve `firecrawl-bh / firecrawl-adorama / firecrawl-amazon / firecrawl-manufacturer`. Para no depender del format del `metadata` de Firecrawl, `_scrape` ahora incluye explícitamente `source_url` en su salida.

---

## ✅ Estado al 2026-05-10 (post-cleanup)

| Severidad | Total | Cerrados | Pendientes |
|---|---|---|---|
| **CRÍTICO** | 5 | **5** ✅ | 0 |
| **ALTO**    | 5 | **5** ✅ | 0 |
| **MEDIO**   | 8 | **8** ✅ | 0 |
| **BAJO**    | 5 | **5** ✅ | 0 |
| **TOTAL**   | **23** | **23** ✅ | **0** |

Todos los bugs auditados están cerrados o son falsos positivos verificados.

## Próxima auditoría

Cuando se acumule deuda nueva (después de varias features), correr el flow
descrito en `PROTOCOLO.md`:

1. Spawn Explore agent con prompt de auditoría.
2. Volcar hallazgos a `BUGS.md` (reset del archivo a las nuevas categorías).
3. Atacar en tandas siguiendo prioridad CRÍTICO → ALTO → MEDIO → BAJO.

---

## Bugs reportados por el usuario — mayo 2026

Fijados en PR #26 (`feat/sistema-specs-bulletproof`).

| Bug | Estado |
|-----|--------|
| PNG con fondo negro | ✅ Resuelto — `object-contain` + `bg-white` en Card/Row/Dialog |
| Cambios en categorías no se guardan | ✅ Resuelto — `CategoriasSection` reescrita; backend ya tenía CRUD correcto |
| Link en "Enriquecer con IA" no funciona | ✅ Resuelto — input UI + parámetro `url` en payload → backend lo usaba pero faltaba el campo |
| Opciones de búsqueda confusas ("Info técnica" buscaba fotos también) | ✅ Resuelto — renombrado a "Specs + foto" |
| Botón "Ingresar" no lleva a ningún lado | ✅ Resuelto — creado `cliente.index.tsx` con redirect; TanStack Router necesitaba un index route |
| Modal de producto vuelve al top al cerrarlo | ✅ Resuelto — `savedScrollY` ref + `resetScroll: false` en navigate + `requestAnimationFrame` restore |
| Imágenes de distintos tamaños | 🟡 Mejorado — `object-contain` + aspect-ratio fijo; normalización completa pendiente (remove.bg) |
| Búsqueda "Solo fotos" calidad baja | 🔵 Pendiente (low priority) |
| Calendario en dashboard | 🔵 Sugerencia pendiente |

## 🔴 CRÍTICO

### #27 - Falta validación de login en cotización
**Módulo:** Cliente/Cotización - Autenticación  
**Descripción:** Al intentar "Confirmar solicitud" sin estar logeado, no hay validación. Debería:
- Mostrar mensaje: "Debes iniciar sesión o crear una cuenta"
- Ofrecimiento: Login o Sign Up

**Steps to reproduce:**
1. No estar logeado
2. Agregar equipos al carrito
3. Click "Confirmar solicitud"
4. Verificar que no valida login

**Estado:** 🔵 Reportado  
**Impacto:** Crítico (bloquea flujo de checkout)

---

## 🟠 ALTO

### #28 - Falta validación de fechas en cotización
**Módulo:** Cliente/Cotización  
**Descripción:** Si el usuario no selecciona fechas (muestra "– 09:00"), debería haber validación/popup cuando intenta confirmar.

**Esperado:** Mostrar modal pidiendo que seleccione fechas

**Estado:** 🔵 Reportado  
**Impacto:** Alto (información esencial incompleta)

---

## 🟡 MEJORA - Home

### #29 - Rediseñar home: enfoque en Estudio
**Módulo:** Home/Landing  
**Cambios solicitados:**
1. ❌ Eliminar badges: CALIDAD, VARIEDAD, AMISTAD, COMUNIDAD, INTERCAMBIO, LOCAL
2. ❌ Eliminar sección "PRODUCTO ESTRELLA"
3. ✅ Dar más importancia a "Conocé el Estudio"
   - Destacar visualmente
   - Mayor jerarquía en la página

**Estado:** 🔵 Solicitado  

---

## 🟢 FEATURE - Página del Estudio

### #30 - Desarrollar página del Estudio
**Módulo:** Estudio (página nueva/mejorada)  
**Descripción:** La página del estudio existe pero necesita desarrollo/mejora. Actualmente está bien pero se puede mejorar.

**Acción:** Diseño y desarrollo de página del estudio mejorada

**Estado:** 🔵 Pendiente  

---

## 🔴 CRÍTICO — Seguridad

### #31 - Endpoints admin sin `require_admin` (escalada de privilegios)
**Módulo:** Backend / Auth  
**Descripción:** Auditoría detectó que el middleware solo valida sesión genérica — no diferencia admin de cliente. Encontrado:
- `routes/clientes.py`: **6 endpoints** sin `require_admin` (listar/ver/crear/modificar/borrar clientes + ver sus pedidos)
- `routes/alquileres.py`: **14 endpoints** sin `require_admin` (CRUD completo de pedidos, pagos, PDFs)
- `routes/estadisticas.py`: **2 endpoints** sin `require_admin` (estadísticas del negocio)

**Impacto:** Cualquier cliente logueado en el portal podía:
- Ver datos personales (email/teléfono/dirección/CUIT) de TODOS los clientes
- Ver, modificar o borrar pedidos ajenos
- Acceder a estadísticas y montos del negocio

**Estado:** ✅ Resuelto (PR #38) — `require_admin(request)` agregado a los 22 endpoints. `/disponibilidad` sigue público. `create_pedido` refactorizado en dos: endpoint admin + helper (`cliente_portal.cliente_crear_pedido` sigue usándolo con su `require_cliente` propio).

---
