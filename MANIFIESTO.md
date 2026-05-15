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
- **Ideas tempranas sin compromiso** → issue con `priority:low` (o conversación con el dueño antes de abrirlo).

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

Cada commit dentro de la rama es atómico y revertible. La PR los publica en bloque.

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

## 4. Glossary

Cuatro nociones que se cruzan a lo largo del producto. Distinguirlas evita confusión:

- **Categoría** — árbol jerárquico de hasta 3 niveles (ej. Cámara → Cinema → FX3). Cada equipo pertenece a una o más. Determina el filtro principal del catálogo público y dispara el spec template + plantilla de nombre.
- **Etiqueta** — tag libre, plano (sin jerarquía). Atraviesa categorías (ej. "Sony E mount" puede aplicar a cámaras y a lentes). Filtro secundario.
- **Spec** — fila clave-valor adjunta a un equipo (`Sensor: Full Frame`). Lo técnico que se ve en la ficha. Tipo `text` o `number` (con unidad).
- **Spec Template** — norma de specs **por categoría**. Define qué labels deben existir en cada equipo de esa categoría, en qué orden, con qué tipo y unidad. Heredan automáticamente al crear un equipo nuevo. "AI sugiere, humano cura" → el autocompletar respeta el template como hint.

---

## 5. Mapa del código

Puntos de entrada para no grepear:

| Qué | Dónde |
|---|---|
| Rutas frontend (file-based) | `src/routes/` |
| Componentes admin | `src/components/admin/` |
| Form V2 de equipos | `src/components/admin/equipo-form-v2/` |
| Lógica reusable / utilities UI | `src/lib/` |
| Endpoints backend | `backend/routes/` (`equipos.py`, `clientes.py`, `dashboard.py`, etc.) |
| Schema base + pool DB | `backend/database.py` |
| Migrations Alembic | `backend/migrations/versions/` |
| Auth admin | `backend/admin_guard.py` |
| Auth cliente | `backend/routes/auth.py` |
| Storage R2 + scrape + optimize foto | dentro de `backend/routes/equipos.py` |

---

## 6. Decisiones del proyecto

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

- **EquipoFormDialogV2** es EL form. Sin tabs, scroll lineal con secciones colapsables. Mismo flow CREATE / EDIT.
- El form viejo (`EquipoFormDialog.tsx`) fue borrado — no resucitar.

### Autocompletar de specs

- **URL única** en la autocompletar bar: bindeada al campo `bh_url` del form, con botones copy/abrir inline.
- **Backend**: endpoint canónico `POST /admin/equipos/autocompletar` (alias deprecated `/enriquecer`). Scrape con Firecrawl + extract con LLM. Devuelve `AutocompletarResult` normalizado.
- **Normalizer de specs**: backend traduce labels EN→ES (Weight→Peso, Lens Mount→Montura, etc.) y convierte unidades (lbs→kg, in→cm, °F→°C, ranges, dimensiones N×N×N).
- **Cache del scrape**: el `AutocompletarResult` completo se guarda en `equipo_fichas.raw_json`. Habilita botones ✨ por sección en el form V2 que re-aplican campos sin volver a scrapear.
- **Batch**: `POST /admin/equipos/batch-enriquecer` procesa hasta 3 equipos por request (cap defensivo, max 50 ids en body). Frontend re-batchea hasta terminar. Resultado se persiste en raw_json (cache). Sleep 1s entre scrapes para no rate-limitear B&H.

### Bulk actions en lista admin

- En vista normal: las bulk actions son soft (`delete` → marca `eliminado_at`).
- En vista papelera: `delete_permanent` hace hard delete. Es la única forma de borrar irreversible.

### Búsqueda fuzzy

- El parámetro `q` en `GET /equipos` busca en `nombre`, `marca`, `modelo`, `serie`, `descripcion`, `specs_json`, `keywords_json`. Aplicable a admin lista y catálogo público.
- Limitación: LIKE crudo sobre JSON → posibles falsos positivos si buscás field names tipo "label" o "value". Aceptable para inventario chico-mediano.

### Mantenimiento

- Log por equipo (`equipo_mantenimiento`) con tipo, costo y `proxima_revision`. Vencidas se marcan visualmente en la lista admin.

### Dashboard de uso

- Dialog desde la lista admin, no ruta separada — evita ediciones de `routeTree.gen.ts` auto-generado.
- "Por cobrar" excluye `cancelado` y `borrador`. Solo cuenta pedidos con compromiso real de pago.

### Naming conventions

- **Frontend**: ya migró a "autocompletar" como nombre del feature.
- **Backend**: endpoints canónicos `/autocompletar`. Los viejos `/enriquecer` quedan como aliases deprecated.
- **Nombres de funciones internas** (`aplicarEnriquecimiento`, `admin_enriquecer_equipo`, `EnriquecerInput`) siguen con el nombre viejo — rename completo es un follow-up cuando duela.
- **Columna DB `roi_pct`**: nombre técnicamente incorrecto. El valor es "% del valor del equipo cobrado por día" (tarifa diaria). **Label canónico en UI**: `% día` (decisión cerrada — #262). La columna DB sigue como `roi_pct` por costo de migración vs valor — solo lo ve dev en queries. El admin ve "% día".

---

## 7. Dónde encontrar cosas

### Backlog, changelog, decisiones puntuales

**Todo vive en GitHub Issues.** Este manifiesto no duplica el contenido — solo apunta.

| Querés saber… | Comando |
|---|---|
| Qué hay pendiente | `gh issue list --state open` |
| Qué features están en curso | `gh issue list --state open --label feature` |
| Qué bugs hay reportados | `gh issue list --state open --label bug` |
| Qué se entregó (changelog) | `gh issue list --state closed --sort created --order desc` |
| Por qué algo está como está | abrir el issue cerrado de esa iniciativa |

Si una funcionalidad existe en código y no en issues, es un gap → crear el issue retroactivo. Excepción documental: `docs/BUGS.md` conserva la auditoría inicial del 2026-05-10 (precede la convención).

### Docs auxiliares

| Archivo | Cuándo |
|---|---|
| [`docs/PROTOCOLO.md`](docs/PROTOCOLO.md) | Workflow de PRs, auditoría, mobile gate |
| [`docs/DEPLOY_RAILWAY.md`](docs/DEPLOY_RAILWAY.md) | Deploy y rollback |
| [`docs/MOBILE_AUDIT.md`](docs/MOBILE_AUDIT.md) | Checklist mobile + status por ruta |
| [`docs/DISEÑO_SPECS.md`](docs/DISEÑO_SPECS.md) | Sistema de specs / templates |
| [`docs/ISSUE_LABELS.md`](docs/ISSUE_LABELS.md) | Convención de labels |

### Cosas que NO existen todavía

Aclaración para no buscarlas en vano: pagos online (Stripe/MercadoPago), notificaciones por email, multi-tenant, dark mode, app mobile nativa.

### Sesión nueva pierde el rumbo

Si Claude se pierde a mitad de sesión: `Releé MANIFIESTO.md y los issues abiertos en https://github.com/tixenre/rental/issues`.
