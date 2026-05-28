import { createLazyFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, Trash2, ExternalLink, Plus, Coins, Pencil } from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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

import { adminApi, ESTADO_LABEL, type Pedido } from "@/lib/admin/api";
import { EstadoBadge } from "@/components/kit/EstadoBadge";
import { authedJson } from "@/lib/authedFetch";
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

/** Grupos de estados que se exponen como chips en el toolbar. Algunos mapean
 *  a un único `estado` del backend, otros agrupan varios y se filtran client-side. */
type EstadoFilter = "activos" | "presupuesto" | "confirmado" | "cerrados" | "todos";

const ESTADO_FILTERS: { id: EstadoFilter; label: string }[] = [
  { id: "activos", label: "Activos" },
  { id: "presupuesto", label: "Solicitados" },
  { id: "confirmado", label: "Confirmados" },
  { id: "cerrados", label: "Cerrados" },
  { id: "todos", label: "Todos" },
];

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
  const [filter, setFilter] = useState<EstadoFilter>("activos");
  const [conSaldo, setConSaldo] = useState(false);
  const [deleting, setDeleting] = useState<Pedido | null>(null);

  // El mock muestra "Solicitado" para el estado interno 'presupuesto'
  // (RUTAS §4.2 del handoff: label visible distinto del estado de la DB).
  const estadoLabel = (e: Pedido["estado"]) =>
    e === "presupuesto" ? "Solicitado" : ESTADO_LABEL[e];

  // Chips "Activos" y "Cerrados" agrupan varios estados → filtramos client-side
  // sobre la lista que devuelve el backend (per_page=200 cubre el volumen real).
  const backendEstado = filter === "presupuesto" || filter === "confirmado" ? filter : undefined;

  const pedidosQ = useQuery({
    queryKey: ["admin", "pedidos", { q, filter, conSaldo }],
    queryFn: () =>
      adminApi.listPedidos({
        q: q || undefined,
        estado: conSaldo ? undefined : backendEstado,
        con_saldo: conSaldo || undefined,
        per_page: 200,
      }),
    refetchInterval: 5000,
  });

  // Contador de solicitudes pendientes para el badge del tab. Fetcheo separado
  // para que sea independiente del filtro del listado de pedidos.
  const solicitudesQ = useQuery({
    queryKey: ["admin", "solicitudes", "count"],
    queryFn: () => authedJson<{ estado: string }[]>("/api/admin/solicitudes"),
    refetchInterval: 10000,
  });
  const pendingCount = (solicitudesQ.data ?? []).filter((s) => s.estado === "pendiente").length;

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

  // El backend filtra solo cuando le pasamos un estado puntual; "Activos" y
  // "Cerrados" son agrupaciones que aplicamos acá.
  const items = useMemo(() => {
    const raw = pedidosQ.data?.items ?? [];
    if (conSaldo) return raw;
    if (filter === "activos")
      return raw.filter((p) => p.estado !== "finalizado" && p.estado !== "cancelado");
    if (filter === "cerrados")
      return raw.filter((p) => p.estado === "finalizado" || p.estado === "cancelado");
    return raw;
  }, [pedidosQ.data, filter, conSaldo]);
  const total = pedidosQ.data?.total ?? 0;

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-7xl mx-auto">
      <header className="flex flex-col md:flex-row md:items-end md:justify-between gap-3">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Operaciones · Pedidos
          </div>
          <h1 className="font-display text-3xl text-ink">Pedidos</h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-[540px]">
            Reservas activas y solicitudes de cambio de tus clientes.{" "}
            {pedidosQ.isLoading ? "Cargando…" : `${total} en total.`}
          </p>
        </div>
        <Button onClick={() => navigate({ to: "/admin/pedidos/nuevo" })} className="hidden md:flex">
          <Plus className="h-4 w-4 mr-1" /> Nuevo pedido
        </Button>
      </header>

      {/* Tabs: Todos / Cobranzas / Solicitudes. Solicitudes navega a su página
          dedicada porque es un flujo aparte (cliente → admin), no un filtro. */}
      <div className="flex items-center gap-1 border-b hairline -mb-1">
        <button
          type="button"
          onClick={() => {
            setConSaldo(false);
            setFilter("activos");
          }}
          className={cn(
            "px-3 py-2 text-sm font-medium border-b-2 transition",
            !conSaldo
              ? "border-amber text-ink"
              : "border-transparent text-muted-foreground hover:text-ink",
          )}
        >
          Todos
        </button>
        <button
          type="button"
          onClick={() => {
            setConSaldo(true);
            setFilter("todos");
          }}
          className={cn(
            "px-3 py-2 text-sm font-medium border-b-2 transition inline-flex items-center gap-1.5",
            conSaldo
              ? "border-amber text-ink"
              : "border-transparent text-muted-foreground hover:text-ink",
          )}
        >
          Cobranzas
          <Coins className="h-3.5 w-3.5" />
        </button>
        <Link
          to="/admin/solicitudes"
          className={cn(
            "px-3 py-2 text-sm font-medium border-b-2 border-transparent text-muted-foreground hover:text-ink transition inline-flex items-center gap-1.5",
          )}
        >
          Solicitudes
          <Pencil className="h-3.5 w-3.5" />
          {pendingCount > 0 && (
            <span className="inline-flex min-w-[20px] items-center justify-center rounded-full bg-amber px-1.5 py-px font-mono text-[10px] font-bold tracking-wider text-ink">
              {pendingCount}
            </span>
          )}
        </Link>
      </div>

      <div className="flex flex-col gap-2.5">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar por cliente, número o remito…"
            className="pl-9 md:max-w-md"
          />
        </div>
        {!conSaldo && (
          <div className="flex flex-wrap items-center gap-1.5">
            {ESTADO_FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setFilter(f.id)}
                className={cn(
                  "inline-flex items-center rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors",
                  filter === f.id
                    ? "bg-ink text-amber border-ink"
                    : "border-hairline text-muted-foreground hover:text-ink hover:border-ink",
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Banner de totales cuando estás viendo cobranzas */}
      {conSaldo &&
        pedidosQ.data &&
        (() => {
          const items = pedidosQ.data.items;
          const totalSaldo = items.reduce(
            (s, p) => s + Math.max(0, (p.monto_total ?? 0) - (p.monto_pagado ?? 0)),
            0,
          );
          return (
            <div className="rounded-md border border-amber/40 bg-amber-soft/50 px-3.5 py-2.5 flex items-center justify-between gap-2 text-sm">
              <span className="text-ink">
                <strong>{items.length}</strong> pedido{items.length !== 1 ? "s" : ""} con saldo
                pendiente
              </span>
              <span className="font-display text-lg tabular text-ink">{fmtArs(totalSaldo)}</span>
            </div>
          );
        })()}

      {pedidosQ.error && (
        <div className="rounded-md border hairline border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          Error: {(pedidosQ.error as Error).message}
        </div>
      )}

      {/* Mobile: cards (< md) */}
      <div className="md:hidden space-y-3 pb-24">
        {pedidosQ.isLoading &&
          Array.from({ length: 3 }).map((_, i) => <MobileCardSkeleton key={i} />)}
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
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <EstadoBadge estado={p.estado} label={estadoLabel(p.estado)} />
                    {p.tiene_solicitud_pendiente && (
                      <Badge variant="outline" className="border-amber text-amber-700 bg-amber-50">
                        Modificación pendiente
                      </Badge>
                    )}
                  </div>
                }
              />
              <AdminCardMeta>
                {fmtFechaMobile(p.fecha_desde)} → {fmtFechaMobile(p.fecha_hasta)}
              </AdminCardMeta>
              <AdminCardFooter>
                <AdminCardPrice total={p.monto_total ?? 0} saldo={saldo > 0 ? saldo : null} />
                <AdminCardActions>
                  <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
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
              <TableHead className="w-20">Pedido</TableHead>
              <TableHead>Cliente</TableHead>
              <TableHead className="hidden md:table-cell">Fechas</TableHead>
              <TableHead className="hidden lg:table-cell">Items</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead className="text-right">Monto</TableHead>
              <TableHead className="text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {pedidosQ.isLoading &&
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={`sk-${i}`}>
                  <TableCell>
                    <Skeleton className="h-4 w-12" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-32" />
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <Skeleton className="h-4 w-28" />
                  </TableCell>
                  <TableCell className="hidden sm:table-cell text-right">
                    <Skeleton className="h-4 w-20 ml-auto" />
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-right">
                    <Skeleton className="h-4 w-16 ml-auto" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-20 rounded-full" />
                  </TableCell>
                  <TableCell className="text-right">
                    <Skeleton className="h-7 w-16 ml-auto" />
                  </TableCell>
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
              return (
                <TableRow
                  key={p.id}
                  className="cursor-pointer hover:bg-accent/30"
                  onClick={() => openPedido(p.id)}
                >
                  <TableCell className="font-mono text-xs">{p.numero_pedido ?? "—"}</TableCell>
                  <TableCell>
                    <div className="text-ink">{p.cliente_nombre || "Sin cliente"}</div>
                    {p.cliente_email && (
                      <div className="text-xs text-muted-foreground">{p.cliente_email}</div>
                    )}
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-sm text-muted-foreground tabular-nums">
                    {fmtFecha(p.fecha_desde)}{" "}
                    <span className="text-muted-foreground/50 mx-0.5">→</span>{" "}
                    {fmtFecha(p.fecha_hasta)}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                    {p.items?.length ?? 0} equipos
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <EstadoBadge estado={p.estado} label={estadoLabel(p.estado)} />
                      {p.tiene_solicitud_pendiente && (
                        <span className="inline-flex items-center gap-1 font-mono text-[10px] font-bold uppercase tracking-wide text-amber-700">
                          <Pencil className="h-3 w-3" /> mod.
                        </span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    <div className="text-ink font-medium">{fmtArs(p.monto_total)}</div>
                    <div
                      className={cn(
                        "font-mono text-[10px] mt-0.5",
                        (p.monto_pagado ?? 0) >= (p.monto_total ?? 0)
                          ? "text-verde"
                          : (p.monto_pagado ?? 0) > 0
                            ? "text-muted-foreground"
                            : "text-destructive",
                      )}
                    >
                      {(p.monto_pagado ?? 0) >= (p.monto_total ?? 0)
                        ? "pagado"
                        : (p.monto_pagado ?? 0) === 0
                          ? "sin seña"
                          : `seña ${fmtArs(p.monto_pagado)}`}
                    </div>
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

      <AlertDialog
        open={!!deleting}
        onOpenChange={(v) => {
          if (!v) setDeleting(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Eliminar pedido{" "}
              {deleting?.numero_pedido ? `#${deleting.numero_pedido}` : `#${deleting?.id}`}
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
