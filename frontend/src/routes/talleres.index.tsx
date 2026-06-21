import { createFileRoute, redirect } from "@tanstack/react-router";

/** /talleres → /workshops (área renombrada; redirect para links viejos de prod). */
export const Route = createFileRoute("/talleres/")({
  beforeLoad: () => {
    throw redirect({ to: "/workshops", replace: true });
  },
  component: () => null,
});
