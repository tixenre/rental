/**
 * Sección Estados — loading / vacío / error, y QueryState que los cablea en un
 * solo lugar sobre un resultado de useQuery.
 */
import { Inbox } from "lucide-react";

import { type CatalogSection } from "../types";
import { Caption } from "../catalog-kit";
import { Skeleton } from "@/design-system/ui/skeleton";
import { TableSkeleton, ListSkeleton, CardGridSkeleton } from "@/components/admin/skeletons";
import { EmptyState } from "@/components/rental/EmptyState";
import { ErrorState } from "@/components/admin/ErrorState";
import { QueryState } from "@/components/admin/QueryState";

type Demo = { items: number[] };

// Mocks de un resultado de useQuery (TanStack) — uno por ramal.
const Q_LOADING = { isLoading: true, isError: false, error: null, data: undefined };
// error: null a propósito → muestra el ramal de error sin loguear a consola
// (ErrorState solo loguea si recibe un error real; acá la demo no lo necesita).
const Q_ERROR = { isLoading: false, isError: true, error: null, data: undefined };
const Q_EMPTY = { isLoading: false, isError: false, error: null, data: { items: [] } };
const Q_OK = { isLoading: false, isError: false, error: null, data: { items: [1, 2, 3] } };

function Panel({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Caption>{label}</Caption>
      <div className="overflow-hidden rounded-md border hairline">{children}</div>
    </div>
  );
}

export const statesSection: CatalogSection = {
  id: "estados",
  title: "Estados (carga / vacío / error)",
  hint: "QueryState ramifica los 4 estados; acá los primitivos que cablea.",
  specimens: [
    {
      name: "Skeleton + presets",
      files: ["design-system/ui/skeleton.tsx", "components/admin/skeletons.tsx"],
      blurb: "Skeleton base + 3 presets de forma. ListSkeleton es el default de QueryState.",
      render: () => (
        <div className="grid gap-4 md:grid-cols-3">
          <Panel label="TableSkeleton">
            <div className="p-3">
              <TableSkeleton rows={3} cols={3} />
            </div>
          </Panel>
          <Panel label="ListSkeleton">
            <div className="p-3">
              <ListSkeleton rows={4} />
            </div>
          </Panel>
          <Panel label="CardGridSkeleton">
            <div className="p-3">
              <CardGridSkeleton count={4} />
            </div>
          </Panel>
          <Panel label="Skeleton (base)">
            <div className="flex items-center gap-3 p-3">
              <Skeleton className="h-10 w-10 rounded-full" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-3 w-3/4" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            </div>
          </Panel>
        </div>
      ),
    },
    {
      name: "EmptyState · ErrorState",
      files: ["components/rental/EmptyState.tsx", "components/admin/ErrorState.tsx"],
      blurb:
        "Vacío (amber) y error (destructive, loguea el técnico a consola, muestra copy genérico).",
      render: () => (
        <div className="grid gap-4 md:grid-cols-2">
          <Panel label="EmptyState">
            <EmptyState
              icon={<Inbox className="h-6 w-6" />}
              title="Sin datos"
              sub="No hay nada todavía."
            />
          </Panel>
          <Panel label="ErrorState">
            <ErrorState onRetry={() => {}} />
          </Panel>
        </div>
      ),
    },
    {
      name: "QueryState",
      files: ["components/admin/QueryState.tsx"],
      blurb:
        "Un solo lugar ramifica loading → error → empty → ok. children es render-prop con data garantizada.",
      render: () => (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Panel label="loading">
            <div className="p-3">
              <QueryState<Demo> query={Q_LOADING} skeleton={<ListSkeleton rows={3} />}>
                {() => null}
              </QueryState>
            </div>
          </Panel>
          <Panel label="error">
            <QueryState<Demo> query={Q_ERROR}>{() => null}</QueryState>
          </Panel>
          <Panel label="empty">
            <QueryState<Demo> query={Q_EMPTY} isEmpty={(d) => d.items.length === 0}>
              {() => null}
            </QueryState>
          </Panel>
          <Panel label="ok">
            <QueryState<Demo> query={Q_OK} isEmpty={(d) => d.items.length === 0}>
              {(d) => (
                <ul className="space-y-1 p-3 text-sm text-ink">
                  {d.items.map((i) => (
                    <li key={i}>Ítem {i}</li>
                  ))}
                </ul>
              )}
            </QueryState>
          </Panel>
        </div>
      ),
    },
  ],
};
