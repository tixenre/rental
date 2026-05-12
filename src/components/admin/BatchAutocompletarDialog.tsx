/**
 * Modal de autocompletar en bulk: toma una lista de equipos con bh_url y para
 * cada uno hace scrape + guarda en cache (raw_json en la ficha). El admin
 * después aplica los campos por sección con los botones ✨ del form V2.
 *
 * El backend procesa max 3 equipos por request (para no timeoutear). El
 * frontend re-batchea hasta terminar todos. Botón "Cancelar" frena el loop.
 *
 * Stats live durante el progreso: procesados, errores, saltados.
 */

import { useRef, useState } from "react";
import { Loader2, Play, Square, AlertCircle, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";

import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

import { adminApi, type Equipo } from "@/lib/admin/api";

type ResultStatus = "ok" | "skipped" | "error";

export function BatchAutocompletarDialog({
  equipos,
  open,
  onOpenChange,
}: {
  /** Lista pre-filtrada (admin ya eligió cuáles procesar). */
  equipos: Equipo[];
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const qc = useQueryClient();
  const [running, setRunning] = useState(false);
  // Cancellation usa ref (no state) para que el closure del loop vea el valor
  // actualizado. Con useState, el closure capturaba el cancelled inicial false.
  const cancelledRef = useRef(false);
  const [progress, setProgress] = useState({ done: 0, ok: 0, skipped: 0, errors: 0 });
  const [log, setLog] = useState<Array<{ id: number; nombre: string; status: ResultStatus; msg: string }>>([]);

  const total = equipos.length;
  const conLink = equipos.filter((e) => e.bh_url);
  const sinLink = total - conLink.length;

  const start = async () => {
    setRunning(true);
    cancelledRef.current = false;
    setProgress({ done: 0, ok: 0, skipped: 0, errors: 0 });
    setLog([]);

    const chunkSize = 3;
    const todo = conLink;
    let done = 0, ok = 0, skipped = 0, errors = 0;

    for (let i = 0; i < todo.length; i += chunkSize) {
      // Chequeo de cancelación al inicio de cada chunk
      if (cancelledRef.current) break;

      const chunk = todo.slice(i, i + chunkSize);
      try {
        const r = await adminApi.batchEnriquecer(chunk.map((e) => e.id));
        for (const res of r.results) {
          const eq = chunk.find((e) => e.id === res.equipo_id);
          if (!eq) continue;
          done++;
          let msg = "";
          if (res.status === "ok") {
            ok++;
            msg = `${res.specs_count ?? 0} specs · llenó: ${(res.filled ?? []).join(", ") || "—"}`;
          } else if (res.status === "skipped") {
            skipped++;
            msg = res.reason ?? "saltado";
          } else {
            errors++;
            msg = res.error ?? "error";
          }
          setLog((prev) => [...prev, { id: eq.id, nombre: eq.nombre, status: res.status, msg }]);
        }
        setProgress({ done, ok, skipped, errors });
      } catch (e) {
        // network error: cuenta TODO el chunk como errores y sigue
        for (const eq of chunk) {
          done++;
          errors++;
          setLog((prev) => [...prev, {
            id: eq.id, nombre: eq.nombre, status: "error",
            msg: e instanceof Error ? e.message : "error de red",
          }]);
        }
        setProgress({ done, ok, skipped, errors });
      }
    }

    setRunning(false);
    qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
    if (cancelledRef.current) {
      toast.info("Batch cancelado");
    } else {
      toast.success(`Listo · ${ok} OK · ${skipped} saltados · ${errors} errores`);
    }
  };

  const stop = () => {
    cancelledRef.current = true;
  };

  // Usar conLink.length (no total) para evitar división por cero cuando
  // hay equipos pero ninguno tiene bh_url.
  const pct = conLink.length > 0 ? Math.round((progress.done / conLink.length) * 100) : 0;

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!running) onOpenChange(v); }}>
      <DialogContent className="w-full sm:max-w-2xl max-h-[92vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display text-xl">Buscar specs en bulk</DialogTitle>
          <p className="text-sm text-muted-foreground">
            Procesa {conLink.length} equipos con link de fuente. El scrape se guarda como cache —
            después aplicás los campos sección por sección con los botones ✨ del form.
          </p>
          {sinLink > 0 && (
            <p className="text-xs text-amber-700 mt-1">
              {sinLink} equipo{sinLink === 1 ? "" : "s"} sin bh_url ({sinLink === 1 ? "será" : "serán"} ignorado{sinLink === 1 ? "" : "s"}).
            </p>
          )}
        </DialogHeader>

        {/* Progress */}
        {(running || progress.done > 0) && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm">
              <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                <div className="h-full bg-amber transition-all" style={{ width: `${pct}%` }} />
              </div>
              <span className="tabular-nums text-xs text-muted-foreground">
                {progress.done}/{conLink.length}
              </span>
            </div>
            <div className="flex gap-3 text-xs">
              <span className="text-green-700">✓ {progress.ok} OK</span>
              <span className="text-muted-foreground">— {progress.skipped} saltados</span>
              <span className="text-destructive">✗ {progress.errors} errores</span>
            </div>
          </div>
        )}

        {/* Log */}
        {log.length > 0 && (
          <div className="max-h-72 overflow-y-auto rounded-md border hairline">
            <div className="divide-y">
              {log.slice().reverse().map((e, i) => (
                <div key={`${e.id}-${i}`} className="flex items-start gap-2 px-2 py-1.5 text-xs">
                  {e.status === "ok" && <CheckCircle2 className="h-3.5 w-3.5 text-green-700 shrink-0 mt-0.5" />}
                  {e.status === "skipped" && <AlertCircle className="h-3.5 w-3.5 text-muted-foreground shrink-0 mt-0.5" />}
                  {e.status === "error" && <AlertCircle className="h-3.5 w-3.5 text-destructive shrink-0 mt-0.5" />}
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate">{e.nombre}</div>
                    <div className="text-muted-foreground truncate">{e.msg}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <DialogFooter>
          {!running && progress.done === 0 && (
            <>
              <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancelar</Button>
              <Button onClick={start} disabled={conLink.length === 0}>
                <Play className="h-3.5 w-3.5 mr-1" />
                Empezar ({conLink.length})
              </Button>
            </>
          )}
          {running && (
            <Button variant="outline" onClick={stop}>
              <Square className="h-3.5 w-3.5 mr-1" /> Detener
            </Button>
          )}
          {!running && progress.done > 0 && (
            <Button onClick={() => onOpenChange(false)}>
              {progress.errors > 0 ? <Loader2 className="h-3.5 w-3.5 mr-1" /> : null}
              Cerrar
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
