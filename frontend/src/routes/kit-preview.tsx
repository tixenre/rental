import { createFileRoute, redirect } from "@tanstack/react-router";

/**
 * /kit-preview → /admin/diseno (solapa Design System).
 *
 * La vitrina del DS se consolidó en UNA sola fuente: el catálogo manifest-driven
 * dentro del back-office (`components/admin/ds-catalog`). Esta ruta era una
 * segunda galería, parcial y redundante, y además **pública sin auth**. El
 * redirect preserva el link viejo y deja la vitrina gobernada + gateada como el
 * resto del admin (decisión "consolidar las 2 galerías", librería del DS).
 */
export const Route = createFileRoute("/kit-preview")({
  beforeLoad: () => {
    throw redirect({ to: "/admin/diseno", replace: true });
  },
  component: () => null,
});
