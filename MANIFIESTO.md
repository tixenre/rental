# Manifiesto — Rambla Rental

> **Contexto del proyecto para Claude.** Acá vive lo que necesita saber para no
> arrancar desde cero: qué es el proyecto, cómo trabajamos, decisiones tomadas.
> No se pega a mano: lo apunta [`CLAUDE.md`](CLAUDE.md) (el front door que Claude Code
> auto-carga al inicio de cada sesión). El supervisor lo lee en su propia ventana.
>
> Si algo cambia (workflow, decisión, herramienta), se actualiza acá. Las **decisiones
> de criterio y preferencias nuevas** van a [`docs/MEMORIA.md`](docs/MEMORIA.md) (memoria
> viva, curada). El [`README.md`](README.md) cubre la cara de GitHub (setup, stack, links).

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

**Branch + PR siempre.** Todo cambio va en una rama dedicada y se mergea por PR contra `main` — corra Claude donde corra (apps de Mac/iPhone sobre sesiones en la nube, o la CLI local). **No se commitea directo a `main`.**

Una **iniciativa** = una **rama** (`claude/<descripcion>`) = una **PR** con N commits atómicos adentro. El dev server (local) o el deploy reflejan los cambios para probar.

```
Edit → commit atómico en la rama → (N veces) → push → PR → supervisor + CI → merge
```

**La memoria del proyecto vive en capas** (detalle en §8):

- **[`docs/MEMORIA.md`](docs/MEMORIA.md)** — decisiones de criterio + preferencias (el *por qué*, curado y duradero). Lo que el supervisor hace cumplir.
- **Commit history** — registro de cambios. Conventional Commits en español; `git log --grep="^fix"` / `"^feat"` son el log buscable.
- **GitHub Issues** — trabajo pendiente (la cola). No es obligatorio por commit.

### Modus operandi durable, sesión efímera

El **cómo se trabaja acá** es durable y vive en estos docs + `docs/MEMORIA.md`. La sesión es efímera: carga la forma establecida vía `CLAUDE.md` y **ejecuta**. No re-discute el modus operandi.

El **plan de una tarea** depende del alcance:

- **Cabe en una sesión** → se planea en la sesión (plan mode) y se ejecuta. No necesita persistencia.
- **Iniciativa que cruza varias sesiones** → un **issue de tracking por iniciativa** (con checklist de fases adentro — **NO un issue por fase**), **auto-mantenido por la sesión** que ejecuta (marca fases hechas, anota desvíos). Así una sesión nueva la retoma sin perder contexto. El supervisor verifica que esté actualizado antes de mergear.

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
- Body: 3 secciones — Summary / Cambios / **Test plan en lenguaje claro** (el dueño testea, no lee código: "andá a /X, hacé Y, tenés que ver Z").
- Si la iniciativa tiene issue de tracking: linkear con `Closes #N`.
- **CI verde antes de mergear** (TypeScript typecheck, Python tests, Build frontend, mobile-smoke). La sesión **no propone merge con CI en rojo**.
- **Antes de abrir/mergear: despachar el agente `supervisor`** — revisión read-only de scope / forma / drift, que resume en claro y deja el plan de prueba. (Instrucción, no gate de sistema: en las apps no hay hooks.)
- **Merge según tamaño** (el supervisor ayuda a clasificar):
  - **Trivial / small** con CI verde + supervisor OK → **auto-merge** (CI verde → GitHub mergea sola, borra la branch).
  - **Sensible / arquitectónico / grande**, o que toca lo que ve el usuario → **PR draft + el dueño prueba** antes de mergear. GitHub no auto-mergea drafts. (Pre-lanzamiento: el dueño prueba en prod, ver §6.)
  - **Opt-out por PR**: pedir explícitamente "no auto-merge esta" — se deja sin habilitar.
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
| **Motor de reservas (sagrado)** | `backend/reservas/` (`estados.py`, `semantics.py`, `disponibilidad.py`, `gate.py`) — disponibilidad + gate `_check_stock`. Ver MEMORIA 2026-05-30 |
| Configuración (Settings) | `backend/config.py` (fuente de `ADMIN_EMAILS`, etc.) |
| Procesamiento/upload de imágenes + anti-SSRF | `backend/services/image_upload.py` |
| Schema base + pool DB | `backend/database.py` |
| Schema de specs / categorías | `backend/specs/` (`__init__.py` define `REGISTRY`; una cat por archivo en `categorias/`) |
| Migrations Alembic | `backend/migrations/versions/` |
| Auth admin | `backend/admin_guard.py` |
| Auth cliente | `backend/routes/auth.py` |

