# Manifiesto — Rambla Rental

> **Memoria para Claude.** Este archivo es el prompt que se carga al inicio de
> cualquier sesión con Claude. Acá vive lo que necesita saber para no
> arrancar desde cero: qué es el proyecto, cómo trabajamos, decisiones tomadas,
> qué está pendiente.
>
> Si algo cambia (workflow, decisión, herramienta), se actualiza acá.
> El [`README.md`](README.md) cubre la cara de GitHub (setup, stack, links). Este archivo cubre el contexto.

---

## 1. Qué es el proyecto

**Rambla Rental** — plataforma de alquiler de equipos audiovisuales.

3 superficies:

- **Catálogo público** (`/`) — clientes ven equipos, arman cotización.
- **Portal cliente** (`/cliente/*`) — login, ver mis pedidos, perfil.
- **Back-office admin** (`/admin/*`) — gestión total: equipos, pedidos, clientes, mantenimiento, dashboard de uso, etc.

Un único dueño/operador maneja el back-office. Inventario chico-mediano (cientos de equipos), volumen de alquileres mensual moderado.

---

## 2. Stack

| Capa | Tech |
|---|---|
| Frontend | React 19 + Vite + TanStack Router (file-based) + TanStack Query + Tailwind v4 + shadcn/Radix UI |
| Backend | FastAPI + psycopg2 + PostgreSQL (pool de conexiones) |
| Auth | Google OAuth via Supabase Auth (admin + portal cliente) |
| Storage | Cloudflare R2 (S3-compatible) para fotos |
| Drag-and-drop | `@dnd-kit/*` |
| Form state | `react-hook-form` + `zod` para validación |
| Deploy | Railway (backend + frontend en un mismo servicio Docker) |

Detalles de setup en [`README.md`](README.md). Detalles de Railway en [`docs/DEPLOY_RAILWAY.md`](docs/DEPLOY_RAILWAY.md).

---

## 3. Cómo trabajamos

### Workflow

Toda mejora / bug / feature se trackea como **GitHub Issue → PR contra `main` → review → merge → cleanup branch**. No hay listas informales en archivos markdown que sean "el roadmap real".

```
Idea → Issue → Branch → PR (draft) → CI verde → ready for review → merge → branch deleted
```

Excepciones:

- **Cambios triviales** (typo, dead import) → PR directo, sin issue.
- **Decisiones de arquitectura / diseño** → docs en `docs/` (ej. `DISEÑO_SPECS.md`).
- **Ideas tempranas sin compromiso** → este manifiesto, sección "Pendientes / Ideas".

### Planes multi-fase → issues

Cuando Claude diseña un plan que se ejecuta en varias fases (refactor grande, feature con backend + frontend, migración por pasos), **cada fase es un GitHub issue independiente**. El plan no vive en un archivo markdown ni en la memoria de una sesión.

Por qué:

- **Sesión-agnóstico**: cualquier sesión nueva puede tomar una fase pendiente y avanzarla sin contexto perdido.
- **Tracking real**: el estado del trabajo se ve en `gh issue list`, no releyendo conversaciones viejas.
- **Reordenar prioridades**: si una fase queda obsoleta o cambia de prioridad, se edita / cierra el issue, no se reescribe el plan entero.

Cada issue describe la fase con: contexto, scope (checklist accionable), cómo (pasos concretos), verificación, y por qué de los labels.

### Una iniciativa = una rama = una PR

**Default**: el trabajo de una iniciativa entera (aunque tenga N fases / N issues) va en **una sola rama con N commits adentro**, y se mergea como **una sola PR** que cierra todos los issues con varios `Closes #N`.

Por qué: minimiza el costo de review + merge + deploy. Una iniciativa = 1 review, 1 merge, 1 deploy — no N.

Pattern del commit history adentro de la rama:

```
feat(ui): wrappers chrome (Logo, PublicLayout, TopBar variant)
refactor(ui): rutas con drift a PublicLayout
refactor(ui): rutas restantes a PublicLayout
docs(mobile): criterio mobile en MOBILE_AUDIT
fix(mobile): tap targets en PedidoPage
...
```

