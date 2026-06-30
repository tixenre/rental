import { useEffect, useState } from "react";

/**
 * Hook que detecta si el usuario pidió reduced motion.
 * Retorna `true` si `prefers-reduced-motion: reduce` está activo.
 * SSR-safe (false en hidratación, true luego si aplica).
 */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    // Chequear media query al montar
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);

    // Escuchar cambios (usuario alterna en Accessibility settings)
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  return reduced;
}
