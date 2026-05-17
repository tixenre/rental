import { createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { adminApi } from "@/lib/admin/api";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/pedidos/nuevo")({
  component: NuevoPedidoPage,
});

function NuevoPedidoPage() {
  useDocumentTitle("Nuevo pedido · Back Office");
  const navigate = useNavigate();
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    // El backend exige fecha_desde/fecha_hasta NOT NULL, así que arrancamos
    // con hoy → mañana como placeholder editable desde la pestaña Info.
    const hoy = new Date();
    const manana = new Date(hoy);
    manana.setDate(manana.getDate() + 1);
    const ymd = (d: Date) => d.toISOString().slice(0, 10);
    adminApi.createPedido({
      estado: "borrador",
      cliente_nombre: "",
      fecha_desde: ymd(hoy),
      fecha_hasta: ymd(manana),
      items: [],
    })
      .then((p) => {
        navigate({ to: "/admin/pedidos/$id", params: { id: String(p.id) }, replace: true });
      })
      .catch((e: Error) => {
        toast.error(`No se pudo crear el borrador: ${e.message}`);
        navigate({ to: "/admin/pedidos", replace: true });
      });
  }, [navigate]);

  return (
    <div className="flex items-center justify-center h-[60vh] text-muted-foreground gap-2">
      <Loader2 className="h-4 w-4 animate-spin" /> Creando borrador…
    </div>
  );
}
