import { createLazyFileRoute } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Database, RefreshCw, Trash2, RotateCcw, AlertCircle } from "lucide-react";

import { adminApi } from "@/lib/admin/api";
import type { GcResult } from "@/lib/admin/api";
import { useConfirm } from "@/components/admin/useConfirm";
import { useDocumentTitle } from "@/lib/use-document-title";
import { cn } from "@/lib/utils";

export const Route = createLazyFileRoute("/admin/media")({
  component: MediaDashboardPage,
});

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

function StatCard({
  label,
  value,
  warn,
}: {
  label: string;
  value: string | number;
  warn?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border hairline p-4",
        warn ? "border-amber/50 bg-amber/10" : "bg-card",
      )}
    >
      <div className="text-2xl font-mono font-semibold text-ink">{value}</div>
      <div className="text-xs text-muted-foreground mt-1">{label}</div>
    </div>
  );
}

function GcResultView({ result }: { result: GcResult }) {
  return (
    <div
      className={cn(
        "rounded-lg border p-4 text-sm space-y-1",
        result.dry_run
          ? "border-hairline bg-muted/30"
          : result.orphans_purged > 0
            ? "border-muted bg-muted/40"
            : "border-hairline bg-muted/30",
      )}
    >
      <div className="font-medium text-ink">
        {result.dry_run ? "Dry-run (sin borrar)" : "GC ejecutado"}
      </div>
      <div className="text-muted-foreground">
        Huérfanos encontrados: <span className="text-ink font-mono">{result.orphans_found}</span>
        {!result.dry_run && (
          <>
            {" · "}Purgados: <span className="text-ink font-mono">{result.orphans_purged}</span>
            {" · "}Keys R2 borradas:{" "}
            <span className="text-ink font-mono">{result.r2_keys_deleted}</span>
          </>
        )}
      </div>
      {result.errors.length > 0 && (
        <div className="mt-2 rounded border border-destructive/30 bg-destructive/5 p-3 space-y-1">
          <div className="text-xs font-medium text-destructive">Errores:</div>
          {result.errors.map((e, i) => (
            <div key={i} className="text-xs font-mono text-destructive">
              {e}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MediaDashboardPage() {
  useDocumentTitle("Media · Back Office");

  const qc = useQueryClient();
  const confirm = useConfirm();
  const [gcResult, setGcResult] = useState<GcResult | null>(null);

  const {
    data: stats,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["admin", "media", "stats"],
    queryFn: () => adminApi.getStats(),
    staleTime: 60_000,
  });

  const gcDryRun = useMutation({
    mutationFn: () => adminApi.runGc({ dry_run: true }),
    onSuccess: (r) => setGcResult(r),
  });

  const gcRun = useMutation({
    mutationFn: () => adminApi.runGc({ dry_run: false }),
    onSuccess: (r) => {
      setGcResult(r);
      qc.invalidateQueries({ queryKey: ["admin", "media"] });
    },
  });

  const isGcRunning = gcDryRun.isPending || gcRun.isPending;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Database className="h-5 w-5 text-muted-foreground" />
          <h1 className="text-xl font-display font-semibold text-ink">Media</h1>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-ink transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Actualizar
        </button>
      </div>

      {/* Stats */}
      {isLoading ? (
        <div className="text-sm text-muted-foreground animate-pulse">Cargando stats…</div>
      ) : stats ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <StatCard label="Assets" value={stats.total_assets} />
          <StatCard label="Variantes" value={stats.total_variants} />
          <StatCard label="Almacenamiento" value={formatBytes(stats.total_bytes)} />
          <StatCard label="Con LQIP" value={stats.assets_with_lqip} />
          <StatCard label="Huérfanos" value={stats.orphans} warn={stats.orphans > 0} />
          <StatCard
            label="Sin variantes"
            value={stats.assets_no_variants}
            warn={stats.assets_no_variants > 0}
          />
        </div>
      ) : null}

      {/* GC */}
      <section className="space-y-3">
        <h2 className="text-sm font-medium text-ink flex items-center gap-2">
          <Trash2 className="h-4 w-4 text-muted-foreground" />
          Garbage collection
        </h2>
        <p className="text-xs text-muted-foreground">
          Detecta y purga assets de media que no están referenciados por ninguna entidad (equipos,
          estudio, marcas).
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => gcDryRun.mutate()}
            disabled={isGcRunning}
            className={cn(
              "inline-flex items-center gap-1.5 text-xs px-3 py-2 rounded border hairline",
              "hover:bg-muted/60 transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            {gcDryRun.isPending ? (
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <AlertCircle className="h-3.5 w-3.5" />
            )}
            Detectar (dry-run)
          </button>
          <button
            onClick={async () => {
              if (
                await confirm({
                  title: "¿Ejecutar GC real?",
                  description: "Esta acción borra assets y keys de R2.",
                  danger: true,
                  confirmLabel: "Ejecutar",
                })
              ) {
                gcRun.mutate();
              }
            }}
            disabled={isGcRunning}
            className={cn(
              "inline-flex items-center gap-1.5 text-xs px-3 py-2 rounded border",
              "border-destructive/40 text-destructive hover:bg-destructive/5 transition-colors",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            {gcRun.isPending ? (
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Trash2 className="h-3.5 w-3.5" />
            )}
            Ejecutar GC real
          </button>
        </div>

        {gcResult && <GcResultView result={gcResult} />}
      </section>

      {/* Re-derivar */}
      <section className="space-y-3">
        <h2 className="text-sm font-medium text-ink flex items-center gap-2">
          <RotateCcw className="h-4 w-4 text-muted-foreground" />
          Re-derivar variantes
        </h2>
        <p className="text-xs text-muted-foreground">
          Regenera las variantes de un asset desde su original privado en R2. Útil si los derive
          specs cambiaron o una variante quedó corrupta.
        </p>
        <RederiveForm />
      </section>
    </div>
  );
}

function RederiveForm() {
  const qc = useQueryClient();
  const [assetId, setAssetId] = useState("");
  const [result, setResult] = useState<string | null>(null);

  const { mutate, isPending, isError, error } = useMutation({
    mutationFn: () => adminApi.rederive(parseInt(assetId, 10)),
    onSuccess: (r) => {
      setResult(`Asset ${r.asset_id}: ${r.variants_derived} variantes generadas.`);
      qc.invalidateQueries({ queryKey: ["media"] });
    },
  });

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="flex flex-col gap-1">
        <label
          htmlFor="asset-id"
          className="text-2xs font-mono uppercase tracking-widest text-muted-foreground"
        >
          Asset ID
        </label>
        <input
          id="asset-id"
          type="number"
          min={1}
          value={assetId}
          onChange={(e) => setAssetId(e.target.value)}
          placeholder="ej: 42"
          className={cn(
            "h-9 w-32 rounded border hairline px-3 text-sm font-mono",
            "bg-background focus:outline-none focus:ring-1 focus:ring-primary",
          )}
        />
      </div>
      <button
        onClick={() => mutate()}
        disabled={isPending || !assetId || isNaN(parseInt(assetId, 10))}
        className={cn(
          "inline-flex items-center gap-1.5 h-9 text-xs px-3 rounded border hairline",
          "hover:bg-muted/60 transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
        )}
      >
        {isPending ? (
          <RefreshCw className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <RotateCcw className="h-3.5 w-3.5" />
        )}
        Re-derivar
      </button>
      {result && <span className="text-xs text-muted-foreground">{result}</span>}
      {isError && (
        <span className="text-xs text-destructive">
          {error instanceof Error ? error.message : "Error desconocido"}
        </span>
      )}
    </div>
  );
}
