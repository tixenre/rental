import { createLazyFileRoute } from "@tanstack/react-router";
import { AdminPage } from "@/components/admin/AdminPage";
import { SpecTemplatesSection } from "@/components/admin/specs/SpecTemplatesSection";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export const Route = createLazyFileRoute("/admin/equipos/specs")({
  component: SpecsPage,
});

function SpecsPage() {
  useDocumentTitle("Specs por categoría · Back Office");
  return (
    <AdminPage
      title="Specs por categoría"
      eyebrow="Equipos"
      maxW="max-w-4xl"
      description="Define qué campos técnicos pide cada categoría. Estos labels también guían la IA al importar."
    >
      <SpecTemplatesSection />
    </AdminPage>
  );
}
