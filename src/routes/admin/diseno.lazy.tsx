import { createLazyFileRoute } from "@tanstack/react-router";
import { DisenoSection } from "@/components/admin/diseno/DisenoSection";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/diseno")({
  component: DisenoPage,
});

function DisenoPage() {
  useDocumentTitle("Diseño · Back Office");
  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-4xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office
        </div>
        <h1 className="font-display text-3xl text-ink">Diseño</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Cómo se ve el catálogo público — orden y visibilidad de las secciones.
        </p>
      </header>
      <DisenoSection />
    </div>
  );
}
