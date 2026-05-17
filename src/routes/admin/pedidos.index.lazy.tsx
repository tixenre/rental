import { createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, Trash2, ExternalLink, Plus } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import { adminApi, ESTADO_LABEL, type Pedido, type PedidoEstado } from "@/lib/admin/api";
import { WhatsAppButton } from "@/components/admin/WhatsAppButton";
import {
  AdminCard,
  AdminCardHeader,
  AdminCardMeta,
  AdminCardFooter,
  AdminCardPrice,
  AdminCardActions,
  FAB,
} from "@/components/mobile";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/pedidos/")({
  component: PedidosPage,
});

const ESTADOS: PedidoEstado[] = [
  "borrador", "presupuesto", "confirmado", "retirado", "devuelto", "finalizado", "cancelado",
];

const ESTADO_CLASS: Record<string, string> = {
  borrador:    "bg-muted/60 text-muted-foreground border-transparent",
  presupuesto: "bg-blue-50 text-blue-700 border-blue-200",
  solicitado:  "bg-amber-50 text-amber-700 border-amber-200",
  confirmado:  "bg-green-50 text-green-700 border-green-200",
  retirado:    "bg-green-100 text-green-800 border-green-300",
  devuelto:    "bg-slate-100 text-slate-600 border-slate-300",
  finalizado:  "bg-slate-100 text-slate-500 border-slate-200",
  cancelado:   "bg-red-50 text-red-600 border-red-200",
};

const fmtArs = (n: number | null | undefined) =>
  n ? `$${Math.round(Number(n)).toLocaleString("es-AR", { maximumFractionDigits: 0 })}` : "$0";

const fmtFecha = (s: string | null) => (s ? s.slice(0, 10) : "—");

const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const fmtFechaMobile = (s: string | null) => {
  if (!s) return "—";
  const [, m, d] = s.slice(0, 10).split("-");
  return `${parseInt(d)} ${MESES[parseInt(m) - 1]}`;
};

function MobileCardSkeleton() {
  return (
    <div className="rounded-xl border hairline bg-surface p-4 space-y-2.5">
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-1.5 flex-1">
          <Skeleton className="h-3 w-8" />
          <Skeleton className="h-4 w-36" />
          <Skeleton className="h-3 w-28" />
        </div>
        <Skeleton className="h-5 w-20 rounded-full shrink-0" />
      </div>
      <Skeleton className="h-3 w-44" />
      <div className="flex items-center justify-between pt-0.5">
        <Skeleton className="h-4 w-24" />
        <div className="flex gap-1">
          <Skeleton className="h-9 w-9 rounded-md" />
          <Skeleton className="h-9 w-9 rounded-md" />
          <Skeleton className="h-9 w-9 rounded-md" />
        </div>
      </div>
    </div>
  );
}

