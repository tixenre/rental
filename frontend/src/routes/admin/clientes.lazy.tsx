import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import {
  Plus,
  Search,
  Pencil,
  Trash2,
  Eye,
  MoreHorizontal,
  ShieldCheck,
  ShieldAlert,
  Copy,
  Check,
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
} from "@/design-system/ui/alert-dialog";

import { adminApi, ESTADO_LABEL, type Cliente } from "@/lib/admin/api";
import { EstadoBadge } from "@/design-system/ui/EstadoBadge";
import { AdminPage } from "@/components/admin/AdminPage";
import { QueryState } from "@/components/admin/QueryState";
import { TableSkeleton } from "@/components/admin/skeletons";
import { EmptyState } from "@/design-system/composites/EmptyState";
import { ClienteFormDialog } from "@/components/admin/ClienteFormDialog";
import { ClientesDuplicadosDialog } from "@/components/admin/ClientesDuplicadosDialog";
import { InvitarClienteDialog } from "@/components/admin/InvitarClienteDialog";
import { useDocumentTitle } from "@/lib/use-document-title";
import { AuthedHttpError } from "@/lib/authedFetch";
import { fmtArs, formatFechaDisplay } from "@/lib/format";
import { nombreCliente } from "@/lib/cliente-nombre";
import { PERFIL_IMPUESTOS_LABEL, type PerfilImpuestos } from "@/lib/iva";

export const Route = createLazyFileRoute("/admin/clientes")({
  component: ClientesPage,
});

const estadoLabel = (e: string) =>
  e === "presupuesto" ? "Solicitado" : (ESTADO_LABEL[e as keyof typeof ESTADO_LABEL] ?? e);
const fmtFecha = (s: string | null) => formatFechaDisplay(s);

function ClientesPage() {
  useDocumentTitle("Clientes · Back Office");
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  // Debounce real (mismo patrón que el selector de clientes del pedido): cada
  // tecla cancela el timer anterior → una sola búsqueda al frenar, no por tecla.
  const [debouncedQ, setDebouncedQ] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q.trim()), 250);
    return () => clearTimeout(t);
  }, [q]);
  const [editing, setEditing] = useState<Cliente | null>(null);
  const [creating, setCreating] = useState(false);
  const [viewing, setViewing] = useState<Cliente | null>(null);
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
                      onClick={() => setViewing(c)}
                    >
                      <TableCell>
                        <div className="flex items-center gap-1.5">
                          <span className="text-ink">{nombreCliente(c)}</span>
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
                            aria-label="Ver historial"
                            onClick={() => setViewing(c)}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            aria-label="Editar datos"
                            onClick={() => setEditing(c)}
                          >
                            <Pencil className="h-4 w-4" />
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
          title={menuCliente ? nombreCliente(menuCliente) : undefined}
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
        <ClientesDuplicadosDialog open={showDuplicados} onOpenChange={setShowDuplicados} />
        <InvitarClienteDialog open={showInvitar} onOpenChange={setShowInvitar} />
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
          onUpdated={(c) => setViewing(c)}
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
                Eliminar a {deleting ? nombreCliente(deleting) : ""}
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

