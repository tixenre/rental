import { useEffect } from "react";
import { useCart } from "@/lib/cart-store";

const DEBOUNCE_MS = 2000;

export function useCartHeartbeat() {
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;

    const sendHeartbeat = () => {
      const { items, startDate, endDate, startTime, endTime, sessionId } = useCart.getState();

      if (Object.keys(items).length === 0) return;

      const body = {
        session_id: sessionId,
        items: Object.entries(items).map(([equipo_id, cantidad]) => ({
          equipo_id: Number(equipo_id),
          cantidad,
        })),
        fecha_desde: startDate ? startDate.toISOString().split("T")[0] : null,
        fecha_hasta: endDate ? endDate.toISOString().split("T")[0] : null,
        hora_desde: startTime ?? null,
        hora_hasta: endTime ?? null,
      };

      fetch("/api/cart/heartbeat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body),
      }).catch(() => {
        // Silencioso — no bloquea la UX si la red falla
      });
    };

    const unsubscribe = useCart.subscribe((state, prev) => {
      if (
        state.items !== prev.items ||
        state.startDate !== prev.startDate ||
        state.endDate !== prev.endDate ||
        state.startTime !== prev.startTime ||
        state.endTime !== prev.endTime
      ) {
        clearTimeout(timer);
        timer = setTimeout(sendHeartbeat, DEBOUNCE_MS);
      }
    });

    return () => {
      clearTimeout(timer);
      unsubscribe();
    };
  }, []);
}
