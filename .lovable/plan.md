# Optimizar header + hero en mobile

## Diagnóstico
Lo que se ve "raro" no es solo el header — es que toda la página tiene **overflow horizontal en mobile** y por eso el pill "Elegir fechas" y el botón del carrito aparecen cortados a la derecha.

Causas concretas:

1. **Hero `h1` con `text-[14vw]`** (`src/routes/index.tsx:170`). A 402px de ancho, "donde pasan" mide ~620px → fuerza scroll horizontal de toda la página, lo que arrastra al header.
2. **Línea "Catálogo · 142 equipos · Mar del Plata"** con `tracking-[0.3em]` y `whitespace` por defecto: en mobile no wrappea bien y se corta ("MAR DEL PLA…").
3. **TopBar en mobile usa 3 filas** (`flex-col`): logo, pill de fechas, botones (carrito + user). Ocupa demasiado alto y el bloque de carrito queda alineado a la derecha solo, raro visualmente.
4. **`backdrop-blur-xl`** en el header sobre el hero amarillo animado (grain) genera jitter en scroll en iOS.

## Solución (solo frontend / presentación)

### 1. Hero — tipografía responsive sana
- Reemplazar `text-[14vw]` por escala Tailwind con clamp:
  `text-5xl sm:text-7xl md:text-[7rem] lg:text-[8.5rem]` (o `clamp(2.75rem, 12vw, 8.5rem)`).
- Mantener el impacto visual en desktop, pero garantizando que en 360–414px no desborde.
- Agregar `break-words` o `hyphens-auto` por si acaso.

### 2. Línea de meta del hero
- Wrap permitido (`flex-wrap` o quitar nowrap).
- En mobile, reducir tracking a `tracking-[0.2em]` o partir en dos líneas: "Catálogo · 142 equipos" / "Mar del Plata".

### 3. TopBar mobile — 2 filas compactas
**Fila 1**: logo (izq) + carrito icon-only + user icon-only (der).
**Fila 2**: pill "Elegir fechas" full-width.

Ventajas:
- El carrito queda al lado del logo (patrón estándar app móvil), no flotando solo.
- La pill ocupa todo el ancho disponible y nunca se corta.
- Reduce el alto del header de ~140px a ~96px → más contenido visible above the fold.

Cambios concretos en `TopBar.tsx`:
- Estructura: `<div class="flex items-center justify-between gap-2">` (logo + acciones) y debajo `<button class="flex md:hidden w-full">` (pill).
- Mover los botones de carrito/user al row del logo en mobile (hoy están en su propio bloque `sm:ml-auto`).
- Carrito mobile: solo icono + badge numérico (chip pequeño en esquina si `count > 0`).

### 4. Header — performance
- Cambiar `backdrop-blur-xl` → `backdrop-blur-md` o quitar blur en mobile (`md:backdrop-blur-xl`) y dejar `bg-background/95` sólido en mobile. Reduce jank de scroll sobre el hero animado.

### 5. Defensa contra overflow horizontal
- En `<body>` o root: `overflow-x-hidden` (en `index.css` o el root layout) como red de seguridad para que ningún hijo accidentalmente scrollee la página completa.

## Archivos a tocar
```
src/components/rental/TopBar.tsx     (re-layout mobile + blur)
src/routes/index.tsx                  (h1 + meta line del hero)
src/styles.css                        (overflow-x-hidden en body)
```

## Out of scope
- Cambiar copy del hero o branding.
- Tocar el modal `RentalDateModal`.
- Animación de grain.
- Cambios en desktop (queda igual).

## QA
Testear en 360, 390, 414 px de ancho:
- Sin scroll horizontal.
- Pill "Elegir fechas" entera, carrito visible al lado del logo.
- Hero legible sin desbordar.
