# Plan: Estudio como producto estrella

Sumar el estudio de foto y video como producto destacado: CTA en el hero, página dedicada `/estudio` con estructura lista para completar, y reserva por hora con mínimo, más un addon "Todo incluido" de luces y griperías a monto fijo por día.

## 1. Hero — CTA al estudio

En `src/routes/index.tsx`, dentro del hero amarillo ("un lugar donde pasan cosas"), debajo del párrafo descriptivo y junto a las píldoras (calidad, variedad…), agregar un bloque CTA destacado:

- Etiqueta chiquita: `★ Producto estrella`
- Botón grande negro: **"Conocé el Estudio →"** que linkea a `/estudio` (Link de TanStack Router con `to="/estudio"`).
- Sub-línea: "Foto y video · reservá por hora · pack de luces y grips opcional".

Sin tocar el resto del hero. Sin imagen del estudio (placeholder llega después).

## 2. Página `/estudio`

Nuevo route file `src/routes/estudio.tsx` con `head()` propio (title, description, og). Reusa `<TopBar/>` y `<CartDrawer/>` para mantener la navegación.

Estructura (todas las secciones con copy placeholder e imágenes vacías marcadas `[FOTO]` para reemplazar luego):

```text
┌───────────────────────────────────────┐
│ Hero del estudio                      │
│  - Título grande "El Estudio"         │
│  - Bajada (placeholder)               │
│  - [FOTO principal]                   │
│  - CTA "Reservar" → scroll a reserva  │
├───────────────────────────────────────┤
│ Galería (grid de [FOTO] placeholders) │
├───────────────────────────────────────┤
│ Características (grid de íconos)      │
│  m², ciclorama, equipo fijo, etc.     │
├───────────────────────────────────────┤
│ Pack "Todo incluido" (addon)          │
│  - Qué trae · monto fijo / día        │
│  - Toggle on/off al reservar          │
├───────────────────────────────────────┤
│ Reservar (formulario)                 │
│  - Fecha + hora inicio + duración     │
│  - Checkbox "Sumar pack todo incluido"│
│  - Resumen de precio                  │
│  - Botón "Confirmar por WhatsApp"     │
├───────────────────────────────────────┤
│ FAQ (placeholders)                    │
└───────────────────────────────────────┘
```

## 3. Reserva del estudio

- Modalidad: **por hora con mínimo** (constante `MIN_HOURS = 3`, editable después).
- Inputs:
  - Fecha (shadcn Calendar single mode dentro de Popover)
  - Hora de inicio (select 08:00–22:00 cada 30 min)
  - Duración (stepper +/- horas, partiendo del mínimo)
- Cálculo:
  - `subtotal = pricePerHour × hours`
  - Si addon activo: `+ ADDON_FLAT_PRICE` (un solo cargo por día, no por hora).
  - Total visible en vivo.
- Botón "Reservar por WhatsApp" arma un mensaje pre-poblado con fecha, horario, duración y addon, abre `wa.me/...` (mismo número que ya usa el TopBar).
- No se mete al carrito de equipos para evitar mezclar lógicas (los equipos se cobran por jornada y el estudio por hora).

## 4. Addon "Todo incluido"

- Definido como constante en `src/data/studio.ts`:
  ```ts
  export const STUDIO = {
    pricePerHour: 0,         // placeholder
    minHours: 3,
    addon: {
      name: "Pack Todo Incluido",
      description: "Todas las luces y griperías del estudio.",
      pricePerDay: 0,        // placeholder, monto fijo
      includes: ["…"],       // bullets placeholder
    },
  };
  ```
- En la página: card destacada describiendo el addon + checkbox en el formulario de reserva.

## Detalles técnicos

- Nuevo archivo `src/routes/estudio.tsx` con `createFileRoute("/estudio")`. El plugin de TanStack regenera `routeTree.gen.ts` solo.
- Nuevo archivo `src/data/studio.ts` con la config del estudio y el addon (precios en 0 por ahora, comentario `// TODO: precio real`).
- Componente nuevo `src/components/studio/StudioBookingForm.tsx` con el formulario y el cálculo.
- En el hero (`src/routes/index.tsx`) sumar el bloque CTA con `<Link to="/estudio">`.
- Sin cambios al store del carrito, ni a `equipment.ts`, ni a `RentalDateModal`.
- Mobile-first: hero CTA full-width en mobile, inline al lado del párrafo en desktop. Página de estudio en una columna con secciones bien espaciadas.

## Lo que NO entra en este plan

- Fotos reales del estudio (placeholders gris con label).
- Precios reales (quedan en 0, fácil de editar).
- Integración con calendario real de disponibilidad del estudio (por ahora todas las fechas seleccionables).
- Pago online (la reserva sale por WhatsApp).
