/**
 * ClientesDuplicadosDialog — back-office para fusionar clientes duplicados (Fase 2 #1098).
 *
 * Lista los grupos de clientes que comparten un CUIL verificado (la misma persona) y deja
 * que el admin elija cuál conservar y fusione las demás. Cablea al motor `identity/merge`
 * vía `/api/clientes/merge` (destructivo + transaccional, con guardas en el backend).
 */
import { useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Users, Loader2, ArrowLeftRight, X } from "lucide-react";

import { Button } from "@/design-system/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/design-system/ui/dialog";
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
import { ClienteAvatar } from "@/design-system/ui/ClienteAvatar";
import { ClienteAutocomplete } from "@/components/admin/pedido/ClienteAutocomplete";
import { adminApi, type Cliente, type GrupoDuplicado } from "@/lib/admin/api";
import { nombreCliente } from "@/lib/cliente-nombre";
import { formatFechaDisplay } from "@/lib/format";
import { cn } from "@/lib/utils";

export function ClientesDuplicadosDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const qc = useQueryClient();
  const dupQ = useQuery({
    queryKey: ["admin", "clientes-duplicados"],
    queryFn: () => adminApi.getClientesDuplicados(),
    enabled: open,
  });
  const grupos = dupQ.data ?? [];

  function onMerged() {
    dupQ.refetch();
    qc.invalidateQueries({ queryKey: ["admin", "clientes"] });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Clientes duplicados</DialogTitle>
          <DialogDescription>
            Cuentas que comparten un CUIL verificado (la misma persona). Elegí cuál conservar y
            fusioná las demás: sus pedidos y datos pasan a la que quede, y se borran.
          </DialogDescription>
        </DialogHeader>

        <div className="max-h-[60vh] space-y-4 overflow-y-auto">
          {dupQ.isLoading ? (
            <div className="py-10 text-center text-sm text-muted-foreground">
              Buscando duplicados…
            </div>
          ) : grupos.length === 0 ? (
            <div className="py-6 text-center">
              <Users className="mx-auto mb-2 h-8 w-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                No hay duplicados por CUIL verificado.
              </p>
            </div>
          ) : (
            grupos.map((g) => <GrupoCard key={g.cuil} grupo={g} onMerged={onMerged} />)
          )}

          <FusionManual onMerged={onMerged} />
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** Cuentas de la misma persona que NO comparten un CUIL verificado (ej. una
 * viene de un import legacy sin datos, la otra es la cuenta real con perfil
 * completo) no aparecen en los grupos automáticos de arriba — esta búsqueda
 * manual cubre ese caso, con el mismo motor `/api/clientes/merge`. */
function FusionManual({ onMerged }: { onMerged: () => void }) {
  const [source, setSource] = useState<Cliente | null>(null);
  const [target, setTarget] = useState<Cliente | null>(null);
  const [merging, setMerging] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  async function fusionar() {
    if (!source || !target || merging) return;
    setMerging(true);
    try {
      await adminApi.mergeClientes(source.id, target.id);
      toast.success("Clientes fusionados");
      setSource(null);
      setTarget(null);
      onMerged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo fusionar");
    } finally {
      setMerging(false);
      setConfirmOpen(false);
    }
  }

  return (
    <div className="space-y-2 rounded-lg border hairline p-3">
      <div className="flex items-center gap-1.5 font-mono text-2xs uppercase tracking-wider text-muted-foreground">
        <ArrowLeftRight className="h-3 w-3" /> Fusión manual
      </div>
      <PickerSlot
        label="Se borra"
        cliente={source}
        onClear={() => setSource(null)}
        pick={<ClienteAutocomplete onPick={setSource} placeholder="Buscar cuenta a fusionar…" />}
      />
      <PickerSlot
        label="Queda"
        cliente={target}
        onClear={() => setTarget(null)}
        pick={<ClienteAutocomplete onPick={setTarget} placeholder="Buscar cuenta que conserva…" />}
      />
      <Button
        size="sm"
        variant="destructive"
        disabled={!source || !target || source.id === target.id || merging}
        onClick={() => setConfirmOpen(true)}
        className="w-full"
      >
        {merging ? (
          <>
            <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> Fusionando…
          </>
        ) : (
          "Fusionar"
        )}
      </Button>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Fusionar estas cuentas?</AlertDialogTitle>
            <AlertDialogDescription>
              Se conserva <strong>{target ? nombreCliente(target) : "—"}</strong>.{" "}
              <strong>{source ? nombreCliente(source) : "—"}</strong> se borra y sus pedidos,
              listas y datos pasan a la que queda. Es <strong>irreversible</strong>.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={merging}>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={fusionar} disabled={merging}>
              {merging ? "Fusionando…" : "Fusionar"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function PickerSlot({
  label,
  cliente,
  onClear,
  pick,
}: {
  label: string;
  cliente: Cliente | null;
  onClear: () => void;
  pick: ReactNode;
}) {
  if (!cliente) return pick;
  return (
    <div className="flex items-center gap-3 rounded-md border hairline px-3 py-2">
      <ClienteAvatar nombre={nombreCliente(cliente)} className="h-8 w-8 text-xs" />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm text-ink">
          {cliente.nombre_completo_renaper || nombreCliente(cliente)}
        </div>
        <div className="truncate text-xs text-muted-foreground">
          {[cliente.email, cliente.telefono].filter(Boolean).join(" · ") || "sin contacto"}
        </div>
      </div>
      <span className="shrink-0 text-2xs font-semibold text-muted-foreground">{label}</span>
      <button
        type="button"
        onClick={onClear}
        className="shrink-0 text-muted-foreground hover:text-ink"
        aria-label="Cambiar"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

/** Exportado para reusar en `ClienteDetalleDialog` (#1251 Fase 2) — sugerencia
 * de fusión inline desde la propia ficha, misma UI/lógica que la vista global. */
export function GrupoCard({ grupo, onMerged }: { grupo: GrupoDuplicado; onMerged: () => void }) {
  // Sugerencia por defecto: conservar la cuenta con más pedidos (más historia).
  const sugerido = [...grupo.clientes].sort((a, b) => b.pedidos - a.pedidos)[0]?.id;
  const [target, setTarget] = useState<number>(sugerido);
  const [merging, setMerging] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const sources = grupo.clientes.filter((c) => c.id !== target);
  const targetCliente = grupo.clientes.find((c) => c.id === target);

  async function fusionar() {
    if (merging) return;
    setMerging(true);
    try {
      // El motor es pairwise; un grupo de >2 se fusiona de a una en la sobreviviente.
      for (const c of sources) {
        await adminApi.mergeClientes(c.id, target);
      }
      toast.success(sources.length > 1 ? "Clientes fusionados" : "Cliente fusionado");
      onMerged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo fusionar");
    } finally {
      setMerging(false);
      setConfirmOpen(false);
    }
  }

  return (
    <div className="space-y-2 rounded-lg border hairline p-3">
      <div className="font-mono text-2xs uppercase tracking-wider text-muted-foreground">
        CUIL {grupo.cuil}
      </div>
      {grupo.clientes.map((c) => {
        const keep = c.id === target;
        return (
          <button
            key={c.id}
            type="button"
            onClick={() => setTarget(c.id)}
            className={cn(
              "flex w-full items-center gap-3 rounded-md border px-3 py-2 text-left transition",
              keep ? "border-verde/40 bg-verde/8" : "hairline hover:bg-surface",
            )}
          >
            <ClienteAvatar nombre={nombreCliente(c)} className="h-8 w-8 text-xs" />
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm text-ink">
                {c.nombre_completo_renaper || nombreCliente(c)}
              </div>
              <div className="truncate text-xs text-muted-foreground">
                {c.email || c.telefono || "sin contacto"}
              </div>
            </div>
            <div className="shrink-0 text-right text-2xs text-muted-foreground">
              <div>{c.pedidos} pedidos</div>
              <div>{formatFechaDisplay(c.created_at)}</div>
            </div>
            {keep && (
              <span className="shrink-0 text-2xs font-semibold text-verde-ink">conservar</span>
            )}
          </button>
        );
      })}
      <Button
        size="sm"
        variant="destructive"
        disabled={merging || sources.length === 0}
        onClick={() => setConfirmOpen(true)}
        className="w-full"
      >
        {merging ? (
          <>
            <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> Fusionando…
          </>
        ) : (
          `Fusionar ${sources.length} en la seleccionada`
        )}
      </Button>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Fusionar estos clientes?</AlertDialogTitle>
            <AlertDialogDescription>
              Se conserva <strong>{targetCliente ? nombreCliente(targetCliente) : "—"}</strong>. Las
              otras {sources.length} cuenta{sources.length === 1 ? "" : "s"} se borran y sus
              pedidos, listas y datos pasan a la que queda. Es <strong>irreversible</strong>.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={merging}>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={fusionar} disabled={merging}>
              {merging ? "Fusionando…" : "Fusionar"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