---

## 6. Decisiones del proyecto

> Lecciones aprendidas y elecciones arquitectónicas. Útil para no re-discutir cosas.
>
> **Baseline fundacional.** Estas son las decisiones de arquitectura que vinieron con el
> proyecto. Las **decisiones nuevas y preferencias** van a [`docs/MEMORIA.md`](docs/MEMORIA.md)
> (fechadas, curadas) — no se agregan acá. El supervisor lee ambos.
>
> **Pre-lanzamiento (con disparador):** la web aún no es pública; el dueño es el único usuario
> de prueba, así que **probar en producción está OK** (no hay clientes que se crucen algo roto).
> **Disparador:** al salir al público, esto se vence → recién ahí hace falta preview/staging y
> dejar de probar en prod. El supervisor avisa al acercarse el lanzamiento. (Registrada en
> `docs/MEMORIA.md`.)

### Auth

- **Admin**: Google OAuth → sesión cookie firmada. `require_admin(request)` en cada endpoint admin.
- **Cliente**: Google OAuth separado → cookie `cliente_session` distinta. `require_cliente(request)` valida `role: "cliente"` (no acepta sesiones admin).
- **Dev mode**: `ADMIN_BYPASS_AUTH=1` en `.env.local` saltea la validación. Lo usan los tests E2E (con `PLAYWRIGHT_ADMIN=1`).

### Base de datos

- **Postgres puro** (migró de SQLite). El wrapper `PGCursor` traduce placeholders `?`→`%s` para no reescribir cientos de queries.
- **Migraciones**: schema base con `CREATE IF NOT EXISTS` en `backend/database.py::init_db()`. Cambios incrementales con Alembic (`backend/migrations/versions/`).
- **Soft delete**: equipos tienen `eliminado_at TIMESTAMP NULL`. Las listas filtran `IS NULL` por default. Endpoint `POST /equipos/:id/restore`. Vista "papelera" en lista admin. Bulk delete en papelera = hard delete (action `delete_permanent`).

### Storage de fotos

