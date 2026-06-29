import { createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef } from "react";
import { toast } from "sonner";
import { Spinner } from "@/design-system/ui/spinner";
import { adminApi } from "@/lib/admin/api";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/pedidos/nuevo")({
  component: NuevoPedidoPage,
});

// Crea un borrador y abre el editor. Mismo endpoint `createPedido`, sin tocar backend.
function NuevoPedidoPage() {
  useDocumentTitle("Nuevo pedido · Back-office");
  const navigate = useNavigate();
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    // El backend exige fecha_desde/fecha_hasta NOT NULL → arrancamos con
    // hoy → mañana como placeholder editable desde el editor.
    const hoy = new Date();
    const manana = new Date(hoy);
    manana.setDate(manana.getDate() + 1);
    const ymd = (d: Date) => d.toISOString().slice(0, 10);
    adminApi
      .createPedido({
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
      <Spinner size="sm" /> Creando borrador…
    </div>
  );
}
