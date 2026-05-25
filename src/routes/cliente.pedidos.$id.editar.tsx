import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { authedFetch } from "@/lib/authedFetch";
import { PublicLayout } from "@/components/rental/PublicLayout";
import { PedidoPage } from "@/components/admin/pedido/PedidoPage";

export const Route = createFileRoute("/cliente/pedidos/$id/editar")({
  head: () => ({ meta: [{ title: "Modificar pedido — Rambla Rental" }] }),
  component: ClienteEditarPedido,
});

function ClienteEditarPedido() {
  const { id } = Route.useParams();
  const navigate = useNavigate();
  const [authed, setAuthed] = useState<null | boolean>(null);

  useEffect(() => {
    let alive = true;
    authedFetch("/api/cliente/me")
      .then((r) => {
        if (alive) setAuthed(r.ok);
      })
      .catch(() => {
        if (alive) setAuthed(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (authed === false) navigate({ to: "/cliente/login" });
  }, [authed, navigate]);

  if (!authed) {
    return (
      <PublicLayout topBar={{ variant: "cliente" }}>
        <div className="grid place-items-center py-24 text-sm text-muted-foreground">Cargando…</div>
      </PublicLayout>
    );
  }

  const pedidoId = parseInt(id, 10);
  return (
    <PublicLayout topBar={{ variant: "cliente" }}>
      <PedidoPage
        pedidoId={pedidoId}
        mode="cliente"
        onClose={() => navigate({ to: "/cliente/portal" })}
      />
    </PublicLayout>
  );
}
