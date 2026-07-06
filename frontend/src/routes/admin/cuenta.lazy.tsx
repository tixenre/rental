import { createLazyFileRoute } from "@tanstack/react-router";

import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { AdminPage } from "@/components/admin/AdminPage";
import { AdminSection } from "@/components/admin/AdminSection";
import { PasskeysSection } from "@/components/admin/settings/PasskeysSection";
import { SessionsSection } from "@/components/admin/settings/SessionsSection";

export const Route = createLazyFileRoute("/admin/cuenta")({
  component: CuentaPage,
});

function CuentaPage() {
  useDocumentTitle("Mi cuenta · Back Office");

  return (
    <AdminPage
      title="Mi cuenta"
      maxW="max-w-4xl"
      description="Seguridad y acceso de TU cuenta de admin — separado de la configuración del negocio (eso vive en Settings)."
    >
      <div className="space-y-6">
        <AdminSection title="Claves de acceso (acceso sin contraseña)" storageKey="cuenta:passkeys">
          <PasskeysSection />
        </AdminSection>

        <AdminSection title="Sesiones activas" storageKey="cuenta:sesiones" defaultOpen={false}>
          <SessionsSection />
        </AdminSection>
      </div>
    </AdminPage>
  );
}
