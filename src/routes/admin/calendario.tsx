import { createFileRoute } from "@tanstack/react-router";
import { ComingSoon } from "@/components/admin/ComingSoon";

export const Route = createFileRoute("/admin/calendario")({
  component: () => (
    <ComingSoon
      title="Calendario"
      description="Vista mensual de disponibilidad y pedidos por día."
      phase="Fase 4"
    />
  ),
});
