# Mobile — Guía de componentes y patrones

## Stack

- **Componentes**: `src/components/mobile/` — importar desde `@/components/mobile`
- **Breakpoint mobile**: `< 768px` (`md` en Tailwind). Usar clases `md:hidden` / `hidden md:block` para dual-view sin JS.
- **Feel**: app nativa — swipe-to-dismiss, safe-area, tap targets ≥ 44px.

---

## Componentes disponibles

### `AdminCard` — listas admin

Reemplaza tablas en mobile. Compuesto por sub-componentes para armar cualquier layout.

```tsx
import {
  AdminCard,
  AdminCardHeader,
  AdminCardMeta,
  AdminCardFooter,
  AdminCardPrice,
  AdminCardActions,
} from "@/components/mobile";

<AdminCard onClick={() => navigate({ to: "/admin/pedidos/$id", params: { id } })}>
  <AdminCardHeader
    label={`#${pedido.numero}`}
    title={pedido.cliente_nombre}
    subtitle={pedido.cliente_email}
    badge={<EstadoBadge estado={pedido.estado} />}
  />
  <AdminCardMeta>12 jun → 15 jun · 3 jornadas</AdminCardMeta>
  <AdminCardFooter>
    <AdminCardPrice total={pedido.total} saldo={pedido.saldo_pendiente} />
    <AdminCardActions>
      <Button size="icon" variant="ghost"><ExternalLink /></Button>
    </AdminCardActions>
  </AdminCardFooter>
</AdminCard>
```

---

### `BottomSheet` — sheets de contenido

Para filtros, pickers, formularios secundarios. Usa `vaul` (swipe-to-dismiss nativo).

```tsx
import { BottomSheet } from "@/components/mobile";

<BottomSheet
  open={open}
  onOpenChange={setOpen}
  title="Filtros"
  footer={<Button onClick={() => setOpen(false)}>Ver {n} resultados</Button>}
>
  {/* contenido scrollable */}
</BottomSheet>
```

Props: `open`, `onOpenChange`, `title?`, `children`, `footer?`, `maxH?` (default `"max-h-[85vh]"`), `showClose?`.

---

### `PageHeader` — header de página mobile

Header sticky con soporte para back button, título y acción derecha.

```tsx
import { PageHeader } from "@/components/mobile";

<PageHeader
  title="Pedidos"
  subtitle="12 activos"
  onBack={() => navigate({ to: "/admin" })}
  action={<Button size="sm">Nuevo</Button>}
/>
```

Maneja `env(safe-area-inset-top)` automáticamente.

---

### `FAB` — floating action button

Botón primario flotante. Posición fija bottom-right, sobre safe-area.

```tsx
import { FAB } from "@/components/mobile";

// Simple (ícono solo)
<FAB onClick={() => setOpen(true)} />

// Extendido (con label)
<FAB onClick={() => setOpen(true)} label="Nuevo pedido" />

// Con ícono custom
<FAB onClick={handleNew} icon={<Plus className="h-6 w-6" />} />
```

Recordar dejar `pb-20` o similar en el contenido para que el FAB no tape el último ítem.

---

### `ActionMenu` — menú de acciones iOS-style

Lista de acciones en un sheet. Swipe-to-dismiss incluido.

```tsx
import { ActionMenu } from "@/components/mobile";

<ActionMenu
  open={open}
  onOpenChange={setOpen}
  title="Pedido #42"
  actions={[
    { label: "Enviar WhatsApp", icon: <MessageCircle />, onClick: handleWA },
    { label: "Ver detalle", icon: <ExternalLink />, onClick: handleOpen },
    { label: "Eliminar", icon: <Trash2 />, variant: "destructive", onClick: handleDelete },
  ]}
/>
```

---

## CSS utilities

| Clase | Uso |
|-------|-----|
| `safe-t` | `padding-top: env(safe-area-inset-top)` — headers bajo notch |
| `safe-b` | `padding-bottom: env(safe-area-inset-bottom)` — footers sobre home bar |
| `safe-x` | padding horizontal seguro para iPhone landscape |

Ya incluido globalmente: todos los `input/textarea/select` tienen `font-size: max(16px, 1em)` en mobile para evitar zoom de iOS.

---

## Patrón dual-view (tabla/cards)

La mayoría de páginas admin necesitan tabla en desktop y cards en mobile:

```tsx
{/* Mobile */}
<div className="md:hidden space-y-3">
  {items.map((item) => (
    <AdminCard key={item.id}>...</AdminCard>
  ))}
</div>

{/* Desktop */}
<div className="hidden md:block overflow-x-auto">
  <Table>...</Table>
</div>
```

No usar `useIsMobile()` para esto — Tailwind CSS puro evita hydration flash.

---

## Checklist al hacer una pantalla nueva mobile

- [ ] Header usa `PageHeader` o tiene `safe-t` / `sticky top-0 backdrop-blur-xl`
- [ ] Todos los botones táctiles son `h-10 w-10` mínimo (44px)
- [ ] Footer / FAB usa `safe-b` o `env(safe-area-inset-bottom)` manual
- [ ] Listas usan `AdminCard` (admin) o diseño equivalente
- [ ] Inputs/selects heredan el `font-size: max(16px, 1em)` global — no agregar zoom manual
- [ ] Scroll containers tienen `overscroll-contain`
- [ ] Sheets/modals usan `BottomSheet` o `ActionMenu` (no `Dialog` en mobile)
- [ ] `tsc --noEmit` sin errores nuevos
