# Admin Back-Office UI Kit

Click-through prototype of the **admin back-office** (`/admin/*` in the
production app). Mirrors the live equipment list — `src/routes/admin/equipos.index.lazy.tsx`
in the codebase — which is the most-used admin surface.

## What you can interact with

- **Sidebar** — `Inventario` expands/collapses. Click any item to mark it
  active (no real navigation since this is a single-page kit).
- **Search** — narrows the table by name, brand, category, or tag.
- **Category / Marca / Estado dropdowns** — proper filter chips. The
  dropdown closes on selection. Each filter combines.
- **Tabs** — `Todos / Nuevos / Destacados / Ficha incompleta`. Tabs are
  in addition to the dropdowns.
- **Row checkboxes** — pick one or many. The header checkbox checks /
  unchecks all visible rows.
- **Bulk action bar** — appears at the bottom when ≥1 row is selected.
  `Mostrar`, `Ocultar`, `Eliminar (soft)` all alert in this kit.
- **Row hover** — reveals the per-row edit / maintenance / visibility /
  more actions.

## Files

| File | What |
| --- | --- |
| `index.html` | Composes `<App />` — filter state, mounts the bulk bar |
| `components.jsx` | `<Sidebar>`, `<KPIStrip>`, `<Toolbar>`, `<EquiposTable>`, `<BulkBar>` |
| `icons.jsx` | Lucide-style icons specific to the admin chrome |
| `data.js` | Fake inventory — 16 equipos across 5 cats, with state + tags |
| `styles.css` | Layout + table CSS. Imports `colors_and_type.css`. |

## Notes against the source

- The real admin uses **shadcn/Radix UI Sidebar primitive** + a TanStack
  Router file tree. Here we hand-roll the chrome — it's purely cosmetic.
- The codebase's filter implementation is more sophisticated (URL-shared
  query state, fuzzy search across `specs_json`, `keywords_json`). Here
  we do a simple substring match.
- Real rows have inline product photos. We substitute the same initials
  thumbnail as the public kit.
- The `% día` column ("ROI por jornada") uses the same color rules as
  prod: green ≥5%, naranja 3-5%, destructive <3%.
- The auto-form (`EquipoFormDialogV2` — 72KB in the source) is not
  represented here; it's the biggest single component in the codebase
  and would need its own kit.