function PedidosPage() {
  useDocumentTitle("Pedidos · Back Office");
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [estado, setEstado] = useState<string>("");
  const [deleting, setDeleting] = useState<Pedido | null>(null);

  const pedidosQ = useQuery({
    queryKey: ["admin", "pedidos", { q, estado }],
    queryFn: () => adminApi.listPedidos({
      q: q || undefined,
      estado: estado || undefined,
      per_page: 200,
    }),
    refetchInterval: 5000,
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => adminApi.deletePedido(id),
    onSuccess: () => {
      toast.success("Pedido eliminado");
      setDeleting(null);
      qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const openPedido = (id: number) =>
    navigate({ to: "/admin/pedidos/$id", params: { id: String(id) } });

  const items = pedidosQ.data?.items ?? [];
  const total = pedidosQ.data?.total ?? 0;

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-7xl mx-auto">
      <header className="flex flex-col md:flex-row md:items-end md:justify-between gap-3">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Back-office
          </div>
          <h1 className="font-display text-3xl text-ink">Pedidos</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {pedidosQ.isLoading ? "Cargando…" : `${total} pedidos`}
          </p>
        </div>
        <Button
          onClick={() => navigate({ to: "/admin/pedidos/nuevo" })}
          className="hidden md:flex"
        >
          <Plus className="h-4 w-4 mr-1" /> Nuevo pedido
        </Button>
      </header>

      <div className="flex flex-col md:flex-row gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar por cliente, número o remito…"
            className="pl-9"
          />
        </div>
        <Select value={estado || "__all"} onValueChange={(v) => setEstado(v === "__all" ? "" : v)}>
          <SelectTrigger className="md:w-48"><SelectValue placeholder="Todos los estados" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="__all">Todos los estados</SelectItem>
            {ESTADOS.map((e) => (
              <SelectItem key={e} value={e}>{ESTADO_LABEL[e]}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {pedidosQ.error && (
        <div className="rounded-md border hairline border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          Error: {(pedidosQ.error as Error).message}
        </div>
      )}

      {/* Mobile: cards (< md) */}
      <div className="md:hidden space-y-3 pb-24">
        {pedidosQ.isLoading && Array.from({ length: 3 }).map((_, i) => (
          <MobileCardSkeleton key={i} />
        ))}
        {!pedidosQ.isLoading && items.length === 0 && (
          <div className="py-12 text-center text-sm text-muted-foreground">Sin pedidos.</div>
        )}
        {items.map((p) => {
          const saldo = (p.monto_total ?? 0) - (p.monto_pagado ?? 0);
          return (
            <AdminCard key={p.id} onClick={() => openPedido(p.id)}>
              <AdminCardHeader
                label={`#${p.numero_pedido ?? p.id}`}
                title={p.cliente_nombre || "Sin cliente"}
                subtitle={p.cliente_email ?? undefined}
                badge={
                  <Badge variant="outline" className={ESTADO_CLASS[p.estado] ?? ""}>
                    {ESTADO_LABEL[p.estado]}
                  </Badge>
                }
              />
              <AdminCardMeta>
                {fmtFechaMobile(p.fecha_desde)} → {fmtFechaMobile(p.fecha_hasta)}
              </AdminCardMeta>
              <AdminCardFooter>
                <AdminCardPrice
                  total={p.monto_total ?? 0}
                  saldo={saldo > 0 ? saldo : null}
                />
                <AdminCardActions>
                  <div
                    className="flex gap-1"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <WhatsAppButton pedido={p} phone={p.cliente_telefono} variant="icon" />
                    <Button size="icon" variant="ghost" onClick={() => openPedido(p.id)}>
                      <ExternalLink className="h-4 w-4" />
                    </Button>
                    <Button size="icon" variant="ghost" onClick={() => setDeleting(p)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </AdminCardActions>
              </AdminCardFooter>
            </AdminCard>
          );
        })}
      </div>

      {/* Desktop: tabla (≥ md) */}
      <div className="hidden md:block rounded-lg border hairline overflow-x-auto bg-background">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-20">N°</TableHead>
              <TableHead>Cliente</TableHead>
              <TableHead className="hidden md:table-cell">Fechas</TableHead>
              <TableHead className="text-right hidden sm:table-cell">Total</TableHead>
              <TableHead className="text-right hidden md:table-cell">Saldo</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead className="text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {pedidosQ.isLoading && Array.from({ length: 5 }).map((_, i) => (
              <TableRow key={`sk-${i}`}>
                <TableCell><Skeleton className="h-4 w-12" /></TableCell>
                <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                <TableCell className="hidden md:table-cell"><Skeleton className="h-4 w-28" /></TableCell>
                <TableCell className="hidden sm:table-cell text-right"><Skeleton className="h-4 w-20 ml-auto" /></TableCell>
                <TableCell className="hidden md:table-cell text-right"><Skeleton className="h-4 w-16 ml-auto" /></TableCell>
                <TableCell><Skeleton className="h-5 w-20 rounded-full" /></TableCell>
                <TableCell className="text-right"><Skeleton className="h-7 w-16 ml-auto" /></TableCell>
              </TableRow>
            ))}
            {items.length === 0 && !pedidosQ.isLoading && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-10">
                  Sin pedidos.
                </TableCell>
              </TableRow>
            )}
            {items.map((p) => {
              const saldo = (p.monto_total ?? 0) - (p.monto_pagado ?? 0);
              return (
                <TableRow
                  key={p.id}
                  className="cursor-pointer hover:bg-accent/30"
                  onClick={() => openPedido(p.id)}
                >
                  <TableCell className="font-mono text-xs">
                    {p.numero_pedido ?? "—"}
                  </TableCell>
                  <TableCell>
                    <div className="text-ink">{p.cliente_nombre || "Sin cliente"}</div>
                    {p.cliente_email && (
                      <div className="text-xs text-muted-foreground">{p.cliente_email}</div>
                    )}
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                    {fmtFecha(p.fecha_desde)} → {fmtFecha(p.fecha_hasta)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums hidden sm:table-cell">
                    {fmtArs(p.monto_total)}
                  </TableCell>
                  <TableCell className={`text-right tabular-nums hidden md:table-cell ${saldo > 0 ? "text-ink" : "text-muted-foreground"}`}>
                    {fmtArs(saldo)}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className={ESTADO_CLASS[p.estado] ?? ""}
                    >
                      {ESTADO_LABEL[p.estado]}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                    <div className="inline-flex gap-1 items-center">
                      <WhatsAppButton pedido={p} phone={p.cliente_telefono} variant="icon" />
                      <Button size="icon" variant="ghost" onClick={() => openPedido(p.id)}>
                        <ExternalLink className="h-4 w-4" />
                      </Button>
                      <Button size="icon" variant="ghost" onClick={() => setDeleting(p)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {/* FAB mobile — nuevo pedido */}
      <FAB
        className="md:hidden"
        onClick={() => navigate({ to: "/admin/pedidos/nuevo" })}
        label="Nuevo pedido"
      />

      <AlertDialog open={!!deleting} onOpenChange={(v) => { if (!v) setDeleting(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Eliminar pedido {deleting?.numero_pedido ? `#${deleting.numero_pedido}` : `#${deleting?.id}`}
            </AlertDialogTitle>
            <AlertDialogDescription>
              Se borrarán también sus ítems y pagos. Esta acción no se puede deshacer.
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
