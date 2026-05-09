## Problema

En la vista de lista, al expandir un equipo la página entera se desplaza para centrar la fila clickeada. Esto pasa porque el `useEffect` de `src/routes/index.tsx` (líneas 68–74) llama a `scrollIntoView({ block: "center" })` cada vez que cambia `?eq=` — incluyendo cuando el usuario hace click. Como resultado, el ítem clickeado "salta" a otra posición y el usuario pierde la referencia visual.

## Cambio

Limitar el auto-scroll a un solo caso: **deep-link inicial** (entrar a la página con `?eq=...` ya en la URL, o compartir un link). Cuando el usuario expande/colapsa una fila por click, no se mueve nada — la fila permanece donde está y el contenido se despliega hacia abajo empujando solo a los ítems siguientes.

### Implementación

En `src/routes/index.tsx`:

- Agregar un `useRef<boolean>` (`didInitialScrollRef`) que arranca en `false`.
- Reescribir el efecto de scroll para que:
  - Si `didInitialScrollRef.current === false` y hay `eq` al montar → hacer `scrollIntoView` y marcar `didInitialScrollRef.current = true`.
  - Si ya se hizo el scroll inicial (o `eq` cambió por interacción del usuario) → no hacer nada.
- Quitar `mode` de las dependencias del efecto (ya no es necesario).

El `motion.div` con `height: 0 → auto` de `EquipmentRow.tsx` ya anima la expansión hacia abajo correctamente; no hace falta tocarlo.

### Resultado

- Click en una fila → se despliega inline sin mover la página.
- Abrir `/?eq=cm3` directo (link compartido) → sigue centrando el ítem como hoy.
- Vista grilla (modal) → sin cambios.