function ClienteHistorialSheet({
  cliente,
  onOpenChange,
  onEdit,
  onUpdated,
}: {
  cliente: Cliente | null;
  onOpenChange: (v: boolean) => void;
  onEdit: (c: Cliente) => void;
  onUpdated: (c: Cliente) => void;
}) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [linkVerif, setLinkVerif] = useState<string | null>(null);
  const [generando, setGenerando] = useState(false);
  const [copiado, setCopiado] = useState(false);
  const [rechequeando, setRechequeando] = useState(false);

  useEffect(() => {
    setLinkVerif(null);
    setCopiado(false);
  }, [cliente?.id]);

  async function rechequearVerificacion() {
    if (!cliente) return;
    setRechequeando(true);
    try {
      const r = await adminApi.rechequearVerificacion(cliente.id);
      const actualizado = await adminApi.getCliente(cliente.id);
      onUpdated(actualizado);
      qc.invalidateQueries({ queryKey: ["admin", "clientes"] });
      if (actualizado.dni_validado_at) {
        toast.success("Didit ya lo tiene aprobado — identidad verificada.");
      } else if (r.status === "Declined") {
        toast.error("Didit lo sigue mostrando rechazado.");
      } else {
        toast.message(`Didit responde: ${r.status || "sin novedades"}.`);
      }
    } catch (err) {
      toast.error(
        err instanceof AuthedHttpError && err.status === 409
          ? "Este cliente todavía no inició una verificación con Didit."
          : "No se pudo re-chequear con Didit",
      );
    } finally {
      setRechequeando(false);
    }
  }

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
        title={cliente ? nombreCliente(cliente) : ""}
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

            {/* Identidad Didit */}
            {cliente.dni_validado_at ? (
              <div className="rounded-lg border border-verde/30 bg-verde/8 px-3 py-2.5 space-y-1.5">
                <div className="flex items-center gap-1.5 text-verde-ink text-sm font-semibold">
                  <ShieldCheck className="h-4 w-4 shrink-0" />
                  Identidad verificada
                </div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-ink">
                  {(cliente.nombre_completo_renaper || cliente.nombre_renaper) && (
                    <div className="col-span-2">
                      <span className="text-muted-foreground">Nombre legal: </span>
                      {cliente.nombre_completo_renaper ||
                        `${cliente.nombre_renaper ?? ""} ${cliente.apellido_renaper ?? ""}`.trim()}
                    </div>
                  )}
                  {cliente.dni && (
                    <div>
                      <span className="text-muted-foreground">DNI: </span>
                      <span className="font-mono">{cliente.dni}</span>
                    </div>
                  )}
                  {cliente.cuil && (
                    <div>
                      <span className="text-muted-foreground">CUIL: </span>
                      <span className="font-mono">{cliente.cuil}</span>
                    </div>
                  )}
                  {cliente.fecha_nacimiento_renaper && (
                    <div>
                      <span className="text-muted-foreground">Nacimiento: </span>
                      {cliente.fecha_nacimiento_renaper}
                    </div>
                  )}
                  {cliente.genero_renaper && (
                    <div>
                      <span className="text-muted-foreground">Género: </span>
                      {cliente.genero_renaper === "M"
                        ? "Masculino"
                        : cliente.genero_renaper === "F"
                          ? "Femenino"
                          : cliente.genero_renaper}
                    </div>
                  )}
                  {cliente.nacionalidad_renaper && (
                    <div>
                      <span className="text-muted-foreground">Nacionalidad: </span>
                      {cliente.nacionalidad_renaper}
                    </div>
                  )}
                  {cliente.lugar_nacimiento_renaper && (
                    <div>
                      <span className="text-muted-foreground">Lugar de nacimiento: </span>
                      {cliente.lugar_nacimiento_renaper}
                    </div>
                  )}
                  {cliente.estado_civil_renaper && (
                    <div>
                      <span className="text-muted-foreground">Estado civil: </span>
                      {cliente.estado_civil_renaper}
                    </div>
                  )}
                  {cliente.tipo_documento_renaper && (
                    <div>
                      <span className="text-muted-foreground">Tipo doc.: </span>
                      {cliente.tipo_documento_renaper}
                    </div>
                  )}
                  {cliente.emision_documento_renaper && (
                    <div>
                      <span className="text-muted-foreground">Emisión: </span>
                      {cliente.emision_documento_renaper}
                    </div>
                  )}
                  {cliente.vencimiento_documento_renaper && (
                    <div>
                      <span className="text-muted-foreground">Vencimiento: </span>
                      {cliente.vencimiento_documento_renaper}
                    </div>
                  )}
                  {cliente.direccion_renaper && (
                    <div className="col-span-2">
                      <span className="text-muted-foreground">Domicilio: </span>
                      {cliente.direccion_renaper}
                    </div>
                  )}
                </div>
                <div className="text-2xs text-muted-foreground font-mono">
                  Verificado {fmtFecha(cliente.dni_validado_at)}
                </div>
              </div>
            ) : (
              <div className="rounded-lg border hairline px-3 py-2.5 space-y-2.5">
                <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                  <ShieldAlert className="h-4 w-4 shrink-0" />
                  Identidad sin verificar
                  {cliente.dni_verificacion_estado === "rechazado" && " — rechazada por Didit"}
                  {cliente.dni_verificacion_estado === "en_revision" && " — en revisión en Didit"}
                </div>
                {cliente.dni_verificacion_motivo && (
                  <p className="text-xs text-muted-foreground">{cliente.dni_verificacion_motivo}</p>
                )}
                <div className="space-y-1">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={rechequeando}
                    onClick={rechequearVerificacion}
                  >
                    <ShieldCheck className="h-3.5 w-3.5" />
                    {rechequeando ? "Consultando a Didit…" : "Re-chequear con Didit"}
                  </Button>
                  <p className="text-2xs text-muted-foreground">
                    Le vuelve a preguntar a Didit el estado actual de la sesión — útil si ya lo
                    aprobaste a mano en su dashboard. Si el cliente nunca inició una verificación,
                    no hace nada.
                  </p>
                </div>
                {linkVerif ? (
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground">
                      Mandále este link al cliente (WhatsApp, mail, etc.):
                    </p>
                    <div className="flex items-center gap-2">
                      <Input
                        readOnly
                        value={linkVerif}
                        className="flex-1 truncate font-mono text-xs text-ink"
                      />
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          navigator.clipboard.writeText(linkVerif);
                          setCopiado(true);
                          setTimeout(() => setCopiado(false), 2000);
                        }}
                        className="shrink-0"
                      >
                        {copiado ? (
                          <Check className="h-3.5 w-3.5 text-verde-ink" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                        {copiado ? "Copiado" : "Copiar"}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={generando}
                    onClick={async () => {
                      if (!cliente) return;
                      setGenerando(true);
                      try {
                        const r = await adminApi.generarLinkVerificacion(cliente.id);
                        setLinkVerif(r.url);
                      } catch {
                        toast.error("No se pudo generar el link de verificación");
                      } finally {
                        setGenerando(false);
                      }
                    }}
                  >
                    <ShieldCheck className="h-3.5 w-3.5" />
                    {generando ? "Generando…" : "Generar link de verificación"}
                  </Button>
                )}
              </div>
            )}

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
      <div className="t-eyebrow">{label}</div>
      <div className="text-ink">{value}</div>
    </div>
  );
}
