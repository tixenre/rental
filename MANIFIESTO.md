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

### Branches

- `main` — siempre estable, deployable.
- `claude/<descripcion>` — branches de Claude. Una por PR.
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

### Mobile gate

Cualquier PR que toque rutas de cliente (`/`, `/equipo/*`, `/cliente/*`, `/estudio`) o admin prioritario (`/admin/pedidos`, `/admin/dashboard`) requiere mobile pass antes de mergear. Checklist en [`docs/PROTOCOLO.md`](docs/PROTOCOLO.md) y detalle en [`docs/MOBILE_AUDIT.md`](docs/MOBILE_AUDIT.md).

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
- **Columna DB `roi_pct`**: nombre técnicamente incorrecto. El valor es "% del valor del equipo cobrado por día" (tarifa diaria). Label UI pendiente de rename.

---

## 5. Estado actual

### Features activas

- **Form V2 de equipos** con autocompletar (single + batch) + cache de scrape.
- **Bulk actions** en lista admin.
- **Soft delete** + papelera + restore.
- **Mantenimiento log** por equipo.
- **Dashboard de uso** con top alquilados, sin uso, revenue por categoría, cuentas por cobrar.
- **Historial de alquileres** por equipo.
- **Búsqueda fuzzy global** en `q` de listEquipos.
- **Specs normalizer** EN→ES + métrico.
- **Catálogo público** con cart, cotización, portal cliente.
- **Tests E2E** del form (skipped en CI sin backend orchestrado).

### Cosas que NO existen todavía

Aclaración para no buscarlas en vano:

- Pagos online (Stripe, MercadoPago) — pagos manuales por fuera.
- Notificaciones email a clientes / admin.
- Multi-tenant.
- Dark mode.
- App mobile nativa.

---

## 6. Pendientes / decisiones abiertas

Items que están en discusión o que requieren tu input antes de hacerse. **No son issues todavía** — se vuelven issues cuando hay decisión.

### Decisiones pendientes de input

- **Rename `roi_pct` label**: el campo no es ROI técnicamente, es "% del valor cobrado por día". Candidatos: `Tarifa diaria %` / `% diario` / `Coeficiente diario` / `% amortización`. Mi pick: `Tarifa diaria %`. Decidir antes de hacer issue.
- **Specs templates por categoría**: cuándo aplicar (manual al guardar, auto al cambiar categoría, o solo como hint visual). Decisión pendiente.

### Ideas backlog (sin commitment todavía)

Históricamente en `docs/MEJORAS.md`. Lista resumida — el detalle queda allí marcado contra lo hecho:

- **Productividad admin**: persistir filtros en URL, atajo `n` para nuevo equipo, confirmación al cerrar form con cambios.
- **Data preservation**: histórico de fotos por equipo, versiones de la ficha técnica.
- **Cliente UX**: carrito persistente (localStorage), compartir equipo (link directo), skeleton loaders en catálogo.
- **Polish**: empty states con ilustración, loading states consistentes, mejor manejo de imágenes rotas.
- **DX**: `uv` para Python, logger estructurado JSON, pre-commit hook con lint/typecheck.
- **Features grandes**: pagos online, notificaciones email, app cliente expandida.

Cuando una idea pase a "vamos a hacerlo", se abre un GitHub issue con label `feature` y prioridad.

### Bugs activos

Hoy: **cero**. Histórico cerrado en [`docs/BUGS.md`](docs/BUGS.md) (referencia).

Reportar bugs nuevos como issues con label `bug` + prioridad. **No** abrir un `BUGS.md` nuevo.

---

## 7. Cómo arrancar una sesión nueva con Claude

Este manifiesto se carga al inicio. Si Claude se pierde, decirle:

```
Releé MANIFIESTO.md y los issues abiertos en https://github.com/tixenre/rental/issues.
```

Otros docs que puede tener que abrir según la tarea:

- `docs/PROTOCOLO.md` — workflow de PRs / auditoría.
- `docs/DEPLOY_RAILWAY.md` — deploy.
- `docs/MOBILE_AUDIT.md` — checklist mobile.
- `docs/DISEÑO_SPECS.md` — diseño del sistema de specs.

Para ver pendientes:

- `gh issue list --state open --label feature` — features abiertas.
- `gh issue list --state open --label bug` — bugs reportados.

---

## 8. Histórico — sesiones grandes

| Sesión | Resumen | PRs |
|---|---|---|
| **2026-05-10** | Auditoría inicial: 23 bugs trackeados y todos cerrados. Ver `docs/BUGS.md`. | PRs #26-#40 |
| **2026-05-12** (fase 1) | V2 del form de equipos: completion workflow, autocompletar con cache, batch, bulk actions, soft delete, mantenimiento, historial, dashboard de uso, tests E2E, split del form, refactor backend. | #211-#217, #221-#224 |
| **2026-05-12** (fase 2) | Limpieza post-fase-1, cuentas por cobrar en dashboard, manifiesto. | #225-#227, #228 (este PR) |
