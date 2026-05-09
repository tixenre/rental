import { create } from "zustand";
import { snapTo30 } from "@/components/rental/TimeStepSelect";

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
  drawerPlacement: "right",
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
    if (!startDate || !endDate) return 1;
    const startOfDay = (d: Date) => {
      const x = new Date(d);
      x.setHours(0, 0, 0, 0);
      return x;
    };
    const dayDiff = Math.round(
      (startOfDay(endDate).getTime() - startOfDay(startDate).getTime()) /
        (1000 * 60 * 60 * 24),
    );
    const [sh = 0, sm = 0] = (startTime ?? "00:00").split(":").map(Number);
    const [eh = 0, em = 0] = (endTime ?? "00:00").split(":").map(Number);
    const endsLater = eh * 60 + em > sh * 60 + sm;
    return Math.max(1, dayDiff + (endsLater ? 1 : 0));
  },
}));
