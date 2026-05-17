import { createLazyFileRoute } from "@tanstack/react-router";
import { SpecTemplatesSection } from "@/components/admin/specs/SpecTemplatesSection";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/equipos/specs")({
  component: SpecsPage,
});

function SpecsPage() {
  useDocumentTitle("Specs por categoría · Back Office");
  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-4xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office › Equipos
        </div>
        <h1 className="font-display text-3xl text-ink">Specs por categoría</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Define qué campos técnicos pide cada categoría. Estos labels también guían la IA al importar.
        </p>
      </header>
      <SpecTemplatesSection />
    </div>
  );
}
