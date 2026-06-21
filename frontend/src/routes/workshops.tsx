import { createFileRoute, Outlet } from "@tanstack/react-router";

import { SITE_URL } from "@/lib/site";

export const Route = createFileRoute("/workshops")({
  component: () => <Outlet />,
  head: () => ({
    meta: [
      { title: "Workshops & Talleres — Rambla Rental" },
      {
        name: "description",
        content:
          "Talleres y workshops de fotografía, video y dirección de arte en Rambla Estudio, Mar del Plata.",
      },
      { property: "og:type", content: "website" },
      { property: "og:url", content: `${SITE_URL}/workshops` },
      { property: "og:title", content: "Workshops & Talleres — Rambla Rental" },
      {
        property: "og:description",
        content:
          "Talleres y workshops de fotografía, video y dirección de arte en Rambla Estudio, Mar del Plata.",
      },
      { property: "og:locale", content: "es_AR" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
    links: [{ rel: "canonical", href: `${SITE_URL}/workshops` }],
  }),
});
