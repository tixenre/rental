import { createFileRoute } from "@tanstack/react-router";
import { EtiquetasSection } from "@/components/admin/equipos-mgmt/EtiquetasSection";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createFileRoute("/admin/equipos/etiquetas")({
  component: EtiquetasPage,
});

function EtiquetasPage() {
  useDocumentTitle("Etiquetas · Back Office");
  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-4xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office › Equipos
        </div>
        <h1 className="font-display text-3xl text-ink">Etiquetas libres</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Bolsa de keywords manuales que se suman a marca/modelo/categorías al buscar.
        </p>
      </header>
      <EtiquetasSection />
    </div>
  );
}
