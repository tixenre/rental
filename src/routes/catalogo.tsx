import { createFileRoute } from "@tanstack/react-router";
import { CatalogoMovil } from "@/components/rental/mobile/CatalogoMovil";

export const Route = createFileRoute("/catalogo")({
  head: () => ({
    meta: [
      { title: "Catálogo — Rambla Rental" },
      {
        name: "description",
        content: "Explorá y alquilá equipos audiovisuales en Mar del Plata.",
      },
    ],
  }),
  component: CatalogoMovil,
});
