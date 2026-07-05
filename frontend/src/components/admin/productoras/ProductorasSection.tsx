/**
 * ProductorasSection — CRUD admin de productoras + membership (#1240).
 *
 * Productoras: entidad fiscal compartida entre cuentas de cliente, sin login
 * propio. El admin la crea (verificando el CUIT contra ARCA, bloqueante) y
 * vincula/desvincula cuentas de cliente — sin roles ni invitaciones, el
 * admin es el único que gestiona la membresía.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, RefreshCw, Trash2, Users } from "lucide-react";

import { Input } from "@/design-system/ui/input";
import { Button } from "@/design-system/ui/button";
import { ListSkeleton } from "@/components/admin/skeletons";
import { ErrorState } from "@/components/admin/ErrorState";
import { useConfirm } from "@/components/admin/useConfirm";
import { ClienteAutocomplete } from "@/components/admin/pedido/ClienteAutocomplete";
import { nombreCliente } from "@/lib/cliente-nombre";
import { PERFIL_IMPUESTOS_LABEL } from "@/lib/iva";
import { productorasApi } from "@/lib/admin/api/productoras";
import { cuitValido } from "@/lib/cuit";
import { cn } from "@/lib/utils";

export function ProductorasSection() {
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const listQ = useQuery({
    queryKey: ["admin", "productoras", { q: search }],
    queryFn: () => productorasApi.listar(search.trim() || undefined),
  });

  const [cuit, setCuit] = useState("");
  const [notas, setNotas] = useState("");
  const cuitOk = cuit.trim() === "" || cuitValido(cuit);

  const crearMut = useMutation({
    mutationFn: () => productorasApi.crear(cuit.trim(), notas.trim() || undefined),
    onSuccess: (p) => {
      toast.success(`Productora "${p.razon_social || p.cuit}" verificada y creada`);
      setCuit("");
      setNotas("");
      void qc.invalidateQueries({ queryKey: ["admin", "productoras"] });
      setSelectedId(p.id);
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "AFIP no pudo confirmar este CUIT.");
    },
  });

  const detalleQ = useQuery({
    queryKey: ["admin", "productoras", selectedId, "detalle"],
    queryFn: () => productorasApi.obtener(selectedId!),
    enabled: selectedId != null,
  });

  const reverificarMut = useMutation({
    mutationFn: (id: number) => productorasApi.reverificar(id),
    onSuccess: () => {
      toast.success("Datos refrescados contra ARCA");
      void qc.invalidateQueries({ queryKey: ["admin", "productoras"] });
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "AFIP no pudo confirmar este CUIT.");
    },
  });

  const agregarMiembroMut = useMutation({
    mutationFn: ({ id, clienteId }: { id: number; clienteId: number }) =>
      productorasApi.agregarMiembro(id, clienteId),
    onSuccess: () => {
      toast.success("Cliente vinculado");
      void qc.invalidateQueries({ queryKey: ["admin", "productoras", selectedId, "detalle"] });
    },
    onError: () => toast.error("No se pudo vincular el cliente"),
  });

  const quitarMiembroMut = useMutation({
    mutationFn: ({ id, clienteId }: { id: number; clienteId: number }) =>
      productorasApi.quitarMiembro(id, clienteId),
    onSuccess: () => {
      toast.success("Vínculo eliminado");
      void qc.invalidateQueries({ queryKey: ["admin", "productoras", selectedId, "detalle"] });
    },
    onError: () => toast.error("No se pudo quitar el vínculo"),
  });

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
      <div className="space-y-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!cuitOk || !cuit.trim() || crearMut.isPending) return;
            crearMut.mutate();
          }}
          className="flex flex-wrap items-end gap-2 rounded-md border hairline p-3"
        >
          <div className="flex-1 min-w-[180px]">
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              CUIT de la productora
            </label>
            <Input
              value={cuit}
              onChange={(e) => setCuit(e.target.value.replace(/[^\d-]/g, "").slice(0, 13))}
              placeholder="30-12345678-9"
              aria-invalid={!cuitOk}
              className={cn(!cuitOk && "border-destructive")}
            />
          </div>
          <div className="flex-1 min-w-[180px]">
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Notas (opcional)
            </label>
            <Input
              value={notas}
              onChange={(e) => setNotas(e.target.value)}
              placeholder="Ref: rodaje X"
            />
          </div>
          <Button type="submit" disabled={!cuitOk || !cuit.trim() || crearMut.isPending}>
            <Plus className="mr-1.5 h-4 w-4" />
            {crearMut.isPending ? "Verificando…" : "Verificar y crear"}
          </Button>
        </form>
        {!cuitOk && <p className="text-xs text-destructive">CUIT inválido — revisá el número.</p>}

        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar por razón social o CUIT…"
        />

        {listQ.isLoading && <ListSkeleton rows={4} />}
        {listQ.isError && <ErrorState title="No se pudieron cargar las productoras" />}
        {listQ.data && listQ.data.length === 0 && (
          <div className="rounded-md border border-dashed hairline p-6 text-center text-sm text-muted-foreground">
            Sin productoras todavía.
          </div>
        )}
        <div className="space-y-2">
          {(listQ.data ?? []).map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setSelectedId(p.id)}
              className={cn(
                "flex w-full items-center justify-between gap-3 rounded-md border hairline p-3 text-left transition hover:bg-accent/40",
                selectedId === p.id && "border-ink bg-accent/40",
              )}
            >
              <div>
                <div className="text-sm font-medium text-ink">{p.razon_social || p.cuit}</div>
                <div className="text-xs text-muted-foreground">
                  {p.cuit} · {PERFIL_IMPUESTOS_LABEL[p.perfil_impuestos]}
                </div>
              </div>
              <Users className="h-4 w-4 shrink-0 text-muted-foreground" />
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-md border hairline p-4">
        {selectedId == null ? (
          <p className="text-sm text-muted-foreground">
            Elegí una productora de la lista para ver sus miembros vinculados.
          </p>
        ) : detalleQ.isLoading ? (
          <ListSkeleton rows={3} />
        ) : detalleQ.data ? (
          <div className="space-y-4">
            <div>
              <div className="text-sm font-semibold text-ink">
                {detalleQ.data.razon_social || detalleQ.data.cuit}
              </div>
              <div className="text-xs text-muted-foreground">
                {detalleQ.data.cuit} · {PERFIL_IMPUESTOS_LABEL[detalleQ.data.perfil_impuestos]}
              </div>
              {detalleQ.data.domicilio_fiscal && (
                <div className="text-xs text-muted-foreground">
                  {detalleQ.data.domicilio_fiscal}
                </div>
              )}
              {detalleQ.data.notas && (
                <div className="mt-1 text-xs italic text-muted-foreground">
                  {detalleQ.data.notas}
                </div>
              )}
              <Button
                variant="outline"
                size="sm"
                className="mt-2"
                disabled={reverificarMut.isPending}
                onClick={() => reverificarMut.mutate(detalleQ.data.id)}
              >
                <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
                Reverificar contra ARCA
              </Button>
            </div>

            <div className="border-t hairline pt-3">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Clientes vinculados
              </div>
              {detalleQ.data.miembros.length === 0 && (
                <p className="text-xs text-muted-foreground">Sin clientes vinculados todavía.</p>
              )}
              <div className="space-y-1.5">
                {detalleQ.data.miembros.map((m) => (
                  <div key={m.id} className="flex items-center justify-between gap-2 text-sm">
                    <div>
                      <div className="text-ink">{nombreCliente(m)}</div>
                      <div className="text-xs text-muted-foreground">{m.email}</div>
                    </div>
                    <button
                      type="button"
                      onClick={async () => {
                        if (
                          await confirm({
                            title: "¿Quitar vínculo?",
                            description: `${nombreCliente(m)} ya no va a poder facturar a nombre de esta productora.`,
                          })
                        ) {
                          quitarMiembroMut.mutate({ id: detalleQ.data.id, clienteId: m.id });
                        }
                      }}
                      className="shrink-0 text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
              <ClienteAutocomplete
                className="mt-3"
                placeholder="Vincular cliente…"
                onPick={(c) => agregarMiembroMut.mutate({ id: detalleQ.data.id, clienteId: c.id })}
              />
            </div>
          </div>
        ) : (
          <ErrorState title="No se pudo cargar el detalle" />
        )}
      </div>
    </div>
  );
}