Cada commit es atómico y revertible. La PR los publica en bloque.

**Excepción explícita**: para algo chico y aislado (typo, una decisión de label puntual, un bug fix de 5 líneas que no está atado a una iniciativa más grande), pedir abrir una **PR separada** de forma explícita. Sin esa indicación, default es agregar al branch en curso.

### Branches

- `main` — siempre estable, deployable.
- `claude/<descripcion>` — una rama por **iniciativa** (no por fase / no por commit). Múltiples commits dentro.
- `bugs` / `features` — branches long-lived legacy del workflow viejo. **NO usar para nuevo trabajo**; quedaron porque hay docs que las mencionan.

Después de mergear: **borrar la branch local** (`git branch -d`) **y remota** (`git push origin --delete`). Sin colgadas.

### Commits

Estilo `tipo(scope): descripción en español, lowercase, sin punto final`.

Tipos: `feat`, `fix`, `refactor`, `chore`, `docs`, `perf`, `test`.

Body explica el **por qué**, no el **qué**. Bullets si hay varios efectos.

`Co-Authored-By: Claude <noreply@anthropic.com>` al final si fue trabajo colaborativo. (Hoy ya no se usa con frecuencia, pero queda como convención.)

### PRs

- Título: igual al commit principal.
- Body: 3 secciones — Summary / Cambios / Test plan.
- Linkear el issue con `Closes #N`.
- CI debe estar verde antes de mergear (TypeScript typecheck, Python tests, Build frontend, mobile-smoke).
- Conflicts con main: rebase / merge desde el branch (no force-push a main).

Detalle completo del flow en [`docs/PROTOCOLO.md`](docs/PROTOCOLO.md).

### Issues — labels

**Cada issue se etiqueta en 3 dimensiones** + opcionales cross-cutting. Sin las 3 dimensiones la issue queda incompleta y no se prioriza.

1. **Tipo** (1, obligatoria): `bug` / `feature` / `design` / `refactor` / `documentation` / `security`.
2. **Prioridad** (1, obligatoria): `priority:critical` / `priority:high` / `priority:medium` / `priority:low`.
3. **Complejidad** (1, obligatoria): `complexity:trivial` / `complexity:small` / `complexity:medium` / `complexity:large` / `complexity:epic`.

**Cross-cutting** (0+, opcionales): `mobile`, `dx`, `infrastructure`, `performance`, `launch-blocker`, `backend`, `admin`.

Regla del `mobile`: aplicar **además** del tipo, no en lugar de. Aplica si la issue afecta rutas cliente o admin prioritario (`/admin/pedidos`, `/admin/dashboard`). Resto del admin = desktop-first.

Convención completa + cómo elegir issues por capacidad de la sesión en [`docs/ISSUE_LABELS.md`](docs/ISSUE_LABELS.md).

**Al crear un issue nuevo**: aplicar las 3 dimensiones siempre. Si no estás seguro de la prioridad, `priority:medium`. Si no estás seguro de la complejidad, mirar el body — > 1 día = `complexity:medium`, sino `complexity:small`.

### Mobile como criterio

**Cada ruta debe tener un layout mobile pensado a propósito, no solo un escalado responsive automático.** No alcanza con "se ve más o menos OK en celu" — necesitamos un patrón visible (dual render `md:hidden`/`hidden md:block`, sticky bar, sheet fullscreen, lista card-based) y validación manual en viewport 375×667 (iPhone SE).

Gate de merge: cualquier PR que toque rutas de cliente (`/`, `/equipo/*`, `/cliente/*`, `/estudio`) o admin prioritario (`/admin/pedidos`, `/admin/dashboard`) requiere mobile pass antes de mergear.

El wrapper [`<PublicLayout>`](src/components/rental/PublicLayout.tsx) provee TopBar + Footer mobile-aware, pero **no garantiza el criterio** — el contenido de cada ruta tiene que cumplirlo por su cuenta.

Definición completa del criterio, checklist y status por ruta en [`docs/MOBILE_AUDIT.md`](docs/MOBILE_AUDIT.md). Procedimiento en [`docs/PROTOCOLO.md`](docs/PROTOCOLO.md).

