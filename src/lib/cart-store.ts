import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { snapTo30 } from "@/components/rental/TimeStepSelect";
import { computeJornadas } from "@/lib/rental-dates";

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

export const useCart = create<CartState>()(
  persist(
    (set, get) => ({
      items: {},
      startDate: undefined,
      endDate: undefined,
      startTime: "09:00",
      endTime: "09:00",
      drawerOpen: false,
      drawerPlacement: "right" as DrawerPlacement,
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
      setStartTime: (t) => set({ startTime: snapTo30(t) }),
      setEndTime: (t) => set({ endTime: snapTo30(t) }),
      setDrawerOpen: (open, placement) =>
        set((s) => ({
          drawerOpen: open,
          drawerPlacement: placement ?? s.drawerPlacement,
        })),
      totalItems: () =>
        Object.values(get().items).reduce((a, b) => a + b, 0),
      days: () => {
        const { startDate, endDate, startTime, endTime } = get();
        return computeJornadas(startDate, endDate, startTime, endTime);
      },
    }),
    {
      name: "rental-cart",
      // Recover Date objects from ISO strings after localStorage rehydration
      storage: createJSONStorage(() => localStorage, {
        reviver: (key, value) => {
          if ((key === "startDate" || key === "endDate") && typeof value === "string") {
            const d = new Date(value);
            return isNaN(d.getTime()) ? undefined : d;
          }
          return value;
        },
      }),
      // Only persist cart data, not transient UI state (drawerOpen, drawerPlacement)
      partialize: (state) => ({
        items: state.items,
        startDate: state.startDate,
        endDate: state.endDate,
        startTime: state.startTime,
        endTime: state.endTime,
      }),
    }
  )
);
