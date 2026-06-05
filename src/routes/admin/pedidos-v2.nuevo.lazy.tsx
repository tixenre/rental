import { createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { adminApi } from "@/lib/admin/api";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/pedidos-v2/nuevo")({
  component: NuevoPedidoV2Page,
});

// Crea un borrador y abre el editor v2. Espeja el armador de v1 (pedidos.nuevo)
// pero navega a la ruta v2 — mismo endpoint `createPedido`, sin tocar backend.
function NuevoPedidoV2Page() {
  useDocumentTitle("Nuevo pedido · Back-office v2");
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
        navigate({ to: "/admin/pedidos-v2/$id", params: { id: String(p.id) }, replace: true });
      })
      .catch((e: Error) => {
        toast.error(`No se pudo crear el borrador: ${e.message}`);
        navigate({ to: "/admin/pedidos-v2", replace: true });
      });
  }, [navigate]);

  return (
    <div className="flex items-center justify-center h-[60vh] text-muted-foreground gap-2">
      <Loader2 className="h-4 w-4 animate-spin" /> Creando borrador…
    </div>
  );
}
