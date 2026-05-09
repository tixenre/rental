import { createFileRoute } from "@tanstack/react-router";
import { ComingSoon } from "@/components/admin/ComingSoon";

export const Route = createFileRoute("/admin/pedidos")({
  component: () => (
    <ComingSoon
      title="Pedidos"
      description="Lista de alquileres, detalle con items y pagos, descarga de PDFs."
      phase="Fase 3"
    />
  ),
});
