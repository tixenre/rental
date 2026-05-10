import { useEffect, useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Upload, Wrench, AlertTriangle, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import { adminApi, type ImportCsvResp, type EtiquetaAdmin } from "@/lib/admin/api";

export const Route = createFileRoute("/admin/settings")({
  component: SettingsPage,
});

type Kind = "equipos" | "clientes" | "alquileres";

function SettingsPage() {
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

      <CategoriasSection />

      <section className="rounded-lg border hairline bg-background p-4 space-y-3">
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
