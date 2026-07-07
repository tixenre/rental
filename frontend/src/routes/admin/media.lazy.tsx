import { createLazyFileRoute } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { RefreshCw, Trash2, RotateCcw, AlertCircle } from "lucide-react";

import { adminApi } from "@/lib/admin/api";
import type { GcResult } from "@/lib/admin/api";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { CardGridSkeleton } from "@/components/admin/skeletons";
import { AdminPage } from "@/components/admin/AdminPage";
import { useConfirm } from "@/components/admin/useConfirm";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { cn } from "@/lib/utils";
import { StatCard } from "@/design-system/composites/StatCard";

export const Route = createLazyFileRoute("/admin/media")({
  component: MediaDashboardPage,
});

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
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
    staleTime: 0,
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
    <AdminPage
      title="Media"
      maxW="detail"
      actions={
        <Button
          variant="ghost"
          size="sm"
          onClick={() => refetch()}
          className="gap-1.5 text-muted-foreground hover:text-ink"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Actualizar
        </Button>
      }
    >
      <div className="space-y-6">
        {/* Stats */}
        {isLoading ? (
          <CardGridSkeleton count={6} />
        ) : stats ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <StatCard label="Assets" value={stats.total_assets} size="md" />
            <StatCard label="Variantes" value={stats.total_variants} size="md" />
            <StatCard label="Almacenamiento" value={formatBytes(stats.total_bytes)} size="md" />
            <StatCard label="Con LQIP" value={stats.assets_with_lqip} size="md" />
            <StatCard
              label="Huérfanos"
              value={stats.orphans}
              size="md"
              tone={stats.orphans > 0 ? "warn" : "default"}
            />
            <StatCard
              label="Sin variantes"
              value={stats.assets_no_variants}
              size="md"
              tone={stats.assets_no_variants > 0 ? "warn" : "default"}
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
            <Button
              variant="outline"
              size="sm"
              onClick={() => gcDryRun.mutate()}
              disabled={isGcRunning}
              className="gap-1.5"
            >
              {gcDryRun.isPending ? (
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <AlertCircle className="h-3.5 w-3.5" />
              )}
              Detectar (dry-run)
            </Button>
            <Button
              variant="destructive"
              size="sm"
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
              className="gap-1.5"
            >
              {gcRun.isPending ? (
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Trash2 className="h-3.5 w-3.5" />
              )}
              Ejecutar GC real
            </Button>
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
    </AdminPage>
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
        <label htmlFor="asset-id" className="t-eyebrow">
          Asset ID
        </label>
        <Input
          id="asset-id"
          type="number"
          min={1}
          value={assetId}
          onChange={(e) => setAssetId(e.target.value)}
          placeholder="ej: 42"
          className="w-32 font-mono"
        />
      </div>
      <Button
        variant="outline"
        onClick={() => mutate()}
        disabled={isPending || !assetId || isNaN(parseInt(assetId, 10))}
        className="gap-1.5 px-3"
      >
        {isPending ? (
          <RefreshCw className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <RotateCcw className="h-3.5 w-3.5" />
        )}
        Re-derivar
      </Button>
      {result && <span className="text-xs text-muted-foreground">{result}</span>}
      {isError && (
        <span className="text-xs text-destructive">
          {error instanceof Error ? error.message : "Error desconocido"}
        </span>
      )}
    </div>
  );
}
