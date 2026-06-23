import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/design-system/ui/alert-dialog";

import { adminApi } from "@/lib/admin/api";
import { formatARS } from "@/lib/format";

type RecalcMode = "missing" | "auto" | "all" | "ids";

export function CambioYPreciosSection() {
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
        dateStyle: "medium",
        timeStyle: "short",
      });
    } catch {
      return s;
    }
  };
  const modeLabel = (m: RecalcMode) =>
    ({
      missing: "Sólo equipos sin precio",
      auto: "Sólo precios automáticos",
      all: "Todos (incluye manuales)",
      ids: "Selección personalizada",
    })[m];

  return (
    <>
      <section className="rounded-lg border hairline bg-background p-4 space-y-3">
        <header>
          <h2 className="font-display text-lg text-ink">Tipo de cambio &amp; precios</h2>
          <p className="text-sm text-muted-foreground">
            Cotización del dólar usada para calcular el precio de jornada en pesos. Actualizalo a
            fin de mes y después aplicá el recálculo masivo.
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
            <p className="mt-1 text-xs text-muted-foreground">
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
              <code className="font-mono text-xs bg-muted/50 px-1 py-0.5 rounded">
                precio_jornada = precio_usd × usd_rate × (roi_pct / 100)
              </code>{" "}
              — redondeado al múltiplo de 100 más cercano.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => dryRunMut.mutate({ mode: "auto" })}
              disabled={dryRunMut.isPending}
              title="Respeta los precios marcados como manuales"
            >
              {dryRunMut.isPending ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                  Calculando…
                </>
              ) : (
                "Sólo automáticos (recomendado)"
              )}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => dryRunMut.mutate({ mode: "missing" })}
              disabled={dryRunMut.isPending}
              title="Sólo equipos que aún no tienen precio cargado"
            >
              Sólo sin precio
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => dryRunMut.mutate({ mode: "all" })}
              disabled={dryRunMut.isPending}
              title="Pisa los precios manuales también — usar con cuidado"
              className="text-destructive hover:text-destructive"
            >
              Todos (pisa manuales)
            </Button>
          </div>
        </div>

        <PreciosManualesPanel onRecalcSelected={(ids) => dryRunMut.mutate({ mode: "ids", ids })} />
      </section>

      <AlertDialog
        open={!!confirmRecalc}
        onOpenChange={(v) => {
          if (!v) setConfirmRecalc(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              ¿Aplicar recálculo a {confirmRecalc?.preview.total_cambios} equipos?
            </AlertDialogTitle>
            <AlertDialogDescription>
              Modo: <strong>{confirmRecalc && modeLabel(confirmRecalc.mode)}</strong>. De{" "}
              {confirmRecalc?.preview.total_evaluados} equipos evaluados,{" "}
              {confirmRecalc?.preview.total_cambios} cambiarían su precio en pesos.
              {confirmRecalc?.mode === "all" && (
                <span className="block mt-2 text-destructive">
                  ⚠️ Vas a pisar también los precios marcados como manuales.
                </span>
              )}{" "}
              Esta acción no se puede deshacer automáticamente.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                confirmRecalc &&
                applyMut.mutate({
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

/** Lista los equipos con precio_jornada_manual=TRUE y muestra qué precio
 *  daría la fórmula con el USD rate actual. Permite seleccionar manualmente
 *  cuáles recalcular (los demás conservan su precio fijado). */
function PreciosManualesPanel({ onRecalcSelected }: { onRecalcSelected: (ids: number[]) => void }) {
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
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const fmtPrecio = (n: number | null) => (n == null ? "—" : formatARS(n));

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
          variant="ghost"
          size="sm"
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
                className="text-xs underline hover:text-ink"
              >
                {selected.size === conDelta.length
                  ? "Deseleccionar todos"
                  : "Seleccionar todos los que cambian"}
              </button>
              <Button
                size="sm"
                className="h-7 text-xs"
                disabled={selected.size === 0}
                onClick={() => onRecalcSelected([...selected])}
              >
                Recalcular {selected.size > 0 ? `(${selected.size})` : ""}
              </Button>
            </div>
          )}
          <table className="w-full text-xs">
            <thead className="text-2xs uppercase tracking-wide text-muted-foreground">
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
                          {" "}
                          — {[it.marca, it.modelo].filter(Boolean).join(" / ")}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums">
                      {fmtPrecio(it.precio_actual)}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground">
                      {fmtPrecio(it.precio_calculado)}
                    </td>
                    <td
                      className={
                        "px-3 py-1.5 text-right tabular-nums " +
                        (cambia
                          ? it.delta! > 0
                            ? "text-verde-ink"
                            : "text-destructive"
                          : "text-muted-foreground")
                      }
                    >
                      {cambia ? `${it.delta! > 0 ? "+" : ""}${fmtPrecio(it.delta).slice(1)}` : "—"}
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
