import { create } from "zustand";

type Origin = { x: number; y: number };

type FlyToCartState = {
  /** Coordenadas de partida del último "+1". null = sin animación activa. */
  origin: Origin | null;
  /** Key incremental — fuerza re-render aunque el origen sea el mismo. */
  flyKey: number;
  /** Key incremental para el "pop" del ícono al recibir item. */
  popKey: number;

  triggerFly: (origin: Origin) => void;
  popCart: () => void;
  clearFly: () => void;
};

export const useFlyToCart = create<FlyToCartState>((set) => ({
  origin: null,
  flyKey: 0,
  popKey: 0,

  triggerFly: (origin) =>
    set((s) => ({ origin, flyKey: s.flyKey + 1 })),

  popCart: () => set((s) => ({ popKey: s.popKey + 1 })),

  clearFly: () => set({ origin: null }),
}));