---

## 4. Decisiones del proyecto

> Lecciones aprendidas y elecciones arquitectónicas. Útil para no re-discutir cosas.

### Auth

- **Admin**: Google OAuth → sesión cookie firmada. `require_admin(request)` en cada endpoint admin.
- **Cliente**: Google OAuth separado → cookie `cliente_session` distinta. `require_cliente(request)` valida `role: "cliente"` (no acepta sesiones admin).
- **Dev mode**: `ADMIN_BYPASS_AUTH=1` en `.env.local` saltea la validación. Lo usan los tests E2E (con `PLAYWRIGHT_ADMIN=1`).

### Base de datos

- **Postgres puro** (migró de SQLite). El wrapper `PGCursor` traduce placeholders `?`→`%s` para no reescribir cientos de queries.
- **Migraciones**: schema base con `CREATE IF NOT EXISTS` en `backend/database.py::init_db()`. Cambios incrementales con Alembic (`backend/migrations/versions/`).
- **Soft delete**: equipos tienen `eliminado_at TIMESTAMP NULL`. Las listas filtran `IS NULL` por default. Endpoint `POST /equipos/:id/restore`. Vista "papelera" en lista admin. Bulk delete en papelera = hard delete (action `delete_permanent`).

### Storage de fotos

- R2 (S3-compatible). Cada foto se sube con upload server-side desde una URL externa o un archivo local.
- Allowlist anti-SSRF para URLs externas (`_validate_external_image_url`). Hosts conocidos (B&H, Adorama, manufacturer domains, CDNs).
- Las fotos se procesan con `_optimize_image`: auto-crop de whitespace, padding 6%, resize a 1200×1200, ratio cuadrado.

### Form de equipos

- **EquipoFormDialogV2** es EL form. El form viejo (`EquipoFormDialog.tsx`) fue borrado.
- Sin tabs, scroll lineal con secciones colapsables (Identificación, Ficha técnica, Kit, Avanzado).
- Mismo flow CREATE / EDIT.
- Drag-and-drop en specs y kit con `@dnd-kit`.
- Cmd/Ctrl+S guarda. Esc cierra.
- Status switches en el top: Visible en catálogo + Ficha completa.
- Sub-componentes extraídos: `KitEditor.tsx`, `SpecsDiffEditor.tsx`, `spec-helpers.ts`. El resto (`PhotoCard`, `CategoriasPicker`, `LinkInput`, `Field`, `CollapsibleSection`) sigue inline.

### Autocompletar de specs

- **URL única** en la autocompletar bar: bindeada al campo `bh_url` del form, con botones copy/abrir inline.
- **Backend**: endpoint canónico `POST /admin/equipos/autocompletar` (alias deprecated `/enriquecer`). Scrape con Firecrawl + extract con LLM. Devuelve `AutocompletarResult` normalizado.
- **Normalizer de specs**: backend traduce labels EN→ES (Weight→Peso, Lens Mount→Montura, etc.) y convierte unidades (lbs→kg, in→cm, °F→°C, ranges, dimensiones N×N×N).
- **Cache del scrape**: el `AutocompletarResult` completo se guarda en `equipo_fichas.raw_json`. Habilita botones ✨ por sección en el form V2 que re-aplican campos sin volver a scrapear.
- **Batch**: `POST /admin/equipos/batch-enriquecer` procesa hasta 3 equipos por request (cap defensivo, max 50 ids en body). Frontend re-batchea hasta terminar. Resultado se persiste en raw_json (cache). Sleep 1s entre scrapes para no rate-limitear B&H.

### Bulk actions en lista admin

- Checkbox por fila + barra flotante con: Mostrar/Ocultar, Marcar completas/pendientes, Eliminar (soft).
- En vista papelera: el botón "Eliminar permanente" hace hard delete (`action: delete_permanent`).
- Hasta 500 ids por request (defensivo).

### Búsqueda fuzzy

- El parámetro `q` en `GET /equipos` busca en `nombre`, `marca`, `modelo`, `serie`, `descripcion`, `specs_json`, `keywords_json`. Aplicable a admin lista y catálogo público.
- Limitación: LIKE crudo sobre JSON → posibles falsos positivos si buscás field names tipo "label" o "value". Aceptable para inventario chico-mediano.

