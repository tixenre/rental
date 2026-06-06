# referencia-repo — molde para implementar handoffs

> Cheatsheet para Claude Code al implementar un handoff (lo usa el paso "reuse-first" + el cableado de
> datos/backend de [`SKILL.md`](./SKILL.md)). **Verificá con grep antes de asumir** — el repo evoluciona;
> esto es el mapa, no la verdad literal.

## 1. Catálogo de componentes canónicos (reusar antes que crear)

> **Fuente canónica = la librería del DS, que vive en la app:** `src/components/*` (primitivos +
> piezas) y `src/styles/` (tokens/tipografía/utilities/fuentes). No hay paquete aparte. La columna
> "Dónde" apunta al path real en `src/`.

| Necesitás… | Usá | Dónde (hoy, en la app) |
|---|---|---|
| Botón (variants: default, amber, **primary**, outline, ghost…) | `Button` | `src/components/ui/button.tsx` |
| Badge de estado de pedido | `EstadoBadge` | `src/components/kit/EstadoBadge.tsx` |
| Bloque de precio | `PriceBlock` | `src/components/kit/PriceBlock.tsx` (catálogo) · `src/components/rental/equipment/shared/PriceBlock.tsx` (cards) |
| Stat / métrica | `StatCard` | `src/components/kit/StatCard.tsx` |
| Stepper de cantidad (pill hairline) | `StepperPill` | `src/components/rental/equipment/shared/StepperPill.tsx` |
| Favorito | `FavButton` | `src/components/rental/equipment/shared/FavButton.tsx` |
| Pills de add-ons | `AddonPills` | `src/components/kit/AddonPills.tsx` |
| Toggle grid/lista | `ViewToggle` | `src/components/kit/ViewToggle.tsx` |
| Empty state | `EmptyState` | `src/components/kit/EmptyState.tsx` |
| Input/Search/FieldLabel | `Input` | `src/components/kit/Input.tsx` |
| Modal de fechas de reserva | `RentalDateModal` | `src/components/rental/RentalDateModal.tsx` (base única) |
| shadcn primitives (dialog, card, accordion, calendar, dropdown…) | varios | `src/components/ui/*` |
| `cn()` classnames | `cn` | `src/lib/utils.ts` |

**Librería canónica del DS — vive EN LA APP, en `src/`:** primitivos shadcn en `src/components/ui/*`,
piezas de marca en `src/components/{kit,rental}` (PriceBlock, StepperPill, EstadoBadge, StatCard…), y
tokens/tipografía/utilities/fuentes en `src/styles/` (entry `src/ds-styles.css`, cableado desde
`src/styles.css`). Es la **fuente única**: un token/utility se edita en `src/styles/`, una pieza en
`src/components/`, **no se duplica**. **Reuse-first:** antes de crear un botón/badge/precio/stepper/estado,
chequeá si ya existe. Un primitivo nuevo reutilizable va a `src/components/{ui,kit}`, no inline. Las
pantallas cableadas (carrito, topbar…) consumen esos primitivos. (Hubo un paquete workspace
`@rambla/design-system` que se consolidó acá — ya no existe.)

> **Assets de marca (logo/wordmark/favicon/og) → NO se recrean.** Salen de un motor backend único,
> `backend/services/branding/` (`rasterize.py` + `derive.py`): el dueño sube dos SVG master en
> `/admin/diseño` y el sistema deriva favicon / apple-touch / og:image / logo de mail / wordmark de los
> PDFs. Consumidores: **web** `Logo.tsx` (wordmark SVG **inline**, themable — nunca un `<img>` nuevo),
> **mail**, **PDFs** (`pdf_templates._active_wordmark`), **favicon** (`FaviconSync`). Decisión: MEMORIA
> *2026-06-06 — `backend/services/branding/` = motor único de assets de marca*. Si un diseño trae un
> logo, se cablea a este motor, no se hardcodea.

## 2. Data layer (cómo conecta datos una pantalla)

- **Fetch:** TanStack Query (`useQuery`) + hook custom. Patrón canónico: `src/hooks/useEquipos.ts`
  (`queryKey`, `queryFn`, `staleTime`). Pre-fetch SEO en rutas: loader + `queryClient.fetchQuery`
  (ej. `src/routes/equipo.$slug.tsx`).
- **HTTP + auth:** `authedFetch` / `authedJson` de `src/lib/authedFetch.ts` (cookie de sesión,
  `credentials:"include"`, base URL `VITE_API_URL`). No armar fetch a mano.
- **Tipos:** backend en `src/lib/api.ts` (`BackendEquipo`, `EstudioConfig`…); frontend en
  `src/data/equipment.ts` (`Equipment`) y `src/components/kit/types.ts` (`EstadoPedido` — 9 estados:
  borrador, presupuesto, solicitado, confirmado, retirado, entregado, devuelto, finalizado, cancelado).
- **Formato:** `formatARS()`, `formatRentalRange()` de `src/lib/format.ts`.
- **Estado global:** `useCart` (`src/lib/cart-store.ts`, zustand+persist), `useClienteSession`
  (`src/lib/iva.ts`), favoritos (`src/hooks/useFavoritos.ts`).

**Molde para conectar un `TODO:`:** hook `useQuery({ queryKey, queryFn: () => authedJson<T>("/api/…") })`
→ tipar la respuesta en `api.ts` → `formatARS` para precios → estados de carga/error.

## 3. Backend — mapa de endpoints (FastAPI, `backend/routes/*.py`, prefijo `/api`)

| Superficie | Ejemplos |
|---|---|
| Catálogo público | `GET /api/equipos`, `/api/equipos/{id}`, `/api/categorias`, `/api/disponibilidad-dias` (días bloqueados) |
| Portal cliente | `GET /api/cliente/me`, `/api/cliente/pedidos`, `/api/cliente/favoritos`, `POST /api/cliente/pedidos` |
| Estudio | `GET /api/estudio`, `/api/estudio/disponibilidad`, `POST /api/estudio/reservas` |
| Admin | `/api/alquileres*`, `/api/clientes*`, `/api/admin/*` |
| Auth | `/auth/*` (Google OAuth + cookie de sesión) |

Auth: cookie de sesión firmada (httponly). Guards: `require_cliente` / `require_admin`
(`backend/admin_guard.py`, `backend/routes/cliente_portal.py`).

## 4. Política de backend híbrida (qué hacer cuando falta un dato)

- **Existe el endpoint** → conectar con el molde de §2.
- **Falta endpoint de SOLO LECTURA simple** → crearlo full-stack:
  1. router en `backend/routes/<x>.py` (`@router.get`, guard según superficie),
  2. registrar en `backend/main.py` con `app.include_router(..., prefix="/api")`,
  3. tipo + helper en `src/lib/api.ts`,
  4. consumir con `useQuery`.
- **PARAR y avisar en el PR** si requiere: migración/columna nueva (Alembic), escritura de datos
  **sensibles** (pagos, estados de pedido, permisos), o toca **disponibilidad/overlap** → el **core de
  reservas es sagrado**. No inventar endpoints ni stubs silenciosos.
