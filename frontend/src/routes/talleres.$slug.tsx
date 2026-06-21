import { createFileRoute, redirect } from "@tanstack/react-router";

/**
 * /talleres/$slug → /workshops/$slug (área renombrada; redirect que **preserva el
 * slug** para no romper links viejos de prod a un taller puntual).
 */
export const Route = createFileRoute("/talleres/$slug")({
  beforeLoad: ({ params }) => {
    throw redirect({ to: "/workshops/$slug", params: { slug: params.slug }, replace: true });
  },
  component: () => null,
});