### Mantenimiento

- Tabla `equipo_mantenimiento` con `fecha`, `tipo` (revision/reparacion/limpieza/otro), `descripcion`, `costo` (ARS), `proxima_revision`.
- Modal CRUD desde la lista admin (botón Wrench por fila).
- Badge rojo si `proxima_revision` está vencida.

### Dashboard de uso

- `GET /admin/dashboard/uso`: top alquilados, sin uso (>90 días), revenue por categoría, cuentas por cobrar.
- Implementado como Dialog desde la lista admin (botón "Uso"), no como ruta separada — evita tocar `routeTree.gen.ts` auto-generado.
- "Por cobrar" suma `monto_total - monto_pagado` para pedidos en estados `confirmado`, `retirado`, `devuelto`, `finalizado` que todavía tienen saldo.

### Naming conventions

- **Frontend**: ya migró a "autocompletar" como nombre del feature.
- **Backend**: endpoints canónicos `/autocompletar`. Los viejos `/enriquecer` quedan como aliases deprecated.
- **Nombres de funciones internas** (`aplicarEnriquecimiento`, `admin_enriquecer_equipo`, `EnriquecerInput`) siguen con el nombre viejo — rename completo es un follow-up cuando duela.
- **Columna DB `roi_pct`**: nombre técnicamente incorrecto. El valor es "% del valor del equipo cobrado por día" (tarifa diaria). **Label canónico en UI**: `% día` (decisión cerrada — #262). La columna DB sigue como `roi_pct` por costo de migración vs valor — solo lo ve dev en queries. El admin ve "% día".

---

## 5. Estado actual

### Dónde se ve qué está hecho

Este manifiesto **no lleva el changelog**. El registro de qué se construyó, cuándo y con qué PR vive en **GitHub Issues cerrados**:

```
gh issue list --state closed --label feature   # features entregadas
gh issue list --state closed --label bug       # bugs cerrados
gh issue list --state closed                   # todo el histórico
```

Cada iniciativa tiene su issue con contexto, scope, PRs incluidos y verificación. Si querés saber por qué algo está como está, el issue es la fuente — no este archivo.

Para una idea rápida de qué hay en producción, el código manda: rutas activas en `src/routes/`, endpoints en `backend/routes/`. Si una funcionalidad existe en código y no en issues, es un gap que hay que cerrar (crear el issue retroactivo).

### Cosas que NO existen todavía

Aclaración para no buscarlas en vano:

- Pagos online (Stripe, MercadoPago) — pagos manuales por fuera.
- Notificaciones email a clientes / admin.
- Multi-tenant.
- Dark mode.
- App mobile nativa.

---

## 6. Cómo arrancar una sesión nueva con Claude

Este manifiesto se carga al inicio. Si Claude se pierde, decirle:

```
Releé MANIFIESTO.md y los issues abiertos en https://github.com/tixenre/rental/issues.
```

Otros docs que puede tener que abrir según la tarea:

- `docs/PROTOCOLO.md` — workflow de PRs / auditoría.
- `docs/DEPLOY_RAILWAY.md` — deploy.
- `docs/MOBILE_AUDIT.md` — checklist mobile.
- `docs/DISEÑO_SPECS.md` — diseño del sistema de specs.

Para ver el trabajo pendiente / activo (todo vive en GitHub Issues):

- `gh issue list --state open --label feature` — features abiertas.
- `gh issue list --state open --label bug` — bugs reportados.
- `gh issue list --state open --label design` — decisiones de diseño / UX.
- `gh issue list --state open` — todo el backlog.

---

## 7. Histórico

El histórico no vive acá. Cada sesión / iniciativa cierra su issue cuando termina, y la lista de issues cerrados (en orden cronológico) **es** el changelog del proyecto:

```
gh issue list --state closed --sort created --order desc
```

Excepción documental: `docs/BUGS.md` conserva la auditoría inicial del 2026-05-10 (23 bugs históricos) porque precede a la convención de issues.
