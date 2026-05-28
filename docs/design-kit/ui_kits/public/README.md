# Public Catalog UI Kit

Click-through prototype of the **public catalog surface** (`/` route in
the production app — `src/routes/index.tsx`). Mirrors the live structure:
TopBar with date pill + cart, amber hero with the chunky tagline, sticky
sub-toolbar (view toggle + search + counter), category mosaic, brand
carousel, then equipment carousels per category, then footer.

## What you can interact with

- **Click a category tile** → filters everything to that category.
- **Click a brand chip** → filters equipment by that brand.
- **Type in the search** → narrows results across name/brand/category.
- **`+` on a card** → adds to the cart, switches the card into "selected"
  state, swaps the button for a stepper.
- **Cart button (top right)** → opens the right-side drawer with totals
  computed against the demo date range (3 jornadas).
- **Filter chips** → click `×` or "Ver todo" to clear.

Everything is **cosmetic**. There is no real backend, no real photos —
products show initial-letter placeholders on a tinted gradient. That's a
deliberate UX choice borrowed from the codebase (`EmptyImage.tsx`):
when there's no photo yet, show a clear-but-honest placeholder rather
than reaching for stock art.

## Files

| File | What |
| --- | --- |
| `index.html` | Composes `<App />` — view-mode + filter state, mounts the cart drawer |
| `components.jsx` | All composable components: `<TopBar>`, `<Hero>`, `<SubToolbar>`, `<CategoryMosaic>`, `<BrandRow>`, `<EquipmentCard>`, `<CategoryCarousel>`, `<Footer>`, `<CartDrawer>` |
| `icons.jsx` | Inline SVG icon library — lucide-react equivalents + the hand-drawn category illustrations (`CATEGORY_ILLS`) |
| `data.js` | Fake catalog: 24 equipment items across 7 categories, 12 brands |
| `styles.css` | Layout + component CSS. Imports `colors_and_type.css` from project root. |

## Notes against the source

- The production `TopBar.tsx` has a `variant="cliente"` for the
  post-login portal. Only the catalog `variant="default"` is reproduced
  here — variants for the cliente portal would be similar with the date
  pill replaced by a name pill + logout.
- The codebase ships a **list mode** alongside the grid mode (rows that
  scroll with infinite loader). It's a real surface in the app — this
  kit only renders the grid carousel mode for brevity. Toggle the view
  switch and the count updates, but the layout stays the same.
- Real product photos go on a pure white tile with `object-contain p-3`;
  here we substitute initial-letter placeholders on the amber gradient.
- The `RentalDateModal` is referenced but not implemented — clicking the
  date pill shows an alert instead of opening the modal.
