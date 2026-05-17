import { createLazyFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Archive, Loader2, CheckCircle2, ArrowUpRight, AlertCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

import { adminApi } from "@/lib/admin/api";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/specs/legacy")({
  component: LegacyPage,
});

function LegacyPage() {
  useDocumentTitle("Cleanup legacy · Back Office");
  const qc = useQueryClient();
  const listQ = useQuery({
    queryKey: ["admin", "specs-legacy"],
    queryFn: () => adminApi.listLegacyInventario(),
    staleTime: 30_000,
  });

  const promoverMut = useMutation({
    mutationFn: (equipoId: number) => adminApi.promoverLegacyEquipo(equipoId),
    onSuccess: (data) => {
      toast.success(
        `Equipo #${data.equipo_id}: ${data.promoted_count} promovidas, ${data.kept_count} quedan en JSON`,
      );
      qc.invalidateQueries({ queryKey: ["admin", "specs-legacy"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const items = listQ.data?.items ?? [];
  const totalSpecs = items.reduce((acc, x) => acc + x.total, 0);
  const totalMatched = items.reduce((acc, x) => acc + x.matched, 0);
  const totalCustom = items.reduce((acc, x) => acc + x.custom, 0);

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-5xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office › Specs
        </div>
        <h1 className="font-display text-3xl text-ink flex items-center gap-2">
          <Archive className="h-6 w-6 text-amber" />
          Cleanup de specs legacy
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
          Equipos que todavía guardan specs en <code className="font-mono">equipo_fichas.specs_json</code>
          {" "}(formato legacy de texto libre) en lugar del catálogo estructurado.
          El tool <strong>"Promover"</strong> migra las que matchean un spec
          canónico a <code className="font-mono">equipo_specs</code> y las saca
          del JSON, manteniendo intactas las custom hasta que las cures
          manualmente.
        </p>
      </header>

      {/* Stats */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <StatCard label="Equipos con legacy" value={items.length} />
        <StatCard label="Specs totales" value={totalSpecs} />
        <StatCard
          label="Matched (promovibles)" value={totalMatched} tone="ok"
        />
        <StatCard
          label="Custom (sin equivalente)" value={totalCustom} tone="warn"
        />
      </section>

      {listQ.isLoading && (
        <div className="rounded-md border hairline px-4 py-6 text-center text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin mx-auto mb-1" />
          Analizando…
        </div>
      )}

      {!listQ.isLoading && items.length === 0 && (
        <div className="rounded-md border hairline border-dashed p-6 text-center text-sm text-muted-foreground">
          <CheckCircle2 className="h-5 w-5 text-emerald-700 mx-auto mb-2" />
          Sin specs legacy. Todos los equipos usan el catálogo estructurado.
        </div>
      )}

      {items.length > 0 && (
        <div className="rounded-md border hairline divide-y hairline overflow-hidden">
          {items.map((it) => (
            <LegacyRow
              key={it.equipo_id}
              item={it}
              onPromover={() => promoverMut.mutate(it.equipo_id)}
              busy={promoverMut.isPending}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function StatCard({
  label, value, tone,
}: {
  label: string;
  value: number;
  tone?: "ok" | "warn";
}) {
  const toneClass =
    tone === "ok" ? "text-emerald-700"
    : tone === "warn" ? "text-amber-700"
    : "text-ink";
  return (
    <div className="rounded-md border hairline p-3">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">
        {label}
      </div>
      <div className={`font-display text-2xl mt-0.5 ${toneClass}`}>{value}</div>
    </div>
  );
}

function LegacyRow({
  item, onPromover, busy,
}: {
  item: {
    equipo_id: number;
    equipo_nombre: string;
    total: number;
    matched: number;
    custom: number;
  };
  onPromover: () => void;
  busy: boolean;
}) {
  return (
    <div className="flex items-center gap-3 px-3 py-2 text-sm hover:bg-muted/20">
      <div className="flex-1 min-w-0">
        <div className="text-ink truncate">
          <span className="text-muted-foreground text-[11px]">#{item.equipo_id}</span>
          {" "}
          {item.equipo_nombre}
        </div>
        <div className="flex items-center gap-2 mt-0.5 text-[11px]">
          <Badge variant="outline" className="text-[10px]">
            {item.total} total
          </Badge>
          {item.matched > 0 && (
            <Badge className="bg-emerald-100 text-emerald-800 text-[10px]">
              {item.matched} matched
            </Badge>
          )}
          {item.custom > 0 && (
            <Badge className="bg-amber-100 text-amber-800 text-[10px]">
              <AlertCircle className="h-2.5 w-2.5 mr-0.5" />
              {item.custom} custom
            </Badge>
          )}
        </div>
      </div>
      <Button
        size="sm"
        disabled={busy || item.matched === 0}
        onClick={onPromover}
        className="h-7 px-2"
        title={item.matched === 0 ? "Sin specs matched para promover" : undefined}
      >
        {busy
          ? <Loader2 className="h-3 w-3 mr-1 animate-spin" />
          : <ArrowUpRight className="h-3 w-3 mr-1" />}
        Promover {item.matched}
      </Button>
    </div>
  );
}
