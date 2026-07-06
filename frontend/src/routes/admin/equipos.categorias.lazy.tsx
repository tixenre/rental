import { createLazyFileRoute } from "@tanstack/react-router";
import { AdminPage } from "@/components/admin/AdminPage";
import { CategoriasSection } from "@/components/admin/equipos-mgmt/CategoriasSection";
import { DisenoSection } from "@/components/admin/diseno/DisenoSection";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export const Route = createLazyFileRoute("/admin/equipos/categorias")({
  component: CategoriasPage,
});

function CategoriasPage() {
  useDocumentTitle("Categorías · Back Office");
  return (
    <AdminPage
      title="Categorías"
      maxW="max-w-4xl"
      description="Árbol jerárquico de categorías y cómo aparecen en el catálogo público."
    >
      <div className="space-y-6">
        <CategoriasSection />
        <DisenoSection />
      </div>
    </AdminPage>
  );
}
