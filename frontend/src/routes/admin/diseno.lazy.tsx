import { createLazyFileRoute } from "@tanstack/react-router";
import { AdminPage } from "@/components/admin/AdminPage";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/design-system/ui/tabs";
import { BrandSvgSection } from "@/components/admin/diseno/BrandSvgSection";
import { BrandingSection } from "@/components/admin/diseno/BrandingSection";
import { ContactoSection } from "@/components/admin/diseno/ContactoSection";
import { DsCatalog } from "@/components/admin/ds-catalog";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export const Route = createLazyFileRoute("/admin/diseno")({
  component: DisenoPage,
});

function DisenoPage() {
  useDocumentTitle("Assets y diseño · Back Office");
  return (
    <AdminPage
      title="Assets y diseño"
      maxW="max-w-4xl"
      description="Tu marca y la librería de diseño de Rambla, en un solo lugar."
    >
      <Tabs defaultValue="assets">
        <TabsList>
          <TabsTrigger value="assets">Assets</TabsTrigger>
          <TabsTrigger value="ds">Design System</TabsTrigger>
        </TabsList>

        {/* Assets: lo que el dueño sube/edita (marca + datos de contacto). */}
        <TabsContent value="assets" className="mt-6 space-y-6">
          <BrandSvgSection />
          <BrandingSection />
          <ContactoSection />
        </TabsContent>

        {/* Design System: la librería, read-only por ahora — puerta al editor de temas. */}
        <TabsContent value="ds" className="mt-6">
          <DsCatalog />
        </TabsContent>
      </Tabs>
    </AdminPage>
  );
}
