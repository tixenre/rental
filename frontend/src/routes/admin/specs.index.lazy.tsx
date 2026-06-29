/**
 * specs.lazy.tsx — UI consolidada de specs por categoría raíz.
 *
 * Reemplaza varias UIs viejas (specs.definitions, specs.observatorio,
 * specs.familias, gear-compatibility, etc.). Lo importante:
 * - Tabs por categoría raíz (Cámaras, Lentes, …).
 * - Lista con drag-and-drop para reordenar prioridad.
 * - Por spec, 3 switches inline: Favorito / En Nombre / En Filtros.
 * - Drawer al click con detalle completo (tipo, valores, ayuda, uso).
 *
 * Los sub-componentes (paneles, filas, drawer, editores de template/formato)
 * viven en `@/components/admin/specs/SpecsConsolidadasHelpers` — este archivo
 * queda como orquestador del route.
 */
import { createLazyFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { AdminPage } from "@/components/admin/AdminPage";
import { Badge } from "@/design-system/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/design-system/ui/tabs";
import { useDocumentTitle } from "@/lib/use-document-title";
import { authedJson } from "@/lib/authedFetch";
import {
  CategoriaPanel,
  SpecDetailDrawer,
  type Spec,
  type PorCategoriaResponse,
} from "@/components/admin/specs/SpecsConsolidadasHelpers";

export const Route = createLazyFileRoute("/admin/specs/")({
  component: SpecsConsolidadasPage,
});

function SpecsConsolidadasPage() {
  useDocumentTitle("Specs · Back Office");
  const q = useQuery<PorCategoriaResponse>({
    queryKey: ["admin", "specs-por-categoria"],
    queryFn: () => authedJson<PorCategoriaResponse>("/api/admin/specs/por-categoria"),
  });

  const [selectedSpec, setSelectedSpec] = useState<Spec | null>(null);
  const [activeTab, setActiveTab] = useState<string>("");

  // Set default tab when data arrives
  const categorias = q.data?.categorias ?? [];
  const defaultTab = categorias[0]?.id ? String(categorias[0].id) : "";
  const currentTab = activeTab || defaultTab;

  return (
    <AdminPage
      title="Specs"
      maxW="max-w-6xl"
      description="Definiciones de specs por categoría raíz. Marcá favoritos para que aparezcan en card, mini-ficha, lateral y pills de la ficha. Arrastrá para reordenar."
    >
      <div className="space-y-6">
        {q.isLoading && <div className="text-sm text-muted-foreground">Cargando specs…</div>}
        {q.isError && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 space-y-2">
            <div className="text-sm font-medium text-destructive">Error cargando specs.</div>
            <div className="text-xs text-destructive/80 font-mono break-all">
              {(q.error as Error)?.message ?? "Error desconocido"}
            </div>
            <div className="text-xs text-muted-foreground">
              Si el deploy es reciente, esperá un minuto y refrescá. Si persiste, revisá que la
              migración
              <code className="mx-1 bg-muted px-1 rounded">e5a7b9d2c4f1_spec_def_flags</code>
              haya corrido en producción.
            </div>
          </div>
        )}

        {!q.isLoading && !q.isError && categorias.length === 0 && (
          <div className="text-sm text-muted-foreground border rounded-lg p-6 text-center">
            No hay specs sembradas todavía.
          </div>
        )}

        {categorias.length > 0 && (
          <Tabs value={currentTab} onValueChange={setActiveTab}>
            <TabsList className="flex flex-wrap h-auto gap-1">
              {categorias.map((cat) => (
                <TabsTrigger key={cat.id} value={String(cat.id)} className="gap-2">
                  {cat.nombre}
                  <Badge variant="secondary" className="text-2xs px-1.5 py-0">
                    {cat.specs.length}
                  </Badge>
                </TabsTrigger>
              ))}
            </TabsList>
            {categorias.map((cat) => (
              <TabsContent key={cat.id} value={String(cat.id)} className="mt-4">
                <CategoriaPanel categoria={cat} onSelectSpec={(s) => setSelectedSpec(s)} />
              </TabsContent>
            ))}
          </Tabs>
        )}

        {selectedSpec && (
          <SpecDetailDrawer spec={selectedSpec} onClose={() => setSelectedSpec(null)} />
        )}
      </div>
    </AdminPage>
  );
}
