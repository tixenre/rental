import { createLazyFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { es } from "date-fns/locale";
import { AlertTriangle, ChevronDown, ChevronRight, RefreshCw } from "lucide-react";

import { adminApi } from "@/lib/admin/api";
import type { ServerError } from "@/lib/admin/api/errores";
import { useDocumentTitle } from "@/lib/use-document-title";
import { QueryState } from "@/components/admin/QueryState";
import { ListSkeleton } from "@/components/admin/skeletons";
import { EmptyState } from "@/design-system/composites/EmptyState";

export const Route = createLazyFileRoute("/admin/errores")({
  component: ErroresPage,
});

function ErrorRow({ e }: { e: ServerError }) {
  const [open, setOpen] = useState(false);
  const ago = formatDistanceToNow(new Date(e.created_at), { addSuffix: true, locale: es });

  return (
    <div className="border hairline rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start gap-3 p-4 text-left hover:bg-muted/40 transition-colors"
      >
        <div className="mt-0.5 shrink-0">
          {open ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className="font-mono text-xs bg-destructive/10 text-destructive px-1.5 py-0.5 rounded">
              {e.error_type}
            </span>
            <span className="font-mono text-xs text-muted-foreground">{e.route}</span>
            <span className="text-xs text-muted-foreground ml-auto shrink-0">{ago}</span>
          </div>
          <p className="text-sm text-ink truncate">{e.message || "(sin mensaje)"}</p>
        </div>
      </button>

      {open && (
        <div className="border-t hairline bg-muted/20 p-4 space-y-3">
          {e.request_id && (
            <div>
              <div className="font-mono text-2xs uppercase tracking-widest text-muted-foreground mb-1">
                Request ID
              </div>
              <code className="text-xs font-mono">{e.request_id}</code>
            </div>
          )}
          <div>
            <div className="font-mono text-2xs uppercase tracking-widest text-muted-foreground mb-1">
              Traceback
            </div>
            <pre className="text-xs font-mono bg-ink text-background rounded p-3 overflow-x-auto whitespace-pre-wrap break-all">
              {e.traceback || e.message || "(vacío)"}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

function ErroresPage() {
  useDocumentTitle("Errores del servidor · Back Office");

  const query = useQuery({
    queryKey: ["admin", "server-errors"],
    queryFn: () => adminApi.listServerErrors(),
    refetchInterval: 5 * 60_000,
    staleTime: 0,
  });

  const { data, refetch, dataUpdatedAt } = query;
  const updatedAt = dataUpdatedAt ? new Date(dataUpdatedAt) : null;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-destructive" />
          <h1 className="text-xl font-display font-semibold text-ink">Errores del servidor</h1>
          {data && (
            <span className="font-mono text-xs text-muted-foreground">
              ({data.total} registros)
            </span>
          )}
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-ink transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Actualizar
        </button>
      </div>

      {updatedAt && (
        <p className="text-xs text-muted-foreground">
          Actualizado {formatDistanceToNow(updatedAt, { addSuffix: true, locale: es })}
          {" · "}
          Refresca automático cada 5 min
        </p>
      )}

      <QueryState
        query={query}
        isEmpty={(d) => d.errores.length === 0}
        skeleton={<ListSkeleton rows={6} />}
        empty={
          <EmptyState
            icon={<AlertTriangle className="h-6 w-6" />}
            title="Sin errores registrados"
            sub="Todo bien."
          />
        }
      >
        {(d) => (
          <div className="space-y-2">
            {d.errores.map((e) => (
              <ErrorRow key={e.id} e={e} />
            ))}
          </div>
        )}
      </QueryState>
    </div>
  );
}
