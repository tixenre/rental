import { useEffect } from "react";
import { createLazyFileRoute, useNavigate } from "@tanstack/react-router";

/**
 * Legacy: la gestión de specs vive ahora en `/admin/specs` (página unificada
 * con tabs por categoría + drag-drop). Redirigimos a la nueva ruta para no
 * dejar puntas sueltas si alguien tiene un bookmark viejo.
 */
export const Route = createLazyFileRoute("/admin/specs/definitions")({
  component: SpecsDefinitionsRedirect,
});

function SpecsDefinitionsRedirect() {
  const navigate = useNavigate();
  useEffect(() => {
    navigate({ to: "/admin/specs", replace: true });
  }, [navigate]);
  return (
    <div className="p-10 text-sm text-muted-foreground text-center">
      Esta página se movió a /admin/specs. Redirigiendo…
    </div>
  );
}
