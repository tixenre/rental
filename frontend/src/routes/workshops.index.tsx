import { createFileRoute, redirect } from "@tanstack/react-router";

/** /workshops → /escuela (área renombrada; redirect para links viejos de prod). */
export const Route = createFileRoute("/workshops/")({
  beforeLoad: () => {
    throw redirect({ to: "/escuela", replace: true });
  },
  component: () => null,
});
