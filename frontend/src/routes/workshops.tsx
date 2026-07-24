import { createFileRoute, Outlet } from "@tanstack/react-router";

/**
 * /workshops → /escuela. Layout solo para anidar los redirects de `/workshops` y
 * `/workshops/$slug` (ver `workshops.index.tsx` y `workshops.$slug.tsx`). El área
 * se renombró a `/escuela`; esta es la ÚNICA redirección que se preserva (era la
 * URL viva en prod). El nombre viejo `/talleres` se dejó de soportar.
 */
export const Route = createFileRoute("/workshops")({
  component: () => <Outlet />,
});
