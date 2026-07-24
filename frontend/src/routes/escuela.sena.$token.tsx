import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/escuela/sena/$token")({
  head: () => ({
    meta: [{ title: "Completá tu seña — Rambla Escuela" }, { name: "robots", content: "noindex" }],
  }),
});
