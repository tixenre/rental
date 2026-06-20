import { createLazyFileRoute } from "@tanstack/react-router";
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
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-4xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office
        </div>
        <h1 className="font-display text-3xl text-ink">Diseño y marca</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Identidad visual y datos del negocio que aparecen en el sitio público y los mails.
        </p>
      </header>
      <BrandSvgSection />
      <BrandingSection />
      <ContactoSection />
    </div>
  );
}
