import { createLazyFileRoute } from "@tanstack/react-router";
import { AdminPage } from "@/components/admin/AdminPage";
import { BrandSvgSection } from "@/components/admin/diseno/BrandSvgSection";
import { BrandingSection } from "@/components/admin/diseno/BrandingSection";
import { ContactoSection } from "@/components/admin/diseno/ContactoSection";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/diseno")({
  component: DisenoPage,
});

function DisenoPage() {
  useDocumentTitle("Diseño y marca · Back Office");
  return (
    <AdminPage
      title="Diseño y marca"
      maxW="max-w-4xl"
      description="Identidad visual y datos del negocio que aparecen en el sitio público y los mails."
    >
      <div className="space-y-6">
        <BrandSvgSection />
        <BrandingSection />
        <ContactoSection />
      </div>
    </AdminPage>
  );
}
