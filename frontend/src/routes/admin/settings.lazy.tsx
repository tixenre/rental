import { createLazyFileRoute } from "@tanstack/react-router";

import { useDocumentTitle } from "@/lib/use-document-title";
import { AdminSection } from "@/components/admin/AdminSection";
import { EmailsAdmin } from "@/components/admin/email/EmailsAdmin";
import { ComisionesSection } from "@/components/admin/settings/ComisionesSection";
import { DescuentosJornadaSection } from "@/components/admin/settings/DescuentosJornadaSection";
import { BufferSection } from "@/components/admin/settings/BufferSection";
import { GoogleAnalyticsSection } from "@/components/admin/settings/GoogleAnalyticsSection";
import { CalendarFeedSection } from "@/components/admin/settings/CalendarFeedSection";
import { HorariosSection } from "@/components/admin/settings/HorariosSection";
import { FaqSection } from "@/components/admin/settings/FaqSection";
import { RankingSection } from "@/components/admin/settings/RankingSection";
import { CambioYPreciosSection } from "@/components/admin/settings/CambioYPreciosSection";

export const Route = createLazyFileRoute("/admin/settings")({
  component: SettingsPage,
});

function SettingsPage() {
  useDocumentTitle("Settings · Back Office");

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-4xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office
        </div>
        <h1 className="font-display text-3xl text-ink">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Configuración del sistema y herramientas de mantenimiento.
        </p>
      </header>

      <AdminSection title="Descuentos por jornadas" storageKey="settings:descuentos">
        <DescuentosJornadaSection />
      </AdminSection>

      <AdminSection title="Buffer entre alquileres" storageKey="settings:buffer">
        <BufferSection />
      </AdminSection>

      <AdminSection title="Horarios de retiro" storageKey="settings:horarios">
        <HorariosSection />
      </AdminSection>

      <AdminSection title="Preguntas frecuentes" storageKey="settings:faq" defaultOpen={false}>
        <FaqSection />
      </AdminSection>

      <AdminSection title="Cambio y precios" storageKey="settings:cambio">
        <CambioYPreciosSection />
      </AdminSection>

      <AdminSection title="Ranking automático" storageKey="settings:ranking" defaultOpen={false}>
        <RankingSection />
      </AdminSection>

      <AdminSection title="Google Analytics" storageKey="settings:ga4" defaultOpen={false}>
        <GoogleAnalyticsSection />
      </AdminSection>

      <AdminSection title="Calendario (feed iCal)" storageKey="settings:ical" defaultOpen={false}>
        <CalendarFeedSection />
      </AdminSection>

      <AdminSection
        title="Reparto de comisiones"
        storageKey="settings:comisiones"
        defaultOpen={false}
      >
        <ComisionesSection />
      </AdminSection>

      <AdminSection title="Emails" storageKey="settings:emails" defaultOpen={false}>
        <EmailsAdmin />
      </AdminSection>
    </div>
  );
}
