import { createFileRoute } from "@tanstack/react-router";
import { ComingSoon } from "@/components/admin/ComingSoon";

export const Route = createFileRoute("/admin/settings")({
  component: () => (
    <ComingSoon
      title="Settings"
      description="Imports CSV (equipos, clientes, alquileres) y herramientas de mantenimiento."
      phase="Fase 5"
    />
  ),
});
