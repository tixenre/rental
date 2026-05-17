import { createLazyFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import {
  Telescope, RefreshCcw, Loader2, ChevronDown, ChevronRight,
  CheckCircle2, AlertCircle, Download, Cloud,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

import { adminApi } from "@/lib/admin/api";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/specs/observatorio")({
  component: ObservatorioPage,
});

const CATEGORIAS_OBSERVABLES = [
  "Cámaras",
  "Lentes",
  "Iluminación",
  "Modificadores",
  "Soportes",
  "Grip",
  "Sonido",
  "Monitores y Video",
  "Adaptadores y Filtros",
  "Energía",
  "Media y Datos",
];

function ObservatorioPage() {
  useDocumentTitle("Observatorio · Back Office");
  const qc = useQueryClient();
  const [categoria, setCategoria] = useState<string>("__todas");
  const [soloUnmapped, setSoloUnmapped] = useState<boolean>(false);
  const [filtroLabel, setFiltroLabel] = useState<string>("");

  const statsQ = useQuery({
    queryKey: ["admin", "observatorio", "stats"],
    queryFn: () => adminApi.observatorioStats(),
    staleTime: 30_000,
  });

  const agregadoQ = useQuery({
    queryKey: ["admin", "observatorio", "agregado", categoria, soloUnmapped],
    queryFn: () => adminApi.observatorioAgregado({
      categoria: categoria === "__todas" ? null : categoria,
      solo_unmapped: soloUnmapped,
      top_values: 8,
    }),
    staleTime: 30_000,
  });

  const recomputeMut = useMutation({
    mutationFn: () => adminApi.recomputeObservatorio(),
    onSuccess: (data) => {
      toast.success(
        `Procesado: ${data.equipos_procesados} equipos, `
        + `${data.observaciones_insertadas} observaciones, `
        + `${data.labels_unicos} labels únicos`,
      );
      qc.invalidateQueries({ queryKey: ["admin", "observatorio"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  /** Descarga el snapshot completo del observatorio como JSON. Fetcha
   *  stats + agregado SIN filtros (todas las categorías, matched +
   *  unmatched) con top_values=20 para tener data rica. Sirve para
   *  pasarle el snapshot a alguien que no tenga acceso a la UI o para
   *  hacer análisis offline. */
  const [downloading, setDownloading] = useState(false);
  async function downloadSnapshot() {
    if (downloading) return;
    setDownloading(true);
    try {
      const [statsData, agregadoData] = await Promise.all([
        adminApi.observatorioStats(),
        adminApi.observatorioAgregado({ top_values: 20 }),
      ]);
      const snapshot = {
        generated_at: new Date().toISOString(),
        stats: statsData,
        agregado: agregadoData,
      };
      const blob = new Blob([JSON.stringify(snapshot, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
      a.download = `specs-observatorio-${ts}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success(
        `Snapshot descargado: ${agregadoData.total} labels, ${statsData.total_obs} observaciones`,
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falló la descarga");
    } finally {
      setDownloading(false);
    }
  }

  /** Scrapea en cadena los equipos con bh_url pero sin raw_json. Itera
   *  el endpoint batch-enriquecer (max 3 por call, 1s sleep entre cada
   *  scrape). Tarda ~4s por equipo. Al final sugiere recomputar para
   *  procesar los nuevos raw_json. */
  const [scrapeProgress, setScrapeProgress] = useState<
    | { mode: "idle" }
    | { mode: "running"; done: number; total: number; ok: number; failed: number }
  >({ mode: "idle" });

  async function scrapearPendientes() {
    if (scrapeProgress.mode === "running") return;
    let pendientes;
    try {
      pendientes = await adminApi.observatorioScrapeablesPendientes();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falló al listar pendientes");
      return;
    }
    const ids = pendientes.ids;
    if (ids.length === 0) {
      toast.success("No hay equipos pendientes de scrape");
      return;
    }
    if (!window.confirm(
      `Scrapear ${ids.length} equipos contra B&H/Adorama?\n`
      + `Tarda ~${Math.ceil(ids.length * 4 / 60)} min (rate limit 1s entre scrapes).`,
    )) return;

    setScrapeProgress({ mode: "running", done: 0, total: ids.length, ok: 0, failed: 0 });
    let ok = 0;
    let failed = 0;
    let done = 0;

    // Procesar en chunks de 3 (límite del endpoint).
    for (let i = 0; i < ids.length; i += 3) {
      const chunk = ids.slice(i, i + 3);
      try {
        const res = await adminApi.batchEnriquecer(chunk);
        for (const r of res.results) {
          if (r.status === "ok") ok++;
          else failed++;
        }
      } catch {
        failed += chunk.length;
      }
      done += chunk.length;
      setScrapeProgress({ mode: "running", done, total: ids.length, ok, failed });
    }

    setScrapeProgress({ mode: "idle" });
    toast.success(
      `Scrape terminado: ${ok} ok, ${failed} fallaron. Tocá "Recomputar" para refrescar el observatorio.`,
    );
    qc.invalidateQueries({ queryKey: ["admin", "observatorio"] });
  }

  const items = agregadoQ.data?.items ?? [];
  const itemsFiltrados = filtroLabel
    ? items.filter((it) =>
        it.label_observado.toLowerCase().includes(filtroLabel.toLowerCase())
        || it.label_normalizado.includes(filtroLabel.toLowerCase()))
    : items;

  const stats = statsQ.data;

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-6xl mx-auto">
      <header className="flex items-end justify-between gap-3 flex-wrap">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Back-office › Specs
          </div>
          <h1 className="font-display text-3xl text-ink flex items-center gap-2">
            <Telescope className="h-6 w-6 text-amber" />
            Observatorio de specs
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            Relevamiento de specs reales detectados por el scraper B&amp;H/Adorama
            en <code className="font-mono">equipo_fichas.raw_json</code>. Sirve
            para encontrar gaps del template canónico y calibrar enum_options
            con datos reales en vez de suposiciones.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {stats && stats.equipos_scrapeables_pendientes > 0 && (
            <Button
              variant="outline"
              onClick={scrapearPendientes}
              disabled={scrapeProgress.mode === "running"}
              title={`Dispara batch-enriquecer en cadena para los ${stats.equipos_scrapeables_pendientes} equipos con bh_url sin raw_json`}
            >
              {scrapeProgress.mode === "running" ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Scrapeando {scrapeProgress.done}/{scrapeProgress.total}
                  {scrapeProgress.failed > 0 && ` (${scrapeProgress.failed} fail)`}
                </>
              ) : (
                <>
                  <Cloud className="h-4 w-4 mr-2" />
                  Scrapear {stats.equipos_scrapeables_pendientes} pendientes
                </>
              )}
            </Button>
          )}
          <Button
            variant="outline"
            onClick={downloadSnapshot}
            disabled={downloading || !stats || stats.total_obs === 0}
            title={
              !stats || stats.total_obs === 0
                ? "Primero recomputá para tener datos"
                : "Descarga un JSON con stats + agregado completo (sin filtros)"
            }
          >
            {downloading ? (
              <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Descargando…</>
            ) : (
              <><Download className="h-4 w-4 mr-2" /> Descargar JSON</>
            )}
          </Button>
          <Button
            onClick={() => recomputeMut.mutate()}
            disabled={recomputeMut.isPending}
          >
            {recomputeMut.isPending ? (
              <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Recomputando…</>
            ) : (
              <><RefreshCcw className="h-4 w-4 mr-2" /> Recomputar</>
            )}
          </Button>
        </div>
      </header>

      {/* Stats */}
      <section className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
        <StatCard
          label="Observaciones"
          value={stats?.total_obs ?? "—"}
          hint="Total filas en spec_observacion"
        />
        <StatCard
          label="Equipos cubiertos"
          value={stats?.equipos_cubiertos ?? "—"}
          hint={
            stats
              ? `${stats.equipos_con_raw_json}/${stats.equipos_total} con raw_json`
              : undefined
          }
        />
        <StatCard
          label="Pendientes scrape"
          value={stats?.equipos_scrapeables_pendientes ?? "—"}
          hint="Tienen bh_url pero falta scrapear"
          tone={
            stats && stats.equipos_scrapeables_pendientes > 0 ? "warn" : undefined
          }
        />
        <StatCard
          label="Labels únicos"
          value={stats?.labels_unicos ?? "—"}
          hint="Después de normalizar"
        />
        <StatCard
          label="Matched"
          value={stats?.matched_count ?? "—"}
          hint="Coinciden con un spec del catálogo"
          tone="ok"
        />
        <StatCard
          label="Sin template"
          value={stats?.unmatched_count ?? "—"}
          hint="Candidatos a canonizar"
          tone="warn"
        />
      </section>

      {/* Filtros */}
      <section className="flex flex-wrap items-center gap-2 rounded-md border hairline p-3 bg-muted/10">
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-muted-foreground">Categoría</span>
          <Select value={categoria} onValueChange={setCategoria}>
            <SelectTrigger className="h-8 w-44 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__todas">Todas</SelectItem>
              {CATEGORIAS_OBSERVABLES.map((c) => (
                <SelectItem key={c} value={c}>{c}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <label className="flex items-center gap-1.5 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={soloUnmapped}
            onChange={(e) => setSoloUnmapped(e.target.checked)}
            className="h-3.5 w-3.5"
          />
          Solo sin template
        </label>

        <div className="flex-1 min-w-[200px]">
          <Input
            value={filtroLabel}
            onChange={(e) => setFiltroLabel(e.target.value)}
            placeholder="Filtrar por label (ej. Lens mount)…"
            className="h-8 text-sm"
          />
        </div>

        <Badge variant="outline" className="text-[10px]">
          {itemsFiltrados.length} {itemsFiltrados.length === 1 ? "fila" : "filas"}
        </Badge>
      </section>

      {/* Tabla principal */}
      {agregadoQ.isLoading && (
        <div className="rounded-md border hairline px-4 py-6 text-center text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin mx-auto mb-1" />
          Cargando…
        </div>
      )}

      {!agregadoQ.isLoading && itemsFiltrados.length === 0 && (
        <div className="rounded-md border hairline border-dashed p-6 text-center text-sm text-muted-foreground">
          {stats?.total_obs === 0 ? (
            <>
              No hay observaciones todavía. Tocá <strong>Recomputar</strong>{" "}
              para extraer las specs del cache de scrapes
              (<code className="font-mono">equipo_fichas.raw_json</code>).
            </>
          ) : (
            <>Sin filas que matcheen los filtros actuales.</>
          )}
        </div>
      )}

      {itemsFiltrados.length > 0 && (
        <div className="rounded-md border hairline divide-y hairline overflow-hidden">
          {itemsFiltrados.map((it) => (
            <ObservacionRow key={`${it.categoria_raiz}|${it.label_normalizado}`} item={it} />
          ))}
        </div>
      )}
    </div>
  );
}

function StatCard({
  label, value, hint, tone,
}: {
  label: string;
  value: number | string;
  hint?: string;
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
      {hint && (
        <div className="text-[10px] text-muted-foreground mt-0.5">{hint}</div>
      )}
    </div>
  );
}

function ObservacionRow({
  item,
}: {
  item: {
    categoria_raiz: string | null;
    label_observado: string;
    label_normalizado: string;
    equipos_count: number;
    matched_template: boolean;
    spec_def_id: number | null;
    top_values: Array<{ value: string; count: number }>;
  };
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="px-3 py-2 text-sm hover:bg-muted/20">
      <div className="flex items-start gap-2">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="mt-0.5 text-muted-foreground hover:text-ink"
          aria-label={open ? "Cerrar" : "Abrir"}
        >
          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </button>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {item.matched_template ? (
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-700 shrink-0" />
            ) : (
              <AlertCircle className="h-3.5 w-3.5 text-amber-700 shrink-0" />
            )}
            <span className="font-medium text-ink truncate">{item.label_observado}</span>
            {item.categoria_raiz && (
              <Badge variant="outline" className="text-[10px]">
                {item.categoria_raiz}
              </Badge>
            )}
            <span className="text-[11px] text-muted-foreground">
              {item.equipos_count} {item.equipos_count === 1 ? "equipo" : "equipos"}
            </span>
            {item.spec_def_id != null && (
              <Badge variant="secondary" className="text-[10px]">
                def #{item.spec_def_id}
              </Badge>
            )}
          </div>

          {!open && item.top_values.length > 0 && (
            <div className="mt-1 text-[11px] text-muted-foreground truncate">
              {item.top_values.slice(0, 3).map((tv) => `${tv.value} (${tv.count})`).join(" · ")}
              {item.top_values.length > 3 && " · …"}
            </div>
          )}

          {open && (
            <div className="mt-2 space-y-1.5 pl-1">
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">
                Top values
              </div>
              <ul className="space-y-0.5 text-[12px] text-ink">
                {item.top_values.map((tv) => (
                  <li
                    key={tv.value}
                    className="flex items-center justify-between gap-2 rounded px-2 py-1 hover:bg-muted/30"
                  >
                    <code className="font-mono truncate">{tv.value}</code>
                    <Badge variant="outline" className="text-[10px] shrink-0">
                      {tv.count}
                    </Badge>
                  </li>
                ))}
              </ul>
              <div className="text-[10px] text-muted-foreground mt-1">
                Normalizado: <code className="font-mono">{item.label_normalizado}</code>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
