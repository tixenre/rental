import { createLazyFileRoute } from "@tanstack/react-router";

import { CalendarioWidget } from "@/components/admin/CalendarioWidget";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/calendario")({
  component: CalendarioPage,
});

function CalendarioPage() {
  useDocumentTitle("Calendario · Back Office");
  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-7xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office
        </div>
        <h1 className="font-display text-3xl text-ink">Calendario</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Pedidos por fecha. Click en un bloque para abrir el pedido.
        </p>
      </header>

      <CalendarioWidget variant="full" initialView="mes" />
    </div>
  );
}
