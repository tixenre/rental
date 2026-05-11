import { createFileRoute } from "@tanstack/react-router";
import { CategoriasSection } from "@/components/admin/equipos-mgmt/CategoriasSection";

export const Route = createFileRoute("/admin/equipos/categorias")({
  component: CategoriasPage,
});

function CategoriasPage() {
  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-4xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office › Equipos
        </div>
        <h1 className="font-display text-3xl text-ink">Categorías</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Árbol jerárquico de categorías que organiza el catálogo público y el inventario.
        </p>
      </header>
      <CategoriasSection />
    </div>
  );
}
