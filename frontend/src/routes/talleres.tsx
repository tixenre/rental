import { createFileRoute, Outlet } from "@tanstack/react-router";

/**
 * /talleres → /workshops. Layout solo para anidar los redirects de `/talleres` y
 * `/talleres/$slug` (ver `talleres.index.tsx` y `talleres.$slug.tsx`). El área se
 * renombró a `/workshops`; esto preserva los links viejos de prod.
 */
export const Route = createFileRoute("/talleres")({
  component: () => <Outlet />,
});
