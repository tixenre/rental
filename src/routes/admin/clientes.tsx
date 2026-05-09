import { createFileRoute } from "@tanstack/react-router";
import { ComingSoon } from "@/components/admin/ComingSoon";

export const Route = createFileRoute("/admin/clientes")({
  component: () => (
    <ComingSoon
      title="Clientes"
      description="CRUD de clientes con historial de pedidos."
      phase="Fase 4"
    />
  ),
});
