import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/estudio")({
  head: () => ({
    meta: [
      { title: "El Estudio — Rambla Rental" },
      {
        name: "description",
        content:
          "Estudio de foto y video en Mar del Plata. Reservá por hora con pack de luces y griperías opcional.",
      },
      { property: "og:type", content: "website" },
      { property: "og:url", content: "https://ramblarental.com/estudio" },
      { property: "og:title", content: "El Estudio — Rambla Rental" },
      {
        property: "og:description",
        content:
          "Estudio de foto y video en Mar del Plata. Reservá por hora con pack de luces y griperías opcional.",
      },
      {
        property: "og:image",
        content: "https://ramblarental.com/estudio/Rambla_Estudio_S7V9519-HDR.jpg",
      },
      { property: "og:locale", content: "es_AR" },
      { name: "twitter:card", content: "summary_large_image" },
      { name: "twitter:title", content: "El Estudio — Rambla Rental" },
      { name: "twitter:description", content: "Estudio de foto y video · Mar del Plata" },
      {
        name: "twitter:image",
        content: "https://ramblarental.com/estudio/Rambla_Estudio_S7V9519-HDR.jpg",
      },
    ],
    links: [{ rel: "canonical", href: "https://ramblarental.com/estudio" }],
  }),
});
