/**
 * ProductorasSection — CRUD admin de productoras + membership (#1240).
 *
 * Productoras: entidad fiscal compartida entre cuentas de cliente, sin login
 * propio. El admin la crea (verificando el CUIT contra ARCA, bloqueante) y
 * vincula/desvincula cuentas de cliente — sin roles ni invitaciones, el
 * admin es el único que gestiona la membresía.
 */
import { useEffect, useState } from "react";
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
  const [nombre, setNombre] = useState("");
  const cuitOk = cuit.trim() === "" || cuitValido(cuit);
  // CUIT opcional (#1251 Fase 3): sin CUIT crea un borrador, que necesita
  // nombre para ser identificable — con CUIT, el nombre sigue siendo opcional.
  const puedeCrear = cuit.trim() ? cuitOk : nombre.trim() !== "";

  const crearMut = useMutation({
    mutationFn: () =>
      productorasApi.crear(
        cuit.trim() || undefined,
        notas.trim() || undefined,
        nombre.trim() || undefined,
      ),
    onSuccess: (p) => {
      toast.success(
        p.cuit
          ? `Productora "${p.nombre || p.razon_social || p.cuit}" verificada y creada`
          : `Productora borrador "${p.nombre}" creada — asignale un CUIT cuando lo tengas.`,
      );
      setCuit("");
      setNotas("");
      setNombre("");
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

  // Nombre/redes sociales — manuales, se editan sin reverificar contra ARCA
  // (#1251 Fase 2, a diferencia de razón social/domicilio/condición IVA).
  const [editNombre, setEditNombre] = useState("");
  const [editRedes, setEditRedes] = useState("");
  useEffect(() => {
    setEditNombre(detalleQ.data?.nombre ?? "");
    setEditRedes(detalleQ.data?.redes_sociales ?? "");
  }, [detalleQ.data]);

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

  const actualizarMut = useMutation({
    mutationFn: (id: number) =>
      productorasApi.actualizar(id, {
        nombre: editNombre.trim() || undefined,
        redes_sociales: editRedes.trim() || undefined,
      }),
    onSuccess: () => {
      toast.success("Datos actualizados");
      void qc.invalidateQueries({ queryKey: ["admin", "productoras"] });
    },
    onError: () => toast.error("No se pudo actualizar"),
  });

  // Asignar CUIT a un borrador (#1251 Fase 3) — completa la MISMA fila, no
  // crea una productora nueva.
  const [asignarCuit, setAsignarCuit] = useState("");
  const asignarCuitOk = cuitValido(asignarCuit);
  const asignarCuitMut = useMutation({
    mutationFn: (id: number) => productorasApi.actualizar(id, { cuit: asignarCuit.trim() }),
    onSuccess: (p) => {
      toast.success(`CUIT verificado — "${p.nombre || p.razon_social || p.cuit}" ya es facturable`);
      setAsignarCuit("");
      void qc.invalidateQueries({ queryKey: ["admin", "productoras"] });
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "AFIP no pudo confirmar este CUIT.");
    },
  });

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
      <div className="space-y-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!puedeCrear || crearMut.isPending) return;
            crearMut.mutate();
          }}
          className="flex flex-wrap items-end gap-2 rounded-md border hairline p-3"
        >
          <div className="flex-1 min-w-[180px]">
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              CUIT (opcional — sin CUIT queda como borrador)
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
              Nombre {cuit.trim() ? "(opcional)" : ""}
            </label>
            <Input
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="Label amigable — útil si ARCA no da razón social"
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
          <Button type="submit" disabled={!puedeCrear || crearMut.isPending}>
            <Plus className="mr-1.5 h-4 w-4" />
            {crearMut.isPending
              ? "Verificando…"
              : cuit.trim()
                ? "Verificar y crear"
                : "Crear borrador"}
          </Button>
        </form>
        {!cuitOk && <p className="text-xs text-destructive">CUIT inválido — revisá el número.</p>}
        {cuitOk && !cuit.trim() && !nombre.trim() && (
          <p className="text-xs text-muted-foreground">
            Sin CUIT, necesitás al menos un nombre para crear el borrador.
          </p>
        )}

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
                <div className="flex items-center gap-1.5 text-sm font-medium text-ink">
                  {p.nombre || p.razon_social || p.cuit}
                  {!p.cuit && (
                    <span className="rounded-full bg-amber px-1.5 py-0.5 text-2xs font-semibold uppercase tracking-wide text-ink">
                      Borrador
                    </span>
                  )}
                </div>
                <div className="text-xs text-muted-foreground">
                  {p.cuit
                    ? `${p.cuit} · ${PERFIL_IMPUESTOS_LABEL[p.perfil_impuestos!]}`
                    : "Sin CUIT — no facturable todavía"}
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
              <div className="flex items-center gap-1.5 text-sm font-semibold text-ink">
                {detalleQ.data.nombre || detalleQ.data.razon_social || detalleQ.data.cuit}
                {!detalleQ.data.cuit && (
                  <span className="rounded-full bg-amber px-1.5 py-0.5 text-2xs font-semibold uppercase tracking-wide text-ink">
                    Borrador
                  </span>
                )}
              </div>
              {detalleQ.data.nombre && detalleQ.data.razon_social && (
                <div className="text-xs text-muted-foreground">{detalleQ.data.razon_social}</div>
              )}
              <div className="text-xs text-muted-foreground">
                {detalleQ.data.cuit
                  ? `${detalleQ.data.cuit} · ${PERFIL_IMPUESTOS_LABEL[detalleQ.data.perfil_impuestos!]}`
                  : "Sin CUIT — no facturable ni visible en el checkout hasta asignarle uno"}
              </div>
              {detalleQ.data.domicilio_fiscal && (
                <div className="text-xs text-muted-foreground">
                  {detalleQ.data.domicilio_fiscal}
                </div>
              )}
              {detalleQ.data.redes_sociales && (
                <div className="text-xs text-muted-foreground">
                  {detalleQ.data.redes_sociales.startsWith("http") ? (
                    <a
                      href={detalleQ.data.redes_sociales}
                      target="_blank"
                      rel="noreferrer"
                      className="underline hover:text-ink"
                    >
                      {detalleQ.data.redes_sociales}
                    </a>
                  ) : (
                    detalleQ.data.redes_sociales
                  )}
                </div>
              )}
              {detalleQ.data.notas && (
                <div className="mt-1 text-xs italic text-muted-foreground">
                  {detalleQ.data.notas}
                </div>
              )}
              {detalleQ.data.cuit ? (
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
              ) : (
                <div className="mt-2 flex flex-wrap items-end gap-2">
                  <div className="min-w-[160px] flex-1">
                    <label className="mb-1 block text-xs font-medium text-muted-foreground">
                      Asignar CUIT
                    </label>
                    <Input
                      value={asignarCuit}
                      onChange={(e) =>
                        setAsignarCuit(e.target.value.replace(/[^\d-]/g, "").slice(0, 13))
                      }
                      placeholder="30-12345678-9"
                      aria-invalid={asignarCuit.trim() !== "" && !asignarCuitOk}
                      className={cn(
                        asignarCuit.trim() !== "" && !asignarCuitOk && "border-destructive",
                      )}
                    />
                  </div>
                  <Button
                    size="sm"
                    disabled={!asignarCuitOk || asignarCuitMut.isPending}
                    onClick={() => asignarCuitMut.mutate(detalleQ.data.id)}
                  >
                    {asignarCuitMut.isPending ? "Verificando…" : "Verificar y asignar"}
                  </Button>
                </div>
              )}
            </div>

            <div className="space-y-2 border-t hairline pt-3">
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Nombre / redes sociales
              </div>
              <Input
                value={editNombre}
                onChange={(e) => setEditNombre(e.target.value)}
                placeholder="Label amigable"
              />
              <Input
                value={editRedes}
                onChange={(e) => setEditRedes(e.target.value)}
                placeholder="Instagram, sitio web, etc."
              />
              <Button
                size="sm"
                variant="outline"
                disabled={actualizarMut.isPending}
                onClick={() => actualizarMut.mutate(detalleQ.data.id)}
              >
                {actualizarMut.isPending ? "Guardando…" : "Guardar"}
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
