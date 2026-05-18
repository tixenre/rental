import { createLazyFileRoute } from "@tanstack/react-router";
import { Wrench } from "lucide-react";

import { SpecDefinitionsContent } from "./specs.definitions.lazy";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/gear-compatibility")({
  component: GearCompatibilityPage,
});

function GearCompatibilityPage() {
  useDocumentTitle("Gear Compatibility · Back Office");

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-5xl mx-auto">
      <header className="space-y-1">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office
        </div>
        <h1 className="font-display text-3xl text-ink flex items-center gap-2">
          <Wrench className="h-6 w-6 text-amber" />
          Gear Compatibility
        </h1>
        <p className="text-sm text-muted-foreground max-w-2xl">
          Sistema de compatibilidad entre equipos AV: catálogo de specs que
          alimentan el match automático entre equipos.
        </p>
      </header>

      <SpecDefinitionsContent />
    </div>
  );
}
