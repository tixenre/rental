import { createLazyFileRoute } from "@tanstack/react-router";
import { AdminPage } from "@/components/admin/AdminPage";
import { ProductorasSection } from "@/components/admin/productoras/ProductorasSection";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export const Route = createLazyFileRoute("/admin/productoras")({
  component: ProductorasPage,
});

function ProductorasPage() {
  useDocumentTitle("Productoras · Back Office");
  return (
    <AdminPage
      title="Productoras"
      maxW="list"
      description="Entidades fiscales compartidas — vinculá cuentas de cliente que facturan a nombre de una productora."
    >
      <ProductorasSection />
    </AdminPage>
  );
}
