import { createLazyFileRoute } from "@tanstack/react-router";
import { AdminPage } from "@/components/admin/AdminPage";
import { MarcasSection } from "@/components/admin/equipos-mgmt/MarcasSection";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export const Route = createLazyFileRoute("/admin/equipos/marcas")({
  component: MarcasPage,
});

function MarcasPage() {
  useDocumentTitle("Marcas · Back Office");
  return (
    <AdminPage
      title="Marcas"
      maxW="max-w-4xl"
      description="Marcas visibles en el catálogo público y su orden en el carrusel."
    >
      <MarcasSection />
    </AdminPage>
  );
}
