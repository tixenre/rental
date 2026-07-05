import { createLazyFileRoute } from "@tanstack/react-router";
import { AdminPage } from "@/components/admin/AdminPage";
import { ProductorasSection } from "@/components/admin/productoras/ProductorasSection";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/productoras")({
  component: ProductorasPage,
});

function ProductorasPage() {
  useDocumentTitle("Productoras · Back Office");
  return (
    <AdminPage
      title="Productoras"
      maxW="max-w-6xl"
      description="Entidades fiscales compartidas — vinculá cuentas de cliente que facturan a nombre de una productora."
    >
      <ProductorasSection />
    </AdminPage>
  );
}
