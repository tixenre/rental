import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { toast } from "sonner";

type FavoritesState = {
  items: string[];
  toggle: (id: string) => void;
  setItems: (ids: string[]) => void;
  clear: () => void;
};

export const useFavoritesStore = create<FavoritesState>()(
  persist(
    (set, get) => ({
      items: [],

      toggle: (id) => {
        const exists = get().items.includes(id);
        set({
          items: exists ? get().items.filter((x) => x !== id) : [...get().items, id],
        });
        toast(exists ? "Quitado de favoritos" : "Guardado en favoritos", {
          duration: 1500,
        });
      },

      setItems: (ids) => set({ items: ids }),

      clear: () => set({ items: [] }),
    }),
    {
      name: "rental-favorites",
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
