import { createLazyFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Sparkles, Library, Wrench } from "lucide-react";

import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

import { SpecDefinitionsContent } from "./specs.definitions.lazy";
import { PropuestasContent } from "./specs.propuestas.lazy";
import { useDocumentTitle } from "@/lib/use-document-title";

type Tab = "definitions" | "propuestas";
const TAB_STORAGE_KEY = "gear-compat:tab";

export const Route = createLazyFileRoute("/admin/gear-compatibility")({
  component: GearCompatibilityPage,
});

function GearCompatibilityPage() {
  useDocumentTitle("Gear Compatibility · Back Office");
  const [activeTab, setActiveTab] = useState<Tab>(() => {
    if (typeof window === "undefined") return "definitions";
    return (localStorage.getItem(TAB_STORAGE_KEY) as Tab) ?? "definitions";
  });

  useEffect(() => {
    localStorage.setItem(TAB_STORAGE_KEY, activeTab);
  }, [activeTab]);

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
          alimentan el match automático y las propuestas que el skill IA
          genera para mantener el catálogo limpio.
        </p>
      </header>

      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as Tab)}>
        <TabsList className="w-full max-w-md">
          <TabsTrigger value="definitions" className="flex-1 gap-1.5">
            <Library className="h-3.5 w-3.5" />
            Definiciones
          </TabsTrigger>
          <TabsTrigger value="propuestas" className="flex-1 gap-1.5">
            <Sparkles className="h-3.5 w-3.5" />
            Propuestas IA
          </TabsTrigger>
        </TabsList>
        <TabsContent value="definitions" className="mt-4">
          <SpecDefinitionsContent />
        </TabsContent>
        <TabsContent value="propuestas" className="mt-4">
          <PropuestasContent />
        </TabsContent>
      </Tabs>
    </div>
  );
}
