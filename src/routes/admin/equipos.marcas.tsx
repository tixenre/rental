import { createFileRoute } from "@tanstack/react-router";
import { MarcasSection } from "@/components/admin/equipos-mgmt/MarcasSection";

export const Route = createFileRoute("/admin/equipos/marcas")({
  component: MarcasPage,
});

function MarcasPage() {
  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-4xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office › Equipos
        </div>
        <h1 className="font-display text-3xl text-ink">Marcas</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Marcas visibles en el catálogo público y su orden en el carrusel.
        </p>
      </header>
      <MarcasSection />
    </div>
  );
}
