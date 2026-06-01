import { AnimatePresence, motion } from "framer-motion";

/**
 * FlyToCartLayer — animación "fly-to-cart" al agregar un ítem al carrito.
 *
 * Se monta UNA VEZ en el root de la app (en `src/routes/__root.tsx`),
 * por encima de todo el contenido pero sin z-index explícito — usa
 * pointer-events: none para no bloquear interacciones.
 *
 * Flujo de uso:
 *   1. El usuario hace click en StepperPill (increment) en una EquipmentCard.
 *   2. El componente padre obtiene `getBoundingClientRect()` de la foto de la card
 *      y del botón del carrito (CartMiniBar o TopBar cart button).
 *   3. Agrega un FlyItem a la lista pasada a FlyToCartLayer.
 *   4. La animación vuela en 550ms, luego llama onComplete(id) para remover el item.
 *   5. Al completar, la badge del carrito ejecuta su pop (implementado externamente
 *      via framer-motion layout animations en el componente de badge).
 *
 * Curva: cubic(0.22, 1, 0.36, 1) — ease-out expo, misma que el drawer.
 * Duración: 550ms (--duration-xslow).
 *
 * El thumbnail vuela desde la card (rect from) hasta el carrito (rect to),
 * reduciendo su tamaño de from.width × from.height a 32×32, con opacity
 * que cae a 0 al final.
 *
 * Source: `docs/DESIGN_SYSTEM.md` → Micro-interactions → fly-to-cart
 *         `preview/components-micro-interactions.html`
 */

export interface FlyItem {
  /** ID único de la animación (ej: `${equipmentId}-${Date.now()}`). */
  id: string;
  /** DOMRect de la FOTO de la EquipmentCard origen. */
  from: DOMRect;
  /** DOMRect del botón del carrito (CartMiniBar o cart icon del TopBar). */
  to: DOMRect;
  /** URL de la foto del equipo para el thumbnail volador. */
  photoUrl?: string;
}

export interface FlyToCartLayerProps {
  items: FlyItem[];
  onComplete: (id: string) => void;
}

export function FlyToCartLayer({ items, onComplete }: FlyToCartLayerProps) {
  return (
    <div
      aria-hidden
      style={{
        position: "fixed",
        inset: 0,
        pointerEvents: "none",
        zIndex: 9999,
        overflow: "hidden",
      }}
    >
      <AnimatePresence>
        {items.map((item) => {
          // Centro del destino
          const toX = item.to.left + item.to.width / 2;
          const toY = item.to.top + item.to.height / 2;
          // Centro del origen
          const fromX = item.from.left + item.from.width / 2;
          const fromY = item.from.top + item.from.height / 2;
          // Delta (framer-motion anima desde 0 relativo a la posición inicial)
          const dx = toX - fromX;
          const dy = toY - fromY;

          return (
            <motion.div
              key={item.id}
              initial={{
                position: "fixed" as const,
                left: item.from.left,
                top:  item.from.top,
                width:  item.from.width,
                height: item.from.height,
                borderRadius: 8,
                opacity: 1,
                x: 0,
                y: 0,
                scale: 1,
              }}
              animate={{
                x: dx,
                y: dy,
                width: 32,
                height: 32,
                borderRadius: 9999,
                opacity: 0,
                scale: 0.5,
              }}
              exit={{ opacity: 0 }}
              transition={{
                duration: 0.55,                      // --duration-xslow
                ease: [0.22, 1, 0.36, 1],            // ease-out expo
              }}
              onAnimationComplete={() => onComplete(item.id)}
              style={{
                overflow: "hidden",
                backgroundImage: item.photoUrl
                  ? `url(${item.photoUrl})`
                  : undefined,
                backgroundSize: "cover",
                backgroundPosition: "center",
                backgroundColor: item.photoUrl
                  ? undefined
                  : "var(--amber)",
              }}
            />
          );
        })}
      </AnimatePresence>
    </div>
  );
}
