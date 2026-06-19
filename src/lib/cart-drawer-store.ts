import { create } from "zustand";

type CartDrawerState = {
  /** Si el drawer está abierto. */
  isOpen: boolean;
  /** Abre el drawer. */
  open: () => void;
  /** Cierra el drawer. */
  close: () => void;
  /** Alterna el estado del drawer. */
  toggle: () => void;
};

export const useCartDrawerStore = create<CartDrawerState>((set) => ({
  isOpen: false,

  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),
  toggle: () => set((s) => ({ isOpen: !s.isOpen })),
}));
