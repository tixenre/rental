import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import { Plus, Search, Pencil, Trash2, Eye, MoreHorizontal } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ActionMenu, BottomSheet } from "@/components/mobile";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import { adminApi, ESTADO_LABEL, type Cliente } from "@/lib/admin/api";
import { EstadoBadge } from "@/components/kit/EstadoBadge";
import { ClienteFormDialog } from "@/components/admin/ClienteFormDialog";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/clientes")({
  component: ClientesPage,
});

const fmtArs = (n: number | null | undefined) =>
  n ? `$${Math.round(Number(n)).toLocaleString("es-AR", { maximumFractionDigits: 0 })}` : "$0";

const estadoLabel = (e: string) =>
  e === "presupuesto" ? "Solicitado" : (ESTADO_LABEL[e as keyof typeof ESTADO_LABEL] ?? e);
const fmtFecha = (s: string | null) => (s ? s.slice(0, 10) : "—");

function ClientesPage() {
  useDocumentTitle("Clientes · Back Office");
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState<Cliente | null>(null);
  const [creating, setCreating] = useState(false);
  const [viewing, setViewing] = useState<Cliente | null>(null);
  const [deleting, setDeleting] = useState<Cliente | null>(null);
  const [menuCliente, setMenuCliente] = useState<Cliente | null>(null);

  const listQ = useQuery({
    queryKey: ["admin", "clientes", { q }],
    queryFn: () => adminApi.listClientes({ q: q || undefined, per_page: 500 }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => adminApi.deleteCliente(id),
    onSuccess: () => {
      toast.success("Cliente eliminado");
      setDeleting(null);
      qc.invalidateQueries({ queryKey: ["admin", "clientes"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const items = listQ.data?.items ?? [];
  const total = listQ.data?.total ?? 0;

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-7xl mx-auto">
      <header className="flex flex-col md:flex-row md:items-end md:justify-between gap-3">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Back-office
          </div>
          <h1 className="font-display text-3xl text-ink">Clientes</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {listQ.isLoading ? "Cargando…" : `${total} clientes`}
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4 mr-1" /> Nuevo cliente
        </Button>
      </header>

      <div className="relative">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar por nombre, apellido, email o CUIT…"
          className="pl-9 text-base sm:text-sm"
        />
      </div>

      {listQ.error && (
        <div className="rounded-md border hairline border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          Error: {(listQ.error as Error).message}
        </div>
      )}

      <div className="rounded-lg border hairline overflow-hidden bg-background">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Cliente</TableHead>
              <TableHead className="hidden md:table-cell">Contacto</TableHead>
              <TableHead className="hidden lg:table-cell">CUIT</TableHead>
              <TableHead className="text-right">Desc.</TableHead>
              <TableHead className="text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 && !listQ.isLoading && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground py-10">
                  Sin clientes.
                </TableCell>
              </TableRow>
            )}
            {items.map((c) => (
              <TableRow
                key={c.id}
                className="cursor-pointer hover:bg-accent/30"
                onClick={() => setViewing(c)}
              >
                <TableCell>
                  <div className="text-ink">
                    {[c.apellido, c.nombre].filter(Boolean).join(", ") || c.nombre}
                  </div>
                  {c.perfil_impuestos && (
                    <div className="text-xs text-muted-foreground">{c.perfil_impuestos}</div>
                  )}
                </TableCell>
                <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                  <div>{c.email || "—"}</div>
                  <div>{c.telefono || ""}</div>
                </TableCell>
                <TableCell className="hidden lg:table-cell font-mono text-xs text-muted-foreground">
                  {c.cuit || "—"}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {c.descuento ? `${c.descuento}%` : "—"}
                </TableCell>
                <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                  {/* Mobile: un botón → ActionMenu */}
                  <Button
                    size="icon"
                    variant="ghost"
                    className="md:hidden"
                    onClick={() => setMenuCliente(c)}
                  >
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                  {/* Desktop: botones individuales */}
                  <div className="hidden md:inline-flex gap-1">
                    <Button size="icon" variant="ghost" onClick={() => setViewing(c)}>
                      <Eye className="h-4 w-4" />
                    </Button>
                    <Button size="icon" variant="ghost" onClick={() => setEditing(c)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button size="icon" variant="ghost" onClick={() => setDeleting(c)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <ActionMenu
        open={!!menuCliente}
        onOpenChange={(v) => {
          if (!v) setMenuCliente(null);
        }}
        title={
          menuCliente
            ? [menuCliente.apellido, menuCliente.nombre].filter(Boolean).join(", ") ||
              menuCliente.nombre
            : undefined
        }
        actions={[
          {
            label: "Ver historial",
            icon: <Eye className="h-4 w-4" />,
            onClick: () => setViewing(menuCliente!),
          },
          {
            label: "Editar datos",
            icon: <Pencil className="h-4 w-4" />,
            onClick: () => setEditing(menuCliente!),
          },
          {
            label: "Eliminar",
            icon: <Trash2 className="h-4 w-4" />,
            variant: "destructive",
            onClick: () => setDeleting(menuCliente!),
          },
        ]}
      />

      <ClienteFormDialog open={creating} onOpenChange={setCreating} cliente={null} />
      <ClienteFormDialog
        open={!!editing}
        onOpenChange={(v) => {
          if (!v) setEditing(null);
        }}
        cliente={editing}
      />

      <ClienteHistorialSheet
        cliente={viewing}
        onOpenChange={(v) => {
          if (!v) setViewing(null);
        }}
        onEdit={(c) => {
          setViewing(null);
          setEditing(c);
        }}
      />

      <AlertDialog
        open={!!deleting}
        onOpenChange={(v) => {
          if (!v) setDeleting(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Eliminar a {deleting?.apellido}, {deleting?.nombre}
            </AlertDialogTitle>
            <AlertDialogDescription>
              No se borrarán los pedidos históricos, pero quedarán sin cliente asignado.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleting && deleteMut.mutate(deleting.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function ClienteHistorialSheet({
  cliente,
  onOpenChange,
  onEdit,
}: {
  cliente: Cliente | null;
  onOpenChange: (v: boolean) => void;
  onEdit: (c: Cliente) => void;
}) {
  const navigate = useNavigate();
  const pedidosQ = useQuery({
    queryKey: ["admin", "cliente-pedidos", cliente?.id],
    queryFn: () => adminApi.getClientePedidos(cliente!.id),
    enabled: !!cliente?.id,
  });

  const pedidos = pedidosQ.data ?? [];
  const totalGastado = pedidos.reduce((acc, p) => acc + (p.monto_total ?? 0), 0);

  return (
    <>
      <BottomSheet
        open={!!cliente}
        onOpenChange={onOpenChange}
        title={
          cliente
            ? [cliente.apellido, cliente.nombre].filter(Boolean).join(", ") || cliente.nombre
            : ""
        }
        showClose
        maxH="max-h-[90vh]"
      >
        {cliente && (
          <div className="px-4 pb-6 space-y-4">
            <p className="text-sm text-muted-foreground">
              {cliente.email || cliente.telefono || "Sin contacto registrado"}
            </p>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <Info label="CUIT" value={cliente.cuit || "—"} />
              <Info label="Descuento" value={cliente.descuento ? `${cliente.descuento}%` : "—"} />
              <Info label="Dirección" value={cliente.direccion || "—"} className="col-span-2" />
              <Info label="Perfil" value={cliente.perfil_impuestos || "—"} />
            </div>

            <div className="flex justify-end">
              <Button variant="outline" size="sm" onClick={() => onEdit(cliente)}>
                <Pencil className="h-4 w-4 mr-1" /> Editar datos
              </Button>
            </div>

            <div className="border-t hairline pt-4">
              <div className="flex items-baseline justify-between mb-2">
                <h3 className="font-display text-lg text-ink">Historial de pedidos</h3>
                <div className="font-mono text-xs text-muted-foreground">
                  {pedidos.length} pedidos · {fmtArs(totalGastado)}
                </div>
              </div>

              {pedidosQ.isLoading && <div className="text-sm text-muted-foreground">Cargando…</div>}
              {!pedidosQ.isLoading && pedidos.length === 0 && (
                <div className="text-sm text-muted-foreground">Sin pedidos.</div>
              )}

              <div className="space-y-2">
                {pedidos.map((p) => (
                  <button
                    key={p.id}
                    onClick={() =>
                      navigate({ to: "/admin/pedidos/$id", params: { id: String(p.id) } })
                    }
                    className="w-full text-left rounded-md border hairline p-3 hover:bg-accent/30 transition-colors"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="font-mono text-xs text-muted-foreground">
                        #{p.numero_pedido ?? p.id}
                      </div>
                      <EstadoBadge estado={p.estado} label={estadoLabel(p.estado)} />
                    </div>
                    <div className="text-sm mt-1">
                      {fmtFecha(p.fecha_desde)} → {fmtFecha(p.fecha_hasta)}
                    </div>
                    {p.equipos && (
                      <div className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
                        {p.equipos}
                      </div>
                    )}
                    <div className="flex justify-between mt-1.5 text-sm tabular-nums">
                      <span className="text-muted-foreground">{fmtArs(p.monto_pagado)} pagado</span>
                      <span className="text-ink">{fmtArs(p.monto_total)}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </BottomSheet>
    </>
  );
}

function Info({
  label,
  value,
  className = "",
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className={className}>
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        {label}
      </div>
      <div className="text-ink">{value}</div>
    </div>
  );
}
