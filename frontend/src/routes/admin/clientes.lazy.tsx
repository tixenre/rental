import { useState } from "react";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { createLazyFileRoute } from "@tanstack/react-router";
import {
  Plus,
  Search,
  Trash2,
  Eye,
  MoreHorizontal,
  ShieldCheck,
  Users,
  UserPlus,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/design-system/ui/table";
import { ActionMenu } from "@/components/mobile";
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

import { adminApi, type Cliente } from "@/lib/admin/api";
import { AdminPage } from "@/components/admin/AdminPage";
import { QueryState } from "@/components/admin/QueryState";
import { TableSkeleton } from "@/components/admin/skeletons";
import { EmptyState } from "@/design-system/composites/EmptyState";
import { ClienteDetalleDialog } from "@/components/admin/ClienteDetalleDialog";
import { ClientesDuplicadosDialog } from "@/components/admin/ClientesDuplicadosDialog";
import { InvitarClienteDialog } from "@/components/admin/InvitarClienteDialog";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { PERFIL_IMPUESTOS_LABEL, type PerfilImpuestos } from "@/lib/iva";

export const Route = createLazyFileRoute("/admin/clientes")({
  component: ClientesPage,
});

function ClientesPage() {
  useDocumentTitle("Clientes · Back Office");
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const debouncedQ = useDebouncedValue(q.trim(), 250);
  const [detalle, setDetalle] = useState<Cliente | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<Cliente | null>(null);
  const [menuCliente, setMenuCliente] = useState<Cliente | null>(null);
  const [showDuplicados, setShowDuplicados] = useState(false);
  const [showInvitar, setShowInvitar] = useState(false);

  const listQ = useQuery({
    queryKey: ["admin", "clientes", { q: debouncedQ }],
    queryFn: () => adminApi.listClientes({ q: debouncedQ || undefined, per_page: 500 }),
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
    <AdminPage
      title="Clientes"
      description={listQ.isLoading ? "Cargando…" : `${total} clientes`}
      actions={
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => setShowDuplicados(true)}>
            <Users className="h-4 w-4 mr-1" /> Duplicados
          </Button>
          <Button variant="outline" onClick={() => setShowInvitar(true)}>
            <UserPlus className="h-4 w-4 mr-1" /> Invitar
          </Button>
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4 mr-1" /> Nuevo cliente
          </Button>
        </div>
      }
    >
      <div className="space-y-6">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar por nombre, apellido, email o CUIT…"
            className="pl-9 text-base sm:text-sm"
          />
        </div>

        <QueryState
          query={listQ}
          isEmpty={(d) => (d.items?.length ?? 0) === 0}
          skeleton={<TableSkeleton rows={6} cols={5} />}
          empty={
            <EmptyState
              icon={<Users className="h-6 w-6" />}
              title="Sin clientes"
              sub="Creá el primero con “Nuevo cliente”."
            />
          }
        >
          {() => (
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
                  {items.map((c) => (
                    <TableRow
                      key={c.id}
                      className="cursor-pointer hover:bg-accent/30"
                      onClick={() => setDetalle(c)}
                    >
                      <TableCell>
                        <div className="flex items-center gap-1.5">
                          <span className="text-ink">{c.nombre_legal}</span>
                          {c.dni_validado_at ? (
                            <ShieldCheck
                              className="h-3.5 w-3.5 shrink-0 text-verde-ink"
                              aria-label="Identidad verificada"
                            />
                          ) : null}
                        </div>
                        {c.perfil_impuestos && (
                          <div className="text-xs text-muted-foreground">
                            {PERFIL_IMPUESTOS_LABEL[c.perfil_impuestos as PerfilImpuestos] ??
                              c.perfil_impuestos}
                          </div>
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
                          aria-label="Más acciones"
                          onClick={() => setMenuCliente(c)}
                        >
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                        {/* Desktop: botones individuales */}
                        <div className="hidden md:inline-flex gap-1">
                          <Button
                            size="icon"
                            variant="ghost"
                            aria-label="Ver / editar cliente"
                            onClick={() => setDetalle(c)}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            aria-label="Eliminar cliente"
                            onClick={() => setDeleting(c)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </QueryState>

        <ActionMenu
          open={!!menuCliente}
          onOpenChange={(v) => {
            if (!v) setMenuCliente(null);
          }}
          title={menuCliente ? menuCliente.nombre_legal : undefined}
          actions={[
            {
              label: "Ver / editar cliente",
              icon: <Eye className="h-4 w-4" />,
              onClick: () => setDetalle(menuCliente!),
            },
            {
              label: "Eliminar",
              icon: <Trash2 className="h-4 w-4" />,
              variant: "destructive",
              onClick: () => setDeleting(menuCliente!),
            },
          ]}
        />

        <ClienteDetalleDialog open={creating} onOpenChange={setCreating} cliente={null} />
        <ClientesDuplicadosDialog open={showDuplicados} onOpenChange={setShowDuplicados} />
        <InvitarClienteDialog open={showInvitar} onOpenChange={setShowInvitar} />
        <ClienteDetalleDialog
          open={!!detalle}
          onOpenChange={(v) => {
            if (!v) setDetalle(null);
          }}
          cliente={detalle}
          onSaved={(c) => setDetalle(c)}
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
                Eliminar a {deleting ? deleting.nombre_legal : ""}
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
    </AdminPage>
  );
}
