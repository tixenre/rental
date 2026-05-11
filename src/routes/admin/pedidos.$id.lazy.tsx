import { createLazyFileRoute } from "@tanstack/react-router";
import { PedidoPage } from "@/components/admin/pedido/PedidoPage";

export const Route = createLazyFileRoute("/admin/pedidos/$id")({
  component: PedidoDetailRoute,
});

function PedidoDetailRoute() {
  const { id } = Route.useParams();
  const pedidoId = parseInt(id, 10);
  if (!pedidoId) return <div className="p-6 text-sm text-destructive">ID inválido</div>;
  return <PedidoPage pedidoId={pedidoId} />;
}
