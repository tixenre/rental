import { useEffect, useMemo, useRef, useState } from "react";
import { createLazyFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown, ArrowUp, Upload, Wrench, AlertTriangle, Loader2, Image as ImageIcon,
  TrendingUp, TrendingDown, Sparkles, FolderSync, Plus, Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import { adminApi, descuentosJornadaApi, type ImportCsvResp } from "@/lib/admin/api";
import { interpolarDescuento } from "@/lib/api";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/settings")({
  component: SettingsPage,
});

type Kind = "equipos" | "clientes" | "alquileres";

function SettingsPage() {
  useDocumentTitle("Settings · Back Office");
  const [results, setResults] = useState<Record<Kind, ImportCsvResp | null>>({
    equipos: null, clientes: null, alquileres: null,
  });
  const [confirmReset, setConfirmReset] = useState(false);

  const importMut = useMutation({
    mutationFn: ({ kind, file }: { kind: Kind; file: File }) =>
      adminApi.importCsv(kind, file),
    onSuccess: (data, { kind }) => {
      setResults((prev) => ({ ...prev, [kind]: data }));
      const ok = data.success_count ?? data.inserted ?? 0;
      toast.success(`Import ${kind}: ${ok} filas procesadas`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const fixMut = useMutation({
    mutationFn: () => adminApi.fixApellidos(),
    onSuccess: (d) => toast.success(d.message ?? `Apellidos corregidos${d.fixed ? ` (${d.fixed})` : ""}`),
    onError: (e: Error) => toast.error(e.message),
  });

  const resetMut = useMutation({
    mutationFn: () => adminApi.resetClientesDesdeBackup(),
    onSuccess: (d) => {
      toast.success(d.message ?? "Clientes restaurados desde backup");
      setConfirmReset(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-4xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office
        </div>
        <h1 className="font-display text-3xl text-ink">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Importación de datos legacy y herramientas de mantenimiento.
        </p>
      </header>

      <AparienciaSection />

      <DescuentosJornadaSection />

      <CambioYPreciosSection />

      <RankingSection />

      <MigrarStorageSection />

      <section className="rounded-lg border hairline bg-background p-4 space-y-3">
        <h2 className="font-display text-lg text-ink">Imports CSV</h2>
        <p className="text-sm text-muted-foreground">
          Subí archivos CSV exportados desde el sistema viejo o planillas. UTF-8, con headers en la primera fila.
        </p>

        <div className="grid md:grid-cols-3 gap-3">
          <ImportCard
            kind="equipos"
            label="Equipos"
            hint="Headers: nombre, marca, modelo, cantidad, precio_jornada…"
            onPick={(f) => importMut.mutate({ kind: "equipos", file: f })}
            busy={importMut.isPending && importMut.variables?.kind === "equipos"}
            result={results.equipos}
          />
          <ImportCard
            kind="clientes"
            label="Clientes"
            hint="Headers: nombre, apellido, email, telefono, cuit…"
            onPick={(f) => importMut.mutate({ kind: "clientes", file: f })}
            busy={importMut.isPending && importMut.variables?.kind === "clientes"}
            result={results.clientes}
          />
          <ImportCard
            kind="alquileres"
            label="Alquileres"
            hint="Headers: numero_pedido, cliente, fecha_desde, fecha_hasta, items…"
            onPick={(f) => importMut.mutate({ kind: "alquileres", file: f })}
            busy={importMut.isPending && importMut.variables?.kind === "alquileres"}
            result={results.alquileres}
          />
        </div>
      </section>

      <section className="rounded-lg border hairline bg-background p-4 space-y-3">
        <h2 className="font-display text-lg text-ink">Mantenimiento</h2>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-t hairline pt-3">
          <div>
            <div className="text-ink">Corregir apellidos</div>
            <p className="text-xs text-muted-foreground">
              Recorre clientes y separa apellido del nombre cuando vinieron juntos.
            </p>
          </div>
          <Button variant="outline" onClick={() => fixMut.mutate()} disabled={fixMut.isPending}>
            <Wrench className="h-4 w-4 mr-1" />
            {fixMut.isPending ? "Procesando…" : "Ejecutar"}
          </Button>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-t hairline pt-3">
          <div>
            <div className="text-ink flex items-center gap-1.5">
              <AlertTriangle className="h-4 w-4 text-destructive" />
              Restaurar clientes desde backup
            </div>
            <p className="text-xs text-muted-foreground">
              Reemplaza la tabla de clientes por la versión del backup. Destructivo.
            </p>
          </div>
          <Button
            variant="outline"
            className="border-destructive/40 text-destructive hover:bg-destructive/5"
            onClick={() => setConfirmReset(true)}
          >
            Restaurar
          </Button>
        </div>
      </section>

      <AlertDialog open={confirmReset} onOpenChange={setConfirmReset}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Restaurar clientes desde backup?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta acción reemplaza la tabla de clientes actual con la versión guardada en el backup.
              Cualquier cliente nuevo creado después se perderá.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => resetMut.mutate()}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Sí, restaurar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function ImportCard({
  label, hint, onPick, busy, result,
}: {
  kind: Kind;
  label: string;
  hint: string;
  onPick: (file: File) => void;
  busy: boolean;
  result: ImportCsvResp | null;
}) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <div className="rounded-md border hairline p-3 space-y-2">
      <div className="font-display text-base text-ink">{label}</div>
      <p className="text-xs text-muted-foreground min-h-8">{hint}</p>
      <input
        ref={ref}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onPick(f);
          e.target.value = "";
        }}
      />
      <Button
        variant="outline"
        size="sm"
        className="w-full"
        onClick={() => ref.current?.click()}
        disabled={busy}
      >
        <Upload className="h-4 w-4 mr-1" />
        {busy ? "Subiendo…" : "Elegir CSV"}
      </Button>

      {result && (
        <div className="text-xs space-y-1 pt-1 border-t hairline">
          <div className="font-mono text-muted-foreground">
            ✓ {result.success_count ?? result.inserted ?? 0} ok
            {result.skipped ? ` · ${result.skipped} skip` : ""}
            {(result.errors?.length ?? result.error_details?.length) ?
              ` · ${result.errors?.length ?? result.error_details?.length} err` : ""}
          </div>
          {(result.errors ?? result.error_details ?? []).slice(0, 3).map((err, i) => (
            <div key={i} className="text-destructive truncate">{err}</div>
          ))}
        </div>
      )}
    </div>
  );
}


// ── Descuentos por jornadas ─────────────────────────────────────────────────

function DescuentosJornadaSection() {
  const qc = useQueryClient();
  const [dias, setDias] = useState("");
  const [pct, setPct] = useState("");

  const { data: puntos = [], isLoading } = useQuery({
    queryKey: ["descuentos-jornada"],
    queryFn: descuentosJornadaApi.list,
    staleTime: 5 * 60 * 1000,
  });

  const crear = useMutation({
    mutationFn: () => descuentosJornadaApi.create({ jornadas: Number(dias), pct: Number(pct) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["descuentos-jornada"] }); setDias(""); setPct(""); },
    onError: () => toast.error("Error al guardar"),
  });

  const borrar = useMutation({
    mutationFn: (id: number) => descuentosJornadaApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["descuentos-jornada"] }),
    onError: () => toast.error("Error al eliminar"),
  });

  const sorted = [...puntos].sort((a, b) => a.jornadas - b.jornadas);

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-4">
      <div>
        <h2 className="font-display text-lg text-ink">Descuentos por jornadas</h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          Definí puntos ancla. Los valores intermedios se interpolan automáticamente.
        </p>
      </div>

      {/* Tabla de puntos */}
      {isLoading ? (
        <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
      ) : sorted.length === 0 ? (
        <p className="text-sm text-muted-foreground italic">Sin descuentos configurados. Todos los alquileres aplican 0%.</p>
      ) : (
        <div className="border hairline rounded-md overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/40">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground">Jornadas</th>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground">Descuento</th>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground text-xs">Ej. interpol.</th>
                <th className="px-3 py-2 w-10" />
              </tr>
            </thead>
            <tbody className="divide-y hairline">
              {sorted.map((p, i) => {
                const siguiente = sorted[i + 1];
                const medio = siguiente
                  ? Math.round((p.jornadas + siguiente.jornadas) / 2)
                  : null;
                const pctMedio = medio ? interpolarDescuento(sorted, medio) : null;
                return (
                  <tr key={p.id}>
                    <td className="px-3 py-2 tabular-nums font-medium">{p.jornadas} {p.jornadas === 1 ? "día" : "días"}</td>
                    <td className="px-3 py-2 tabular-nums text-emerald-600 font-medium">{p.pct}%</td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {pctMedio !== null ? `${medio} días → ${pctMedio}%` : "—"}
                    </td>
                    <td className="px-3 py-2">
                      <button
                        onClick={() => borrar.mutate(p.id)}
                        className="text-muted-foreground hover:text-destructive"
                        disabled={borrar.isPending}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Agregar punto */}
      <div className="flex items-end gap-2">
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Jornadas</label>
          <Input
            type="number" min="1" value={dias} onChange={(e) => setDias(e.target.value)}
            placeholder="7" className="w-24 h-8 text-sm"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Descuento %</label>
          <Input
            type="number" min="0" max="100" step="0.5" value={pct} onChange={(e) => setPct(e.target.value)}
            placeholder="10" className="w-24 h-8 text-sm"
          />
        </div>
        <Button
          size="sm" variant="outline"
          onClick={() => crear.mutate()}
          disabled={!dias || !pct || crear.isPending}
        >
          {crear.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
          Agregar
        </Button>
      </div>
    </section>
  );
}


// ── Apariencia (logo del sitio) ─────────────────────────────────────────────

function AparienciaSection() {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: settings } = useQuery({
    queryKey: ["admin", "settings"],
    queryFn: () => adminApi.listSettings(),
  });

  const logoUrl = settings?.items.find((s) => s.key === "logo_url")?.value ?? null;

  const uploadMut = useMutation({
    mutationFn: (file: File) => adminApi.uploadLogo(file),
    onSuccess: () => {
      toast.success("Logo actualizado");
      qc.invalidateQueries({ queryKey: ["admin", "settings"] });
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function handleFile(file: File) {
    if (!file.type.startsWith("image/")) {
      toast.error("Solo se admiten imágenes");
      return;
    }
    uploadMut.mutate(file);
  }

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <h2 className="font-display text-lg text-ink flex items-center gap-2">
        <ImageIcon className="h-4 w-4 text-muted-foreground" />
        Apariencia
      </h2>

      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex-shrink-0 w-32 h-16 rounded-md border hairline bg-muted flex items-center justify-center overflow-hidden">
          {logoUrl ? (
            <img src={logoUrl} alt="Logo actual" className="object-contain w-full h-full p-2" />
          ) : (
            <span className="text-xs text-muted-foreground">Sin logo</span>
          )}
        </div>

        <div className="space-y-1.5">
          <p className="text-sm text-muted-foreground">
            PNG, SVG o WebP recomendado. Máx 5 MB. Se optimiza automáticamente.
          </p>
          <Button
            size="sm"
            variant="outline"
            onClick={() => inputRef.current?.click()}
            disabled={uploadMut.isPending}
          >
            {uploadMut.isPending ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Upload className="h-4 w-4 mr-2" />
            )}
            {uploadMut.isPending ? "Subiendo…" : "Subir logo"}
          </Button>
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
              e.target.value = "";
            }}
          />
        </div>
      </div>
    </section>
  );
}

// ── Ranking automático de equipos ───────────────────────────────────────────

function RankingSection() {
  const qc = useQueryClient();
  const [reporte, setReporte] = useState<Awaited<ReturnType<typeof adminApi.recalcularRanking>> | null>(null);

  const recalcMut = useMutation({
    mutationFn: (dry_run: boolean) =>
      adminApi.recalcularRanking({ dry_run, ventana_dias: 180 }),
    onSuccess: (data) => {
      setReporte(data);
      if (!data.dry_run) {
        toast.success(`Ranking recalculado · ${data.cambios.length} equipos actualizados`);
        qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
        qc.invalidateQueries({ queryKey: ["equipos"] });
      } else {
        toast.message(`Preview: ${data.cambios.length} equipos cambiarían (dry-run)`);
      }
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-amber" /> Ranking automático
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Calcula la prioridad de cada equipo en el catálogo basándose en
          el histórico de pedidos e ingresos de los últimos 180 días.
          Normalizado por categoría (los equipos compiten contra sus pares,
          no contra todo el inventario).
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-2 pt-2">
        <Button
          variant="outline"
          onClick={() => recalcMut.mutate(true)}
          disabled={recalcMut.isPending}
        >
          {recalcMut.isPending && recalcMut.variables ? (
            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
          ) : null}
          Ver preview (dry-run)
        </Button>
        <Button
          onClick={() => recalcMut.mutate(false)}
          disabled={recalcMut.isPending}
        >
          {recalcMut.isPending && !recalcMut.variables ? (
            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
          ) : null}
          Recalcular y aplicar
        </Button>
      </div>

      {reporte && (
        <div className="mt-3 space-y-2 rounded-md border hairline bg-muted/30 p-3">
          <div className="text-xs">
            <span className="font-medium text-ink">
              {reporte.dry_run ? "Preview (dry-run): " : "Aplicado: "}
            </span>
            <span className="text-muted-foreground">
              {reporte.cambios.length} equipos {reporte.dry_run ? "cambiarían" : "actualizados"},
              {" "}{reporte.sin_cambios} sin cambios. Ventana: {reporte.ventana_dias} días.
            </span>
          </div>
          {reporte.cambios.length > 0 && (
            <div className="space-y-1 max-h-80 overflow-y-auto">
              {reporte.cambios
                .slice()
                .sort((a, b) => (b.despues.score - b.antes.score) - (a.despues.score - a.antes.score))
                .slice(0, 20)
                .map((c) => {
                  const delta = c.despues.score - c.antes.score;
                  return (
                    <div key={c.id} className="flex items-center justify-between gap-2 text-xs py-1 border-b hairline last:border-0">
                      <span className="text-ink truncate flex-1">{c.nombre}</span>
                      <span className="text-muted-foreground tabular shrink-0">
                        {c.antes.score} → {c.despues.score}
                      </span>
                      <span className={`tabular shrink-0 inline-flex items-center gap-0.5 ${delta > 0 ? "text-green-600" : delta < 0 ? "text-destructive" : "text-muted-foreground"}`}>
                        {delta > 0 ? <TrendingUp className="h-3 w-3" /> : delta < 0 ? <TrendingDown className="h-3 w-3" /> : null}
                        {delta > 0 ? "+" : ""}{delta}
                      </span>
                    </div>
                  );
                })}
              {reporte.cambios.length > 20 && (
                <div className="text-xs text-muted-foreground pt-1">
                  …y {reporte.cambios.length - 20} más.
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

// ── Cambio (USD/ARS) y recálculo masivo de precios ─────────────────────────

type RecalcMode = "missing" | "auto" | "all" | "ids";

function CambioYPreciosSection() {
  const qc = useQueryClient();
  const [valor, setValor] = useState("");
  const [confirmRecalc, setConfirmRecalc] = useState<{
    mode: RecalcMode;
    ids?: number[];
    preview: { total_cambios: number; total_evaluados: number };
  } | null>(null);

  const settingQ = useQuery({
    queryKey: ["settings", "usd_rate"],
    queryFn: () => adminApi.getSetting("usd_rate"),
    staleTime: 60_000,
  });

  // Cargar el valor actual cuando llega de la red.
  useEffect(() => {
    if (settingQ.data && !valor) setValor(settingQ.data.value);
  }, [settingQ.data, valor]);

  const updateMut = useMutation({
    mutationFn: (v: string) => adminApi.updateSetting("usd_rate", v),
    onSuccess: () => {
      toast.success("Tipo de cambio actualizado");
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const dryRunMut = useMutation({
    mutationFn: (args: { mode: RecalcMode; ids?: number[] }) =>
      adminApi.recalcularPrecios({ dry_run: true, ...args }).then((r) => ({ ...r, ...args })),
    onSuccess: (r) => {
      if (r.total_cambios === 0) {
        toast.info("Nada para recalcular — todos los precios ya están en sincro.");
        return;
      }
      setConfirmRecalc({
        mode: r.mode,
        ids: r.ids,
        preview: { total_cambios: r.total_cambios, total_evaluados: r.total_evaluados },
      });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const applyMut = useMutation({
    mutationFn: (args: { mode: RecalcMode; ids?: number[] }) =>
      adminApi.recalcularPrecios({ dry_run: false, ...args }),
    onSuccess: (r) => {
      toast.success(`${r.total_cambios} precios actualizados`);
      qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
      qc.invalidateQueries({ queryKey: ["equipos"] });
      qc.invalidateQueries({ queryKey: ["admin", "precios-manuales"] });
      setConfirmRecalc(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const dirty = valor.trim() !== (settingQ.data?.value ?? "");
  const fmtFecha = (s: string | null) => {
    if (!s) return "—";
    try {
      return new Date(s).toLocaleString("es-AR", {
        dateStyle: "medium", timeStyle: "short",
      });
    } catch {
      return s;
    }
  };
  const modeLabel = (m: RecalcMode) => ({
    missing: "Sólo equipos sin precio",
    auto: "Sólo precios automáticos",
    all: "Todos (incluye manuales)",
    ids: "Selección personalizada",
  }[m]);

  return (
    <>
      <section className="rounded-lg border hairline bg-background p-4 space-y-3">
        <header>
          <h2 className="font-display text-lg text-ink">Tipo de cambio &amp; precios</h2>
          <p className="text-sm text-muted-foreground">
            Cotización del dólar usada para calcular el precio de jornada en pesos.
            Actualizalo a fin de mes y después aplicá el recálculo masivo.
          </p>
        </header>

        <div className="flex flex-col sm:flex-row sm:items-end gap-3 border-t hairline pt-3">
          <div className="flex-1">
            <label className="text-xs uppercase tracking-wide text-muted-foreground">
              ARS por 1 USD
            </label>
            <Input
              type="number"
              min={0}
              step="0.01"
              value={valor}
              onChange={(e) => setValor(e.target.value)}
              placeholder="1200"
              className="mt-1"
            />
            <p className="mt-1 text-[11px] text-muted-foreground">
              Última actualización: {fmtFecha(settingQ.data?.updated_at ?? null)}
              {settingQ.data?.updated_by && ` · ${settingQ.data.updated_by}`}
            </p>
          </div>
          <Button
            onClick={() => updateMut.mutate(valor)}
            disabled={!dirty || updateMut.isPending || !valor.trim()}
          >
            {updateMut.isPending ? "Guardando…" : "Guardar"}
          </Button>
        </div>

        <div className="border-t hairline pt-3 space-y-2">
          <div>
            <div className="text-ink font-medium">Recalcular precios</div>
            <p className="text-xs text-muted-foreground">
              <code className="font-mono text-[11px] bg-muted/50 px-1 py-0.5 rounded">
                precio_jornada = precio_usd × usd_rate × (roi_pct / 100)
              </code>
              {" "}— redondeado al múltiplo de 100 más cercano.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline" size="sm"
              onClick={() => dryRunMut.mutate({ mode: "auto" })}
              disabled={dryRunMut.isPending}
              title="Respeta los precios marcados como manuales"
            >
              {dryRunMut.isPending ? (
                <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Calculando…</>
              ) : (
                "Sólo automáticos (recomendado)"
              )}
            </Button>
            <Button
              variant="ghost" size="sm"
              onClick={() => dryRunMut.mutate({ mode: "missing" })}
              disabled={dryRunMut.isPending}
              title="Sólo equipos que aún no tienen precio cargado"
            >
              Sólo sin precio
            </Button>
            <Button
              variant="ghost" size="sm"
              onClick={() => dryRunMut.mutate({ mode: "all" })}
              disabled={dryRunMut.isPending}
              title="Pisa los precios manuales también — usar con cuidado"
              className="text-destructive hover:text-destructive"
            >
              Todos (pisa manuales)
            </Button>
          </div>
        </div>

        <PreciosManualesPanel
          onRecalcSelected={(ids) => dryRunMut.mutate({ mode: "ids", ids })}
        />
      </section>

      <AlertDialog open={!!confirmRecalc} onOpenChange={(v) => { if (!v) setConfirmRecalc(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              ¿Aplicar recálculo a {confirmRecalc?.preview.total_cambios} equipos?
            </AlertDialogTitle>
            <AlertDialogDescription>
              Modo: <strong>{confirmRecalc && modeLabel(confirmRecalc.mode)}</strong>.
              {" "}De {confirmRecalc?.preview.total_evaluados} equipos evaluados,
              {" "}{confirmRecalc?.preview.total_cambios} cambiarían su precio en pesos.
              {confirmRecalc?.mode === "all" && (
                <span className="block mt-2 text-destructive">
                  ⚠️ Vas a pisar también los precios marcados como manuales.
                </span>
              )}
              {" "}Esta acción no se puede deshacer automáticamente.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                confirmRecalc && applyMut.mutate({
                  mode: confirmRecalc.mode,
                  ids: confirmRecalc.ids,
                })
              }
              disabled={applyMut.isPending}
            >
              {applyMut.isPending ? "Aplicando…" : "Sí, aplicar"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}


// ── Migración de paths R2 ───────────────────────────────────────────────────

function MigrarStorageSection() {
  type MigrateResult = Awaited<ReturnType<typeof adminApi.migrarStoragePaths>>;
  const [preview, setPreview] = useState<MigrateResult | null>(null);
  const [applied, setApplied] = useState<MigrateResult | null>(null);

  const previewMut = useMutation({
    mutationFn: () => adminApi.migrarStoragePaths(true),
    onSuccess: (data) => {
      setPreview(data);
      setApplied(null);
      if ((data.to_rename ?? 0) === 0) {
        toast.info("Todas las fotos ya tienen el formato correcto.");
      }
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const applyMut = useMutation({
    mutationFn: () => adminApi.migrarStoragePaths(false),
    onSuccess: (data) => {
      setApplied(data);
      setPreview(null);
      toast.success(`${data.moved ?? 0} fotos renombradas${data.errors ? ` · ${data.errors} errores` : ""}`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const busy = previewMut.isPending || applyMut.isPending;
  const toRename = preview?.to_rename ?? 0;

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink flex items-center gap-2">
          <FolderSync className="h-4 w-4 text-muted-foreground" />
          Migrar fotos R2
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Renombra las carpetas y archivos de fotos al nuevo esquema{" "}
          <code className="font-mono text-[11px] bg-muted/50 px-1 py-0.5 rounded">
            id_slug/id_slug.ext
          </code>
          . Actualizá el deploy primero, luego ejecutá esto una sola vez.
        </p>
      </div>

      <div className="flex flex-wrap gap-2 pt-1">
        <Button variant="outline" onClick={() => previewMut.mutate()} disabled={busy}>
          {previewMut.isPending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
          Ver preview
        </Button>
        {toRename > 0 && !applied && (
          <Button onClick={() => applyMut.mutate()} disabled={busy}>
            {applyMut.isPending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
            Renombrar {toRename} fotos
          </Button>
        )}
      </div>

      {preview && toRename > 0 && (
        <div className="rounded-md border hairline bg-muted/20 p-3 space-y-2">
          <p className="text-xs text-muted-foreground">
            <strong className="text-ink">{toRename}</strong> fotos para renombrar:
          </p>
          <div className="max-h-48 overflow-y-auto space-y-1">
            {(preview.detail ?? []).slice(0, 30).map((r, i) => (
              <div key={i} className="font-mono text-[11px] text-muted-foreground leading-tight">
                <span className="line-through">{r.old}</span>
                <span className="text-ink"> → {r.new}</span>
              </div>
            ))}
            {toRename > 30 && (
              <p className="text-xs text-muted-foreground">…y {toRename - 30} más.</p>
            )}
          </div>
        </div>
      )}

      {applied && (
        <div className="rounded-md border hairline bg-muted/20 p-3 text-sm space-y-1">
          <p className="text-ink font-medium">Migración completa</p>
          <p className="text-xs text-muted-foreground">
            {applied.moved ?? 0} fotos movidas · {applied.db_updated ?? 0} URLs actualizadas en BD
            {(applied.errors ?? 0) > 0 && (
              <span className="text-destructive"> · {applied.errors} errores</span>
            )}
          </p>
          {(applied.error_detail ?? []).map((e, i) => (
            <p key={i} className="text-xs text-destructive font-mono truncate">{e.key}: {e.error}</p>
          ))}
        </div>
      )}
    </section>
  );
}

/** Lista los equipos con precio_jornada_manual=TRUE y muestra qué precio
 *  daría la fórmula con el USD rate actual. Permite seleccionar manualmente
 *  cuáles recalcular (los demás conservan su precio fijado). */
function PreciosManualesPanel({
  onRecalcSelected,
}: {
  onRecalcSelected: (ids: number[]) => void;
}) {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [expanded, setExpanded] = useState(false);

  const manualesQ = useQuery({
    queryKey: ["admin", "precios-manuales"],
    queryFn: () => adminApi.listarPreciosManuales(),
    staleTime: 30_000,
  });

  const items = manualesQ.data?.items ?? [];
  const conDelta = items.filter((i) => i.delta != null && i.delta !== 0);

  if (manualesQ.isLoading) {
    return (
      <div className="border-t hairline pt-3 text-xs text-muted-foreground">
        Cargando precios manuales…
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="border-t hairline pt-3 text-xs text-muted-foreground">
        No hay equipos con precio fijado manualmente.
      </div>
    );
  }

  const toggleAll = () => {
    if (selected.size === conDelta.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(conDelta.map((i) => i.id)));
    }
  };

  const toggleOne = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const fmtPrecio = (n: number | null) =>
    n == null ? "—" : `$${Math.round(n).toLocaleString("es-AR", { maximumFractionDigits: 0 })}`;

  return (
    <div className="border-t hairline pt-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="text-ink font-medium text-sm">
            Precios manuales — revisión equipo por equipo
          </div>
          <p className="text-xs text-muted-foreground">
            {items.length} equipos con precio fijado a mano.{" "}
            {conDelta.length > 0
              ? `${conDelta.length} cambiarían con el USD actual.`
              : "Todos coinciden con la fórmula actual."}
          </p>
        </div>
        <Button
          variant="ghost" size="sm"
          onClick={() => setExpanded((e) => !e)}
          className="shrink-0 h-7 text-xs"
        >
          {expanded ? "Ocultar" : "Revisar"}
        </Button>
      </div>

      {expanded && (
        <div className="rounded-md border hairline bg-muted/20 max-h-96 overflow-y-auto">
          {conDelta.length > 0 && (
            <div className="sticky top-0 z-10 flex items-center justify-between gap-2 px-3 py-2 border-b hairline bg-background/95 backdrop-blur">
              <button
                type="button"
                onClick={toggleAll}
                className="text-[11px] underline hover:text-ink"
              >
                {selected.size === conDelta.length ? "Deseleccionar todos" : "Seleccionar todos los que cambian"}
              </button>
              <Button
                size="sm" className="h-7 text-xs"
                disabled={selected.size === 0}
                onClick={() => onRecalcSelected([...selected])}
              >
                Recalcular {selected.size > 0 ? `(${selected.size})` : ""}
              </Button>
            </div>
          )}
          <table className="w-full text-xs">
            <thead className="text-[10px] uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="text-left px-3 py-1.5 w-8"></th>
                <th className="text-left px-3 py-1.5">Equipo</th>
                <th className="text-right px-3 py-1.5">Actual</th>
                <th className="text-right px-3 py-1.5">Si recalcula</th>
                <th className="text-right px-3 py-1.5">Δ</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => {
                const cambia = it.delta != null && it.delta !== 0;
                return (
                  <tr key={it.id} className="border-t hairline">
                    <td className="px-3 py-1.5">
                      <input
                        type="checkbox"
                        checked={selected.has(it.id)}
                        disabled={!cambia}
                        onChange={() => toggleOne(it.id)}
                        className="cursor-pointer"
                      />
                    </td>
                    <td className="px-3 py-1.5 text-ink">
                      {it.nombre}
                      {(it.marca || it.modelo) && (
                        <span className="text-muted-foreground">
                          {" "}— {[it.marca, it.modelo].filter(Boolean).join(" / ")}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums">
                      {fmtPrecio(it.precio_actual)}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground">
                      {fmtPrecio(it.precio_calculado)}
                    </td>
                    <td className={
                      "px-3 py-1.5 text-right tabular-nums " +
                      (cambia ? (it.delta! > 0 ? "text-emerald-600" : "text-destructive") : "text-muted-foreground")
                    }>
                      {cambia
                        ? `${it.delta! > 0 ? "+" : ""}${fmtPrecio(it.delta).slice(1)}`
                        : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

