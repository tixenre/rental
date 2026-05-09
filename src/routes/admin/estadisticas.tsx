import { createFileRoute } from "@tanstack/react-router";
import { ComingSoon } from "@/components/admin/ComingSoon";

export const Route = createFileRoute("/admin/estadisticas")({
  component: () => (
    <ComingSoon
      title="Estadísticas"
      description="Reportes de ingresos, equipos más alquilados, métricas."
      phase="Fase 5"
    />
  ),
});
