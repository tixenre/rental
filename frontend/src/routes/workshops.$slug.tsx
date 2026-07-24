import { createFileRoute, redirect } from "@tanstack/react-router";

/**
 * /workshops/$slug → /escuela/$slug (área renombrada; redirect que **preserva el
 * slug** para no romper links viejos de prod a un taller puntual).
 */
export const Route = createFileRoute("/workshops/$slug")({
  beforeLoad: ({ params }) => {
    throw redirect({ to: "/escuela/$slug", params: { slug: params.slug }, replace: true });
  },
  component: () => null,
});
