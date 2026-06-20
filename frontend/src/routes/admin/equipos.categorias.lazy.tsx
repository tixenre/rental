import { createLazyFileRoute } from "@tanstack/react-router";
import { CategoriasSection } from "@/components/admin/equipos-mgmt/CategoriasSection";
import { DisenoSection } from "@/components/admin/diseno/DisenoSection";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/equipos/categorias")({
  component: CategoriasPage,
});

function CategoriasPage() {
  useDocumentTitle("Categorías · Back Office");
  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-4xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Back-office › Equipos
        </div>
        <h1 className="font-display text-3xl text-ink">Categorías</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Árbol jerárquico de categorías y cómo aparecen en el catálogo público.
        </p>
      </header>
      <CategoriasSection />
      <DisenoSection />
    </div>
  );
}
