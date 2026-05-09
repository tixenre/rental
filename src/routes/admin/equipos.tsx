import { createFileRoute } from "@tanstack/react-router";
import { ComingSoon } from "@/components/admin/ComingSoon";

export const Route = createFileRoute("/admin/equipos")({
  component: () => (
    <ComingSoon
      title="Equipos"
      description="Listado, alta, edición de equipos. Categorías, etiquetas, kits e historial."
      phase="Fase 2"
    />
  ),
});
