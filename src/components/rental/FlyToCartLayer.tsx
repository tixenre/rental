import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import { useFlyToCart } from "@/lib/fly-to-cart-store";

/**
 * Capa global que anima un "+1" desde donde se tocó "Agregar"
 * hasta el ícono del carrito (data-cart-icon).
 *
 * Mount una sola vez cerca del root del catálogo.
 */
export function FlyToCartLayer() {
  const origin = useFlyToCart((s) => s.origin);
  const flyKey = useFlyToCart((s) => s.flyKey);
  const popCart = useFlyToCart((s) => s.popCart);
  const clearFly = useFlyToCart((s) => s.clearFly);

  const [target, setTarget] = useState<{ x: number; y: number } | null>(null);

  // Capturar destino solo en el momento de disparar (no cachear — el ícono
  // puede moverse si cambia el viewport, etc.).
  useEffect(() => {
    if (!origin) return;
    const el = document.querySelector<HTMLElement>("[data-cart-icon]");
    if (!el) {
      // Sin destino visible — limpiar y no animar.
      clearFly();
      return;
    }
    const rect = el.getBoundingClientRect();
    setTarget({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
  }, [flyKey, origin, clearFly]);

  if (typeof document === "undefined") return null;

  return createPortal(
    <AnimatePresence
      onExitComplete={() => {
        // Pop del ícono cuando la animación termina.
        popCart();
        clearFly();
      }}
    >
      {origin && target && (
        <motion.div
          key={flyKey}
          initial={{
            x: origin.x,
            y: origin.y,
            scale: 1,
            opacity: 1,
          }}
          animate={{
            x: target.x,
            y: target.y,
            scale: 0.4,
            opacity: 0.8,
          }}
          exit={{ opacity: 0 }}
          transition={{
            duration: 0.55,
            ease: [0.22, 1, 0.36, 1],
          }}
          onAnimationComplete={() => clearFly()}
          className="pointer-events-none fixed left-0 top-0 z-[60] grid h-9 w-9 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-amber font-mono text-xs font-bold text-ink shadow-lg ring-2 ring-amber/40"
          aria-hidden
        >
          +1
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
