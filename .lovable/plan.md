## Objetivo

Eliminar el "lío visual" del sticky en móviles consolidando todo en **una sola barra coherente** y moviendo el modo grid a un menú secundario.

## Diagnóstico

Hoy en móvil hay **3 bloques apilados** dentro del sticky + un 4° debajo:

```text
┌─ TopBar (logo/cart/user) ─────────────────────────┐  56px
├─ [📅 fechas]      [🔍]                            │  ~56px  ← MobileStickyBar
├─ [⊞ Explorar | ☰ Lista]            142 RESULTADOS │  ~44px  ← toggle row
├─ [Todas las marcas ▾] [Limpiar]                   │  ~96px  ← ListFilters (otro sticky!)
│  [Accesorios] [Baterías] [Brazo Mágico] …         │
└────────────────────────────────────────────────────┘
```

Problemas:
- Dos barras sticky distintas con `top` diferentes → se ve un "salto" entre ellas.
- Toggle Grid/Lista ocupa espacio aunque en móvil casi nadie usa grid.
- Contador "142 resultados" compite con el resto.
- Marca + chips de categorías son ~100px verticales antes de ver un equipo.

## Propuesta

### 1. Barra única sticky (móvil)

Una sola fila, una sola altura, un solo `sticky`:

```text
┌─ TopBar ────────────────────────────────────────────┐  56px
└─ [📅 04 jun → 06 jun · 2j]  [🔍]  [⚙ 3]            │  ~52px
```

- **Pill fechas** (igual que ahora) — flex-1, truncate.
- **Botón 🔍 búsqueda** — abre el input expandido in-place (igual que hoy).
- **Botón ⚙ filtros** — abre un **bottom sheet** con marcas + categorías + "Limpiar". Badge con count de filtros activos.

Sin segunda fila, sin contador inline, sin chips horizontales visibles por defecto.

### 2. Modo lista forzado en móvil

- Móvil: siempre `mode = "list"`. El toggle desaparece de la barra.
- El acceso a "Vista grid / Explorar" se mueve a un item dentro del sheet de filtros (al final, como opción de visualización), o directamente se omite en móvil. Recomendación: omitirlo del todo en móvil — la grid en pantalla angosta no aporta vs la lista.
- Desktop (`sm+`): se mantiene tal cual está hoy (search input visible, toggle Grid/Lista, contador).

### 3. Contador de resultados

- Móvil: aparece **dentro** del sheet de filtros (header: "142 equipos · 3 filtros activos") y como sutil texto debajo del primer item de la lista, no en la barra.
- Desktop: sin cambios.

### 4. Eliminar el segundo sticky de ListFilters en móvil

`ListFilters` deja de ser sticky en móvil — su contenido vive ahora dentro del sheet. En desktop sigue como está (chips visibles arriba de la lista).

## Cambios técnicos

- `src/components/rental/MobileStickyBar.tsx`: agregar tercer botón (filtros) con badge. Estado de sheet.
- **Nuevo** `src/components/rental/MobileFiltersSheet.tsx`: bottom sheet (usar `Sheet` de shadcn, `side="bottom"`) con marca select, chips de categorías wrapped, contador, botón "Limpiar todo" y "Aplicar/Cerrar".
- `src/components/rental/ListFilters.tsx`: en `md:` y arriba mantener; en móvil ocultarlo (`hidden md:block`).
- `src/routes/index.tsx`:
  - Forzar `mode = "list"` en móvil y no permitir cambiarlo desde la UI móvil.
  - Mostrar el toggle Grid/Lista solo en `sm:flex`.
  - Mover contador "N resultados" al desktop only (`hidden sm:block`).
  - Pasar `selectedCats`, `brand`, `setBrand`, `toggleCat`, `onClear`, `apiBrands`, `apiCategories` al `MobileStickyBar` para alimentar el sheet.

## Fuera de alcance

- No tocar desktop salvo el `hidden sm:` ya mencionado.
- No cambiar la pill cuando hay/no hay fechas (ya quedó bien).
- No cambiar TopBar.
- No tocar la lógica de filtrado.

## Resultado visual esperado (móvil)

```text
┌─ logo · carrito · user ────────────────────────────┐
├─ 📅 04 jun 11:00 → 06 jun 09:00 · 2j   🔍    ⚙ ③  │  ← único sticky
├──────────────────────────────────────────────────────
│  ▸ Adaptador EF-RF con ND Vari…  $13.500 /día  +  │
│  ▸ Adaptador EF-RF Canon…        $10.500 /día  +  │
│  ▸ …                                                │
```

Todo lo demás (marcas, categorías, contador, vista grid) vive a un tap de distancia en el sheet.
