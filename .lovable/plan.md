## Objetivo

Construir un back-office nuevo dentro de Lovable bajo `/admin/*`, con la misma estética del frontend público (paleta amber/ink, `font-display`, mono para overlines, hairlines, shadcn/ui). Toda la lógica de negocio sigue viviendo en el FastAPI de `backend/` — el back-office solo consume sus endpoints. El back-office HTML viejo en Railway queda intacto como fallback durante la transición.

## Arquitectura

```text
┌─ Repo (este, deploy a Railway) ────────────────────┐
│                                                    │
│  src/routes/_admin/*       ◄── Pantallas React     │
│  src/lib/admin/*.ts        ◄── Hooks + fetchers    │
│         │                                          │
│         │ authedFetch (JWT Supabase)               │
│         ▼                                          │
│  backend/*.py              ◄── FastAPI             │
│    + supabase_auth.py      ◄── Valida JWT          │
│    + require_admin         ◄── Chequea email       │
│                                                    │
└────────────────────────────────────────────────────┘
```

Frontend y backend viven en el mismo repo. Cada push a Railway redeploya ambos.

## Auth

- Login único: `/login` con Google (Lovable Cloud), ya funciona.
- En FastAPI: nuevo dependency `require_admin` que (1) valida JWT con `supabase_auth.py`, (2) chequea email contra `ADMIN_EMAILS` env var, (3) acepta también la cookie session vieja para retrocompatibilidad con el back-office HTML viejo. Devuelve 403 si no.
- En frontend: layout `_admin` con `beforeLoad` que redirige a `/login?redirect=...` si no hay sesión, y a `/admin/no-autorizado` si la sesión no es admin.
- Se elimina el `BYPASS_AUTH` actual.

## Pantallas (paridad con el back-office viejo)

```text
/admin                      Dashboard: stats, próximos pedidos, alertas stock
/admin/equipos              Lista + filtros + buscador
/admin/equipos/$id          Detalle: ficha, kit, etiquetas, historial, precio
/admin/equipos/nuevo        Crear equipo
/admin/pedidos              Lista alquileres con filtros (estado/fecha/cliente)
/admin/pedidos/$id          Detalle: items, pagos, estado, descargar PDFs
/admin/pedidos/nuevo        Crear pedido manual (wizard 3 pasos)
/admin/clientes             Lista + buscador
/admin/clientes/$id         Detalle + historial pedidos
/admin/calendario           Vista mensual disponibilidad
/admin/estadisticas         Reportes (ingresos, top equipos)
/admin/settings             Imports CSV + herramientas mantenimiento
```

Layout compartido: sidebar shadcn colapsable (`collapsible="icon"`) con las 7 secciones, header con email del admin + logout, breadcrumbs.

## Implementación por fases

Cada fase queda usable y mergeable antes de empezar la siguiente.

### Fase 1 — Fundación (auth + layout + dashboard)

Backend:
- `backend/supabase_auth.py`: agregar `require_admin` dependency (JWT + email allowlist).
- Aplicar `Depends(require_admin)` en routers admin (acepta también cookie session vieja).
- Env var nueva: `ADMIN_EMAILS` (CSV de emails autorizados).

Frontend:
- `src/routes/_admin.tsx` — layout con `SidebarProvider` + guard de auth/rol.
- `src/components/admin/AdminSidebar.tsx` — sidebar con las 7 secciones.
- `src/lib/admin/api.ts` — wrappers tipados de `authedFetch` para cada endpoint admin.
- `src/lib/admin/queries.ts` — `queryOptions` reutilizables (react-query).
- `src/routes/_admin/index.tsx` — Dashboard (consume `/api/dashboard`).
- `src/routes/admin.tsx` actual: pasa a redirigir a `/admin` (el nuevo layout).

### Fase 2 — Equipos

- `_admin/equipos/index.tsx`: tabla con buscador + filtros (categoría, etiqueta, estado), botón "Nuevo".
- `_admin/equipos/$id.tsx`: tabs (Datos, Ficha técnica, Kit, Etiquetas, Historial, Precio).
- `_admin/equipos/nuevo.tsx`: form con react-hook-form + zod.
- Componentes: `EquipoForm`, `KitEditor`, `EtiquetasEditor`.

### Fase 3 — Pedidos (la más grande)

- `_admin/pedidos/index.tsx`: tabla con filtros (estado, rango fechas, cliente).
- `_admin/pedidos/$id.tsx`: tabs (Items, Pagos, Datos cliente, Documentos).
  - Editor de items con búsqueda de equipos y disponibilidad live.
  - Lista de pagos + agregar/borrar.
  - Botones para descargar PDF/albarán/contrato (`window.open` con token).
- `_admin/pedidos/nuevo.tsx`: wizard 3 pasos (cliente → fechas → items).

### Fase 4 — Clientes + Calendario

- `_admin/clientes/index.tsx` y `$id.tsx`: CRUD básico + historial pedidos.
- `_admin/calendario.tsx`: vista mensual con shadcn Calendar custom, color por densidad. Click en día → modal con pedidos del día.

### Fase 5 — Estadísticas + Settings

- `_admin/estadisticas.tsx`: cards con métricas + gráficos con `recharts` (ya instalado).
- `_admin/settings.tsx`: file upload → POST a `/api/settings/import-*`.

## Detalles técnicos

- **Estado servidor**: `@tanstack/react-query` (ya en uso). Cada endpoint tiene su `queryOptions` con invalidación al mutar.
- **Forms**: `react-hook-form` + `zod` (ya instalados).
- **PDFs**: el FastAPI ya genera PDFs con `pdf.py`. Si el endpoint actual solo acepta cookie session, agrego soporte para token en query string para que el frontend pueda hacer `window.open`.
- **Estética**: mismos tokens del sitio público (`bg-background`, `text-ink`, `bg-amber`, `font-display`, `font-mono uppercase tracking-[0.25em]`, `border hairline`, `bg-surface`). Cero colores nuevos.
- **Mobile**: el back-office optimiza para desktop (uso real), pero las tablas usan scroll horizontal y la sidebar colapsa a offcanvas en mobile.

## Qué NO se hace

- No se reescribe el FastAPI ni se agregan features de negocio nuevas.
- No se toca el frontend público (catálogo, cart, mis-pedidos).
- No se borra el back-office HTML viejo hasta que la versión React esté completa y validada.
- No se migra DB ni se cambia el modelo de datos.

## Validación al final de cada fase

1. Login con Google entra al `/admin` nuevo sin pedir credenciales extra.
2. Sidebar navega entre secciones, ruta activa marcada.
3. Cada CRUD: listar, crear, editar, borrar funcionan contra el FastAPI.
4. Estética visualmente coherente con el frontend público.
5. Back-office HTML viejo sigue funcionando en `https://ramblarental.up.railway.app/admin`.

## Empezamos por

Fase 1 (auth + sidebar + dashboard). Una vez aprobado, paso a build mode y dejo eso funcionando antes de seguir con Fase 2.