- Vive en `backend/services/image_upload.py` (extraído de `routes/equipos.py` en #501 Fase 3; lo reusan equipos/marcas/estudio/settings).
- R2 (S3-compatible). Cada foto se sube con upload server-side desde una URL externa o un archivo local.
- Allowlist anti-SSRF para URLs externas (`_validate_external_image_url`). Hosts conocidos (B&H, Adorama, manufacturer domains, CDNs).
- Las fotos se procesan con `_optimize_image`: auto-crop de whitespace, padding 6%, resize a 1200×1200, ratio cuadrado.

### Form de equipos

- **EquipoFormDialogV2** es EL form. Sin tabs, scroll lineal con secciones colapsables. Mismo flow CREATE / EDIT.
- El form viejo (`EquipoFormDialog.tsx`) fue borrado — no resucitar.

### Sistema de specs / catálogo / datasets / autocompletar / compatibilidad

El detalle técnico de todo esto vive en **[`docs/SISTEMA_SPECS.md`](docs/SISTEMA_SPECS.md)**:
autocompletar (admin, por equipo), carga de datasets por categoría (seed bulk), motor de
compatibilidades cross-categoría, display templates de nombres, y los workflows para agregar
specs / sub-categorías. La fuente de verdad del schema es `backend/specs/__init__.py` (`REGISTRY`).

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

## 7. Sistema de specs (manual técnico)

Movido a **[`docs/SISTEMA_SPECS.md`](docs/SISTEMA_SPECS.md)** — el registry como fuente única del
schema, specs por categoría, sub-categorías, keywords automáticas, merge dataset↔DB y el flow
operativo. Reemplaza al borrador histórico (ahora en `docs/archive/DISEÑO_SPECS.md`).

---

## 8. Dónde encontrar cosas

### Memoria en capas — cada cosa en su lugar

La memoria está separada por propósito (no se duplica):

| Querés saber… | Dónde |
|---|---|
| **Por qué decidimos algo / cómo quiere el dueño que se hagan las cosas** | [`docs/MEMORIA.md`](docs/MEMORIA.md) — decisiones de criterio + preferencias, curado y fechado. **El supervisor lo hace cumplir.** |
| Decisiones de arquitectura fundacionales | §6 de este manifiesto (baseline congelado) |
| Qué hay pendiente / en curso | GitHub Issues (la cola). `gh issue list` localmente, o las tools de GitHub en la nube |
| Qué cambió y cuándo | Commit history (`git log --grep="^feat"` / `"^fix"`) |

Regla: **trabajo pendiente** → Issues. **Registro de cambios** → commits/PRs. **El *por qué* y las
preferencias** → `docs/MEMORIA.md` (curado, no exhaustivo: solo lo que tiene consecuencia
duradera o se repite). Si una funcionalidad existe en código y no está trackeada, crear el issue.
Histórico: `docs/archive/` conserva auditorías viejas (`BUGS.md`, `MEJORAS.md`).

### Docs auxiliares

| Archivo | Cuándo |
|---|---|
| [`docs/MEMORIA.md`](docs/MEMORIA.md) | Decisiones de criterio + preferencias (memoria viva, curada) |
| [`docs/PROTOCOLO.md`](docs/PROTOCOLO.md) | Workflow de PRs, auditoría, mobile gate |
| [`docs/DEPLOY_RAILWAY.md`](docs/DEPLOY_RAILWAY.md) | Deploy y rollback |
| [`docs/SISTEMA_SPECS.md`](docs/SISTEMA_SPECS.md) | **Manual técnico del sistema de specs / catálogo / datasets / autocompletar / compat** |
| [`docs/FLUJO_PEDIDOS.md`](docs/FLUJO_PEDIDOS.md) | Recorrido del pedido: estados, confirmación visible, mails, `id` vs `numero_pedido` |
| [`docs/MOBILE.md`](docs/MOBILE.md) | Componentes y patrones mobile |
| [`docs/MOBILE_AUDIT.md`](docs/MOBILE_AUDIT.md) | Criterio mobile + checklist + status por ruta |
| [`docs/DATASET_ILUMINACION.md`](docs/DATASET_ILUMINACION.md) | Dataset curado de luces + workflow seed por categoría |
| [`docs/ISSUE_LABELS.md`](docs/ISSUE_LABELS.md) | Convención de labels |

### Cosas que NO existen todavía

Aclaración para no buscarlas en vano: pagos online (Stripe/MercadoPago), multi-tenant, dark mode, app mobile nativa.

Las **notificaciones por email** sí están **construidas** (`backend/services/email/`, plantillas editables en `/admin/email-templates`) pero **no activadas** — caen al backend `test` hasta configurar el proveedor (`RESEND_API_KEY`/`SMTP_*`). Ver [`docs/FLUJO_PEDIDOS.md`](docs/FLUJO_PEDIDOS.md) §3.

### Sesión nueva pierde el rumbo

Si Claude se pierde a mitad de sesión: `Releé CLAUDE.md, MANIFIESTO.md, docs/MEMORIA.md y los issues abiertos en https://github.com/tixenre/rental/issues`.
