import { create } from "zustand";

type DrawerPlacement = "right" | "bottom";

type CartState = {
  items: Record<string, number>;
  startDate: Date | undefined;
  endDate: Date | undefined;
  startTime: string;
  endTime: string;
  drawerOpen: boolean;
  drawerPlacement: DrawerPlacement;
  add: (id: string) => void;
  remove: (id: string) => void;
  setQty: (id: string, qty: number) => void;
  clear: () => void;
  setDates: (start?: Date, end?: Date) => void;
  setStartTime: (t: string) => void;
  setEndTime: (t: string) => void;
  setDrawerOpen: (open: boolean, placement?: DrawerPlacement) => void;
  totalItems: () => number;
  days: () => number;
};

export const useCart = create<CartState>((set, get) => ({
  items: {},
  startDate: undefined,
  endDate: undefined,
  startTime: "09:00",
  endTime: "09:00",
  drawerOpen: false,
  add: (id) =>
    set((s) => ({ items: { ...s.items, [id]: (s.items[id] ?? 0) + 1 } })),
  remove: (id) =>
    set((s) => {
      const next = { ...s.items };
      const n = (next[id] ?? 0) - 1;
      if (n <= 0) delete next[id];
      else next[id] = n;
      return { items: next };
    }),
  setQty: (id, qty) =>
    set((s) => {
      const next = { ...s.items };
      if (qty <= 0) delete next[id];
      else next[id] = qty;
      return { items: next };
    }),
  clear: () => set({ items: {} }),
  setDates: (start, end) => set({ startDate: start, endDate: end }),
  setStartTime: (t) => set({ startTime: t }),
  setEndTime: (t) => set({ endTime: t }),
  setDrawerOpen: (open) => set({ drawerOpen: open }),
  totalItems: () =>
    Object.values(get().items).reduce((a, b) => a + b, 0),
  days: () => {
    const { startDate, endDate } = get();
    if (!startDate || !endDate) return 1;
    const ms = endDate.getTime() - startDate.getTime();
    return Math.max(1, Math.ceil(ms / (1000 * 60 * 60 * 24)) + 1);
  },
}));
