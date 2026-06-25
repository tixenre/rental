import { createFileRoute } from "@tanstack/react-router";

import { SITE_URL } from "@/lib/site";

// Fallback para clientes JS — los crawlers reciben el OG real de R2 vía F5 (backend).
const ESTUDIO_IMG = `${SITE_URL}/og-image.png`;

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
      { property: "og:url", content: `${SITE_URL}/estudio` },
      { property: "og:title", content: "El Estudio — Rambla Rental" },
      {
        property: "og:description",
        content:
          "Estudio de foto y video en Mar del Plata. Reservá por hora con pack de luces y griperías opcional.",
      },
      {
        property: "og:image",
        content: ESTUDIO_IMG,
      },
      { property: "og:locale", content: "es_AR" },
      { name: "twitter:card", content: "summary_large_image" },
      { name: "twitter:title", content: "El Estudio — Rambla Rental" },
      { name: "twitter:description", content: "Estudio de foto y video · Mar del Plata" },
      {
        name: "twitter:image",
        content: ESTUDIO_IMG,
      },
    ],
    links: [{ rel: "canonical", href: `${SITE_URL}/estudio` }],
  }),
});
