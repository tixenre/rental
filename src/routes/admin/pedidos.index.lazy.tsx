import { createLazyFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Search, Trash2, ExternalLink, Plus, Minus, Pencil, MessageSquare,
  Check, X, Clock, Inbox, AlertTriangle, ArrowRight, ChevronDown, RotateCcw,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import {
  adminApi, ESTADO_LABEL,
  type Pedido, type SolicitudAdmin, type SolicitudEstado,
  type SolicitudItemSnapshot,
} from "@/lib/admin/api";
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

export const Route = createLazyFileRoute("/admin/pedidos/")({
  component: PedidosPage,
});

const ESTADO_CLASS: Record<string, string> = {
  borrador:    "bg-muted/60 text-muted-foreground border-transparent",
  presupuesto: "bg-amber-100 text-amber-900 border-amber-200",
  confirmado:  "bg-green-100 text-green-800 border-green-200",
  retirado:    "bg-indigo-100 text-indigo-800 border-indigo-200",
  devuelto:    "bg-emerald-100 text-emerald-800 border-emerald-200",
  finalizado:  "bg-slate-100 text-slate-600 border-slate-200",
  cancelado:   "bg-red-50 text-red-700 border-red-200",
};

const fmtArs = (n: number | null | undefined) =>
  n ? `$${Math.round(Number(n)).toLocaleString("es-AR", { maximumFractionDigits: 0 })}` : "$0";

const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const fmtFechaCorta = (s: string | null) => {
  if (!s) return "—";
  const [, m, d] = s.slice(0, 10).split("-");
  return `${parseInt(d)} ${MESES[parseInt(m) - 1]}`;
};

function fmtRelative(s: string): string {
  const d = new Date(s).getTime();
  if (Number.isNaN(d)) return "—";
  const diff = Date.now() - d;
  if (diff < 0) return "ahora";
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `hace ${mins} min`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `hace ${hrs} h`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `hace ${days} d`;
  return fmtFechaCorta(s.slice(0, 10));
}

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

type EstadoFilter = "activos" | "presupuesto" | "confirmado" | "cerrados" | "todos";

const ESTADO_FILTERS: { id: EstadoFilter; label: string }[] = [
  { id: "activos",     label: "Activos" },
  { id: "presupuesto", label: "Solicitados" },
  { id: "confirmado",  label: "Confirmados" },
  { id: "cerrados",    label: "Cerrados" },
  { id: "todos",       label: "Todos" },
];

function FilterChip({
  active, onClick, children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-colors " +
        (active
          ? "bg-ink text-amber border-ink"
          : "bg-transparent text-muted-foreground border-hairline hover:text-ink hover:border-ink")
      }
    >
      {children}
    </button>
  );
}

function PrimaryTab({
  active, onClick, label, count, urgent,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count: number;
  urgent?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "relative -mb-px inline-flex items-center gap-2 border-b-2 px-1 py-3.5 text-sm font-semibold transition-colors " +
        (active
          ? "border-amber text-ink"
          : "border-transparent text-muted-foreground hover:text-ink")
      }
    >
      <span>{label}</span>
      <span
        className={
          "inline-flex min-w-[22px] items-center justify-center rounded-full px-1.5 py-px font-mono text-[10px] font-bold tracking-wider " +
          (active
            ? "bg-amber text-ink"
            : urgent
              ? "bg-amber text-ink animate-pulse"
              : "bg-muted text-muted-foreground")
        }
      >
        {count}
      </span>
    </button>
  );
}

function BalanceLabel({ pagado, total }: { pagado: number; total: number }) {
  if (pagado >= total && total > 0) {
    return <div className="font-mono text-[11px] text-green-700">pagado</div>;
  }
  if (pagado === 0) {
    return <div className="font-mono text-[11px] text-destructive">sin seña</div>;
  }
  return (
    <div className="font-mono text-[11px] text-muted-foreground">
      seña {fmtArs(pagado)}
    </div>
  );
}

function PedidosPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [tab, setTab] = useState<"pedidos" | "solicitudes">("pedidos");
  const [deleting, setDeleting] = useState<Pedido | null>(null);
  const [autoSwitched, setAutoSwitched] = useState(false);

  const pedidosQ = useQuery({
    queryKey: ["admin", "pedidos", { per_page: 200 }],
    queryFn: () => adminApi.listPedidos({ per_page: 200 }),
    refetchInterval: 5000,
  });

  const solicitudesQ = useQuery({
    queryKey: ["admin", "solicitudes"],
    queryFn: () => adminApi.listSolicitudes(),
    refetchInterval: 10000,
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

  const items = pedidosQ.data?.items ?? [];
  const total = pedidosQ.data?.total ?? 0;
  const solicitudes = solicitudesQ.data ?? [];
  const pendingCount = solicitudes.filter((s) => s.estado === "pendiente").length;

  const pedidosConPendiente = useMemo(() => {
    const set = new Set<number>();
    for (const s of solicitudes) if (s.estado === "pendiente") set.add(s.pedido_id);
    return set;
  }, [solicitudes]);

  // First time the data lands and there are pending requests, jump to that tab.
  // We track the auto-switch so we don't hijack the user once they pick a tab.
  useEffect(() => {
    if (autoSwitched) return;
    if (solicitudesQ.isLoading) return;
    setAutoSwitched(true);
    if (pendingCount > 0) setTab("solicitudes");
  }, [autoSwitched, pendingCount, solicitudesQ.isLoading]);

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-7xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office
        </div>
        <div className="mt-1 flex items-baseline justify-between gap-4">
          <h1 className="font-display text-3xl md:text-4xl font-black text-ink leading-none tracking-tight">
            Pedidos
          </h1>
        </div>
        <p className="mt-2 max-w-[540px] text-sm text-muted-foreground leading-snug">
          Reservas activas y solicitudes de cambio de tus clientes. Las modificaciones aparecen como
          solapa aparte para que puedas resolverlas rápido.
        </p>
      </header>

      <div className="flex items-stretch gap-7 border-b hairline">
        <PrimaryTab
          active={tab === "pedidos"}
          onClick={() => setTab("pedidos")}
          label="Todos los pedidos"
          count={total}
        />
        <PrimaryTab
          active={tab === "solicitudes"}
          onClick={() => setTab("solicitudes")}
          label="Solicitudes"
          count={pendingCount > 0 ? pendingCount : solicitudes.length}
          urgent={pendingCount > 0 && tab !== "solicitudes"}
        />
      </div>

      {pedidosQ.error && (
        <div className="rounded-md border hairline border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          Error: {(pedidosQ.error as Error).message}
        </div>
      )}

      {tab === "pedidos" ? (
        <PedidosTab
          loading={pedidosQ.isLoading}
          items={items}
          pedidosConPendiente={pedidosConPendiente}
          onSwitchToSolicitudes={() => setTab("solicitudes")}
          onDelete={(p) => setDeleting(p)}
        />
      ) : (
        <SolicitudesTab
          loading={solicitudesQ.isLoading}
          solicitudes={solicitudes}
          onResolved={() => {
            qc.invalidateQueries({ queryKey: ["admin", "solicitudes"] });
            qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
          }}
        />
      )}

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

// ── PedidosTab ───────────────────────────────────────────────────────────────

function PedidosTab({
  loading,
  items,
  pedidosConPendiente,
  onSwitchToSolicitudes,
  onDelete,
}: {
  loading: boolean;
  items: Pedido[];
  pedidosConPendiente: Set<number>;
  onSwitchToSolicitudes: () => void;
  onDelete: (p: Pedido) => void;
}) {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [estado, setEstado] = useState<EstadoFilter>("activos");

  const filtered = useMemo(() => {
    return items.filter((p) => {
      if (estado === "activos" && (p.estado === "finalizado" || p.estado === "cancelado")) return false;
      if (estado === "presupuesto" && p.estado !== "presupuesto") return false;
      if (estado === "confirmado" && p.estado !== "confirmado") return false;
      if (estado === "cerrados" && p.estado !== "finalizado" && p.estado !== "cancelado") return false;
      if (q.trim()) {
        const needle = q.trim().toLowerCase();
        const hay = `${p.numero_pedido ?? ""} ${p.cliente_nombre ?? ""} ${p.cliente_email ?? ""}`.toLowerCase();
        if (!hay.includes(needle)) return false;
      }
      return true;
    });
  }, [items, estado, q]);

  const openPedido = (id: number) =>
    navigate({ to: "/admin/pedidos/$id", params: { id: String(id) } });

  return (
    <>
      <div className="flex flex-wrap items-center gap-2.5">
        <div className="relative flex-1 min-w-[240px] md:max-w-[320px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar por número, cliente o email…"
            className="pl-10 rounded-full bg-surface"
          />
        </div>
        {ESTADO_FILTERS.map((f) => (
          <FilterChip
            key={f.id}
            active={estado === f.id}
            onClick={() => setEstado(f.id)}
          >
            {f.label}
          </FilterChip>
        ))}
        <span className="flex-1" />
        <Button
          onClick={() => navigate({ to: "/admin/pedidos/nuevo" })}
          className="hidden md:inline-flex rounded-full bg-ink text-amber hover:bg-amber hover:text-ink"
        >
          <Plus className="h-4 w-4 mr-1" /> Nuevo pedido
        </Button>
      </div>

      {/* Mobile: cards (< md) */}
      <div className="md:hidden space-y-3 pb-24 mt-4">
        {loading && Array.from({ length: 3 }).map((_, i) => <MobileCardSkeleton key={i} />)}
        {!loading && filtered.length === 0 && (
          <div className="py-12 text-center text-sm text-muted-foreground">Sin pedidos.</div>
        )}
        {filtered.map((p) => {
          const saldo = (p.monto_total ?? 0) - (p.monto_pagado ?? 0);
          const tieneMod = pedidosConPendiente.has(p.id);
          return (
            <AdminCard key={p.id} onClick={() => openPedido(p.id)}>
              <AdminCardHeader
                label={`#${p.numero_pedido ?? p.id}`}
                title={p.cliente_nombre || "Sin cliente"}
                subtitle={p.cliente_email ?? undefined}
                badge={
                  <div className="flex items-center gap-1">
                    <Badge variant="outline" className={ESTADO_CLASS[p.estado] ?? ""}>
                      {ESTADO_LABEL[p.estado]}
                    </Badge>
                    {tieneMod && (
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); onSwitchToSolicitudes(); }}
                        className="inline-flex items-center gap-0.5 rounded-full bg-amber px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider text-ink"
                      >
                        <Pencil className="h-2.5 w-2.5" /> mod.
                      </button>
                    )}
                  </div>
                }
              />
              <AdminCardMeta>
                {fmtFechaCorta(p.fecha_desde)} → {fmtFechaCorta(p.fecha_hasta)}
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
                    <Button size="icon" variant="ghost" onClick={() => onDelete(p)}>
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
      <div className="hidden md:block mt-4 rounded-lg border hairline overflow-x-auto bg-card">
        <Table>
          <TableHeader>
            <TableRow className="bg-surface">
              <TableHead className="w-24 font-mono text-[9px] uppercase tracking-widest text-muted-foreground">Pedido</TableHead>
              <TableHead className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">Cliente</TableHead>
              <TableHead className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground hidden md:table-cell">Fechas</TableHead>
              <TableHead className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground hidden lg:table-cell">Items</TableHead>
              <TableHead className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">Estado</TableHead>
              <TableHead className="text-right font-mono text-[9px] uppercase tracking-widest text-muted-foreground">Monto</TableHead>
              <TableHead className="text-right font-mono text-[9px] uppercase tracking-widest text-muted-foreground">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && Array.from({ length: 5 }).map((_, i) => (
              <TableRow key={`sk-${i}`}>
                <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                <TableCell className="hidden md:table-cell"><Skeleton className="h-4 w-28" /></TableCell>
                <TableCell className="hidden lg:table-cell"><Skeleton className="h-4 w-16" /></TableCell>
                <TableCell><Skeleton className="h-5 w-20 rounded-full" /></TableCell>
                <TableCell className="text-right"><Skeleton className="h-4 w-20 ml-auto" /></TableCell>
                <TableCell className="text-right"><Skeleton className="h-7 w-16 ml-auto" /></TableCell>
              </TableRow>
            ))}
            {filtered.length === 0 && !loading && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-10">
                  Sin pedidos.
                </TableCell>
              </TableRow>
            )}
            {filtered.map((p) => {
              const tieneMod = pedidosConPendiente.has(p.id);
              const itemsCount = p.items?.length ?? 0;
              return (
                <TableRow
                  key={p.id}
                  className="cursor-pointer hover:bg-accent/30"
                  onClick={() => openPedido(p.id)}
                >
                  <TableCell className="font-mono text-xs font-bold tracking-wider">
                    {p.numero_pedido ?? "—"}
                  </TableCell>
                  <TableCell>
                    <div className="font-semibold text-ink">{p.cliente_nombre || "Sin cliente"}</div>
                    {p.cliente_email && (
                      <div className="font-mono text-[10px] tracking-wide text-muted-foreground mt-0.5">
                        {p.cliente_email}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="hidden md:table-cell font-mono text-xs tabular-nums text-ink">
                    {fmtFechaCorta(p.fecha_desde)}
                    <span className="text-muted-foreground mx-1">→</span>
                    {fmtFechaCorta(p.fecha_hasta)}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell font-mono text-[11px] text-muted-foreground">
                    {itemsCount ? `${itemsCount} equipos` : "—"}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className={(ESTADO_CLASS[p.estado] ?? "") + " font-mono text-[9px] font-bold uppercase tracking-widest"}
                    >
                      {ESTADO_LABEL[p.estado]}
                    </Badge>
                    {tieneMod && (
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); onSwitchToSolicitudes(); }}
                        className="ml-1.5 inline-flex items-center gap-0.5 rounded-full bg-amber px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider text-ink hover:opacity-90"
                      >
                        <Pencil className="h-2.5 w-2.5" /> mod.
                      </button>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="font-mono text-sm font-bold tabular-nums text-ink">
                      {fmtArs(p.monto_total)}
                    </div>
                    <BalanceLabel pagado={p.monto_pagado ?? 0} total={p.monto_total ?? 0} />
                  </TableCell>
                  <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                    <div className="inline-flex gap-1 items-center">
                      <WhatsAppButton pedido={p} phone={p.cliente_telefono} variant="icon" />
                      <Button size="icon" variant="ghost" onClick={() => openPedido(p.id)}>
                        <ExternalLink className="h-4 w-4" />
                      </Button>
                      <Button size="icon" variant="ghost" onClick={() => onDelete(p)}>
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
    </>
  );
}

// ── SolicitudesTab ───────────────────────────────────────────────────────────

type SolicitudFilter = "pendientes" | "resueltas" | "todas";

function SolicitudesTab({
  loading,
  solicitudes,
  onResolved,
}: {
  loading: boolean;
  solicitudes: SolicitudAdmin[];
  onResolved: () => void;
}) {
  const [filter, setFilter] = useState<SolicitudFilter>("pendientes");

  const pendientes = solicitudes.filter((s) => s.estado === "pendiente");
  const resueltas = solicitudes.filter((s) => s.estado !== "pendiente");

  const today = new Date().toISOString().slice(0, 10);
  const resueltasHoy = resueltas.filter((s) => s.created_at.startsWith(today)).length;
  const aprobadasMes = resueltas.filter((s) => s.estado === "aprobada").length;

  return (
    <div className="space-y-5">
      <div className="sticky top-0 z-10 -mx-4 md:-mx-6 px-4 md:px-6 flex items-center gap-1.5 border-b hairline bg-background/90 backdrop-blur py-3">
        {(["pendientes", "resueltas", "todas"] as const).map((f) => {
          const count = f === "pendientes" ? pendientes.length
            : f === "resueltas" ? resueltas.length
            : solicitudes.length;
          return (
            <FilterChip
              key={f}
              active={filter === f}
              onClick={() => setFilter(f)}
            >
              {f === "pendientes" ? "Pendientes" : f === "resueltas" ? "Resueltas" : "Todas"}
              <span className="font-mono text-[10px] opacity-70">{count}</span>
            </FilterChip>
          );
        })}
        <span className="flex-1" />
        <span className="hidden sm:inline font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          Más nuevas primero
        </span>
      </div>

      {filter === "pendientes" && pendientes.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 max-w-[560px]">
          <Kpi label="Pendientes" value={pendientes.length} meta="requieren respuesta" alert />
          <Kpi label="Resueltas hoy" value={resueltasHoy} meta="en las últimas 24 h" />
          <Kpi
            label="Aprobadas (mes)"
            value={aprobadasMes}
            meta={`de ${resueltas.length} resueltas`}
          />
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          <Skeleton className="h-40 w-full max-w-[940px]" />
          <Skeleton className="h-40 w-full max-w-[940px]" />
        </div>
      ) : (
        <>
          {filter !== "resueltas" && pendientes.length > 0 && (
            <div className="flex flex-col gap-3.5 max-w-[940px]">
              {pendientes.map((s) => (
                <PendienteCard key={s.id} solicitud={s} onResolved={onResolved} />
              ))}
            </div>
          )}

          {filter !== "pendientes" && resueltas.length > 0 && (
            <section className="max-w-[940px] mt-8">
              <header className="flex items-baseline gap-2.5 pb-3 border-b hairline mb-2.5">
                <h2 className="font-display text-lg font-black tracking-tight text-ink">
                  Resueltas
                </h2>
                <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                  {resueltas.length} en total
                </span>
              </header>
              {resueltas.map((s) => (
                <ResueltaRow key={s.id} solicitud={s} />
              ))}
            </section>
          )}

          {filter === "pendientes" && pendientes.length === 0 && (
            <EmptyState
              title="Todo al día"
              sub="No hay solicitudes pendientes de respuesta."
            />
          )}
          {filter === "resueltas" && resueltas.length === 0 && (
            <EmptyState title="Sin historial" sub="Todavía no se resolvió ninguna solicitud." />
          )}
          {filter === "todas" && solicitudes.length === 0 && (
            <EmptyState title="Sin solicitudes" sub="Los clientes todavía no pidieron modificaciones." />
          )}
        </>
      )}
    </div>
  );
}

function Kpi({
  label, value, meta, alert,
}: { label: string; value: number; meta: string; alert?: boolean }) {
  return (
    <div
      className={
        "rounded-xl border p-3.5 " +
        (alert
          ? "border-amber/50 bg-amber-soft/40"
          : "border-hairline bg-surface")
      }
    >
      <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
        {label}
      </div>
      <div className="font-display text-2xl font-black tabular-nums text-ink leading-none mt-1.5">
        {value}
      </div>
      <div className="font-mono text-[10px] text-muted-foreground mt-1">{meta}</div>
    </div>
  );
}

function EmptyState({ title, sub }: { title: string; sub: string }) {
  return (
    <div className="rounded-lg border border-dashed border-hairline px-6 py-14 text-center max-w-[940px]">
      <div className="mx-auto mb-3.5 grid h-14 w-14 place-items-center rounded-full bg-amber-soft text-ink">
        <Inbox className="h-6 w-6" />
      </div>
      <div className="font-display text-xl font-black text-ink mb-1.5">{title}</div>
      <div className="text-sm text-muted-foreground">{sub}</div>
    </div>
  );
}

// ── Diff helpers ─────────────────────────────────────────────────────────────

type DiffRowKind = "same" | "added" | "removed" | "changed";
type DiffRow = {
  kind: DiffRowKind;
  equipo_id: number;
  nombre: string;
  antes: number;
  despues: number;
};

function buildItemsDiff(
  antes: SolicitudItemSnapshot[],
  despues: SolicitudItemSnapshot[],
): DiffRow[] {
  const aMap = new Map(antes.map((it) => [it.equipo_id, it]));
  const dMap = new Map(despues.map((it) => [it.equipo_id, it]));
  const allIds = new Set<number>([...aMap.keys(), ...dMap.keys()]);
  const rows: DiffRow[] = [];
  for (const id of allIds) {
    const a = aMap.get(id);
    const d = dMap.get(id);
    if (!a && d) {
      rows.push({ kind: "added", equipo_id: id, nombre: d.nombre_publico || d.nombre, antes: 0, despues: d.cantidad });
    } else if (a && !d) {
      rows.push({ kind: "removed", equipo_id: id, nombre: a.nombre_publico || a.nombre, antes: a.cantidad, despues: 0 });
    } else if (a && d && a.cantidad !== d.cantidad) {
      rows.push({ kind: "changed", equipo_id: id, nombre: d.nombre_publico || d.nombre, antes: a.cantidad, despues: d.cantidad });
    } else if (a && d) {
      rows.push({ kind: "same", equipo_id: id, nombre: d.nombre_publico || d.nombre, antes: a.cantidad, despues: d.cantidad });
    }
  }
  return rows;
}

function jornadasEntre(desde: string | null, hasta: string | null): number {
  if (!desde || !hasta) return 1;
  const d0 = new Date(desde + (desde.length === 10 ? "T12:00:00" : "")).getTime();
  const d1 = new Date(hasta + (hasta.length === 10 ? "T12:00:00" : "")).getTime();
  if (Number.isNaN(d0) || Number.isNaN(d1) || d1 < d0) return 1;
  return Math.max(1, Math.ceil((d1 - d0) / 86_400_000) + 1);
}

function calcMonto(items: { cantidad: number; precio_jornada: number }[], jornadas: number): number {
  return items.reduce((acc, it) => acc + it.precio_jornada * it.cantidad * jornadas, 0);
}

function fmtFechaLarga(s: string | null): string {
  if (!s) return "—";
  const d = new Date(s + (s.length === 10 ? "T12:00:00" : ""));
  if (Number.isNaN(d.getTime())) return "—";
  const dias = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
  return `${dias[d.getDay()]} ${d.getDate()} ${MESES[d.getMonth()]}`;
}

// ── PendienteCard ────────────────────────────────────────────────────────────

function PendienteCard({
  solicitud,
  onResolved,
}: {
  solicitud: SolicitudAdmin;
  onResolved: () => void;
}) {
  const [respuesta, setRespuesta] = useState("");
  const [overrideOpen, setOverrideOpen] = useState(false);

  // Baseline para el override: la propuesta del cliente si existe, sino el
  // pedido actual (caso "mensaje libre" donde no hay diff).
  const baseline = solicitud.propuesta ?? solicitud.pedido_actual;
  const baselineKey = solicitud.id;
  const baselineItemsKey = useMemo(
    () => new Map(baseline.items.map((it) => [it.equipo_id, it.cantidad])),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [baselineKey],
  );

  const [overrideItems, setOverrideItems] = useState<Map<number, number>>(
    () => new Map(baselineItemsKey),
  );
  const [overrideDesde, setOverrideDesde] = useState<string>(
    baseline.fecha_desde?.slice(0, 10) ?? "",
  );
  const [overrideHasta, setOverrideHasta] = useState<string>(
    baseline.fecha_hasta?.slice(0, 10) ?? "",
  );
  const [search, setSearch] = useState("");

  // Si llega otra solicitud, resetear el editor.
  useEffect(() => {
    setOverrideItems(new Map(baselineItemsKey));
    setOverrideDesde(baseline.fecha_desde?.slice(0, 10) ?? "");
    setOverrideHasta(baseline.fecha_hasta?.slice(0, 10) ?? "");
    setSearch("");
    setOverrideOpen(false);
    setRespuesta("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baselineKey]);

  const hayOverride = useMemo(() => {
    if ((overrideDesde || null) !== (baseline.fecha_desde?.slice(0, 10) ?? null)) return true;
    if ((overrideHasta || null) !== (baseline.fecha_hasta?.slice(0, 10) ?? null)) return true;
    if (overrideItems.size !== baselineItemsKey.size) return true;
    for (const [k, v] of overrideItems) {
      if (baselineItemsKey.get(k) !== v) return true;
    }
    return false;
  }, [overrideItems, overrideDesde, overrideHasta, baselineItemsKey, baseline]);

  // Equipos del catálogo cuando el editor está abierto (search + add).
  const equiposQ = useQuery({
    queryKey: ["admin", "equipos", "for-override"],
    queryFn: () => adminApi.listEquipos({ per_page: 1000 }),
    enabled: overrideOpen,
  });

  const equiposPorId = useMemo(() => {
    const map = new Map<number, { nombre: string; marca: string | null; categoria: string | null; precio_jornada: number }>();
    for (const e of equiposQ.data?.items ?? []) {
      map.set(e.id, {
        nombre: e.nombre,
        marca: e.marca ?? null,
        categoria: e.categorias?.[0]?.nombre ?? null,
        precio_jornada: e.precio_jornada ?? 0,
      });
    }
    // Merge in snapshot info from solicitud (cliente puede haber propuesto un equipo
    // que también está en el listado, pero igual lo tenemos del snapshot).
    for (const src of [baseline.items, solicitud.pedido_actual.items]) {
      for (const it of src) {
        if (!map.has(it.equipo_id)) {
          map.set(it.equipo_id, {
            nombre: it.nombre,
            marca: it.marca,
            categoria: null,
            precio_jornada: it.precio_jornada,
          });
        }
      }
    }
    return map;
  }, [equiposQ.data, baseline.items, solicitud.pedido_actual.items]);

  const overrideItemsEfectivos = useMemo(() => {
    return Array.from(overrideItems.entries())
      .filter(([, c]) => c > 0)
      .map(([equipo_id, cantidad]) => {
        const info = equiposPorId.get(equipo_id);
        return {
          equipo_id,
          cantidad,
          nombre: info?.nombre ?? "—",
          marca: info?.marca ?? null,
          precio_jornada: info?.precio_jornada ?? 0,
        };
      });
  }, [overrideItems, equiposPorId]);

  const overrideVacio = hayOverride && overrideItemsEfectivos.length === 0;

  function bumpQty(equipo_id: number, delta: number) {
    setOverrideItems((prev) => {
      const next = new Map(prev);
      const cur = next.get(equipo_id) ?? 0;
      const nv = Math.max(0, cur + delta);
      next.set(equipo_id, nv);
      return next;
    });
  }

  function addEquipo(equipo_id: number) {
    setOverrideItems((prev) => {
      const next = new Map(prev);
      next.set(equipo_id, (next.get(equipo_id) ?? 0) + 1);
      return next;
    });
    setSearch("");
  }

  function resetOverride() {
    setOverrideItems(new Map(baselineItemsKey));
    setOverrideDesde(baseline.fecha_desde?.slice(0, 10) ?? "");
    setOverrideHasta(baseline.fecha_hasta?.slice(0, 10) ?? "");
  }

  // Diff antes/después (sin override — eso es del admin).
  const itemsDiff = solicitud.propuesta
    ? buildItemsDiff(solicitud.pedido_actual.items, solicitud.propuesta.items)
    : null;
  const fechasCambian = solicitud.propuesta
    ? solicitud.pedido_actual.fecha_desde !== solicitud.propuesta.fecha_desde
      || solicitud.pedido_actual.fecha_hasta !== solicitud.propuesta.fecha_hasta
    : false;
  const itemsCambian = itemsDiff?.some((r) => r.kind !== "same") ?? false;

  const jornadasActuales = jornadasEntre(
    solicitud.pedido_actual.fecha_desde,
    solicitud.pedido_actual.fecha_hasta,
  );
  const jornadasPropuestas = solicitud.propuesta
    ? jornadasEntre(solicitud.propuesta.fecha_desde, solicitud.propuesta.fecha_hasta)
    : jornadasActuales;
  const montoPropuesta = solicitud.propuesta
    ? calcMonto(solicitud.propuesta.items, jornadasPropuestas)
    : 0;
  const delta = montoPropuesta - solicitud.pedido_actual.monto_total;

  // Resultados de búsqueda para "agregar equipo" en el override.
  const searchResults = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q || !equiposQ.data) return [];
    return equiposQ.data.items
      .filter((e) => {
        if (overrideItems.has(e.id) && (overrideItems.get(e.id) ?? 0) > 0) return false;
        const cats = (e.categorias ?? []).map((c) => c.nombre).join(" ");
        const hay = `${e.nombre} ${e.marca ?? ""} ${cats}`.toLowerCase();
        return hay.includes(q);
      })
      .slice(0, 6);
  }, [search, equiposQ.data, overrideItems]);

  const resolveMut = useMutation({
    mutationFn: (estado: "aprobada" | "rechazada") => {
      const override = (estado === "aprobada" && hayOverride)
        ? {
            fecha_desde: overrideDesde || null,
            fecha_hasta: overrideHasta || null,
            items: overrideItemsEfectivos.map((it) => ({
              equipo_id: it.equipo_id, cantidad: it.cantidad,
            })),
          }
        : null;
      return adminApi.responderSolicitud(solicitud.id, estado, respuesta, override);
    },
    onSuccess: (resp, estado) => {
      toast.success(
        estado === "aprobada"
          ? (resp?.applied_override
              ? "Aprobada con tus cambios — pedido actualizado"
              : "Aprobada — pedido actualizado")
          : "Rechazada — cliente notificado",
      );
      setRespuesta("");
      onResolved();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const horasDesde = (Date.now() - new Date(solicitud.created_at).getTime()) / 3_600_000;
  const urgent = horasDesde > 18;

  const numero = solicitud.numero_pedido ?? solicitud.pedido_id;
  const clienteFull = `${solicitud.cliente_nombre ?? ""} ${solicitud.cliente_apellido ?? ""}`.trim();

  return (
    <article className="overflow-hidden rounded-2xl border border-amber/50 bg-card shadow-[0_8px_28px_-10px_rgba(20,16,12,0.08)]">
      <header className="flex items-start gap-3.5 px-5 py-4 border-b hairline">
        <div className="flex-1 min-w-0 flex flex-col gap-1">
          <div className="flex items-center gap-2.5 flex-wrap">
            <Link
              to="/admin/pedidos/$id"
              params={{ id: String(solicitud.pedido_id) }}
              className="font-mono text-xs font-bold tracking-wider px-2 py-0.5 rounded-full bg-surface border hairline hover:border-ink"
            >
              #{numero}
            </Link>
            <div className="font-display text-lg font-black tracking-tight text-ink">
              {clienteFull || "Sin cliente"}
            </div>
          </div>
          <div className="flex items-center gap-2.5 flex-wrap font-mono text-[10px] tracking-wide text-muted-foreground">
            {solicitud.cliente_email && <span>{solicitud.cliente_email}</span>}
            <span className="opacity-40">·</span>
            <span>Monto actual <span className="font-bold text-ink">{fmtArs(solicitud.pedido_actual.monto_total)}</span></span>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-widest text-ink">
            <span className="h-1.5 w-1.5 rounded-full bg-ink animate-pulse" />
            Pendiente
          </span>
          <span
            className={
              "inline-flex items-center gap-1 font-mono text-[10px] font-semibold " +
              (urgent ? "text-destructive" : "text-muted-foreground")
            }
          >
            <Clock className="h-3 w-3" />
            {fmtRelative(solicitud.created_at)}
          </span>
        </div>
      </header>

      {solicitud.mensaje && (
        <div className="mx-5 mt-4 flex gap-2.5 rounded-md border border-amber/30 bg-amber-soft p-3">
          <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-amber" />
          <div className="flex-1 text-sm leading-snug text-ink whitespace-pre-wrap">
            <strong className="block mb-1 font-mono text-[9px] font-bold uppercase tracking-widest text-muted-foreground">
              Mensaje del cliente
            </strong>
            {solicitud.mensaje}
          </div>
        </div>
      )}

      {/* Diff section */}
      {solicitud.propuesta ? (
        <div className="px-5 py-4">
          <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground mb-2.5">
            Cambios propuestos
          </div>
          {!fechasCambian && !itemsCambian ? (
            <div className="rounded-md bg-surface px-3 py-2 text-xs italic text-muted-foreground">
              Sin cambios estructurales detectados — solo nota libre del cliente.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-[1fr_24px_1fr] gap-3.5 items-stretch">
              <DiffCol
                title="Pedido actual"
                fechaDesde={solicitud.pedido_actual.fecha_desde}
                fechaHasta={solicitud.pedido_actual.fecha_hasta}
                jornadas={jornadasActuales}
                items={solicitud.pedido_actual.items.map((it) => ({
                  key: String(it.equipo_id),
                  nombre: it.nombre_publico || it.nombre,
                  cantidad: it.cantidad,
                  kind: "same" as DiffRowKind,
                }))}
                total={solicitud.pedido_actual.monto_total}
                tone="before"
              />
              <div className="hidden sm:grid place-items-center text-amber">
                <ArrowRight className="h-4 w-4" />
              </div>
              <DiffCol
                title="Propuesta del cliente"
                fechaDesde={solicitud.propuesta.fecha_desde}
                fechaHasta={solicitud.propuesta.fecha_hasta}
                jornadas={jornadasPropuestas}
                items={itemsDiff!.map((r) => ({
                  key: String(r.equipo_id),
                  nombre: r.nombre,
                  cantidad: r.despues,
                  antes: r.antes,
                  kind: r.kind,
                }))}
                total={montoPropuesta}
                delta={delta}
                tone="after"
              />
            </div>
          )}
        </div>
      ) : (
        <div className="px-5 py-3 mt-1">
          <div className="rounded-md border border-dashed border-hairline bg-surface px-3 py-2 text-xs text-muted-foreground">
            El cliente mandó solo una nota libre, sin propuesta estructurada. Si vas a aplicar cambios, usá "Aprobar con cambios" abajo o editá el pedido a mano.
          </div>
        </div>
      )}

      {/* Override editor */}
      <div className="px-5 pb-4">
        <button
          type="button"
          onClick={() => setOverrideOpen((o) => !o)}
          className={
            "w-full flex items-center gap-2 px-3.5 py-2.5 rounded-md text-xs font-semibold transition-colors " +
            (overrideOpen
              ? "border border-amber bg-amber-soft/40 text-ink"
              : "border border-dashed border-hairline text-muted-foreground hover:text-ink hover:border-solid hover:border-ink")
          }
        >
          <Pencil className={"h-3.5 w-3.5 " + (overrideOpen ? "text-amber" : "text-muted-foreground")} />
          <span>Aprobar con cambios</span>
          {hayOverride && (
            <span className="rounded-full bg-amber px-2 py-0.5 font-mono text-[9px] font-bold uppercase tracking-widest text-ink">
              Modificado
            </span>
          )}
          <ChevronDown className={"h-3.5 w-3.5 ml-auto transition-transform " + (overrideOpen ? "rotate-180" : "")} />
        </button>

        {overrideOpen && (
          <div className="mt-3 p-3.5 rounded-md border border-amber bg-card flex flex-col gap-3.5">
            <div className="grid grid-cols-2 gap-2.5">
              <label className="flex flex-col gap-1">
                <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">Desde</span>
                <Input
                  type="date"
                  value={overrideDesde}
                  onChange={(e) => setOverrideDesde(e.target.value)}
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">Hasta</span>
                <Input
                  type="date"
                  value={overrideHasta}
                  min={overrideDesde || undefined}
                  onChange={(e) => setOverrideHasta(e.target.value)}
                />
              </label>
            </div>

            <div>
              <div className="flex items-baseline justify-between mb-1.5">
                <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                  Equipos
                </span>
                {hayOverride && (
                  <button
                    type="button"
                    onClick={resetOverride}
                    className="inline-flex items-center gap-1 rounded-full border hairline px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground hover:text-ink hover:border-ink transition-colors"
                  >
                    <RotateCcw className="h-2.5 w-2.5" /> Volver a propuesta
                  </button>
                )}
              </div>
              <div className="rounded-md border hairline overflow-hidden">
                {Array.from(overrideItems.entries()).map(([equipo_id, cant]) => {
                  const info = equiposPorId.get(equipo_id);
                  const original = baselineItemsKey.get(equipo_id) ?? 0;
                  const dirty = cant !== original;
                  const zeroed = cant === 0;
                  return (
                    <div
                      key={equipo_id}
                      className={
                        "flex items-center gap-2.5 px-3 py-2 border-b hairline last:border-b-0 " +
                        (zeroed
                          ? "bg-destructive/5"
                          : dirty
                            ? "bg-amber-soft/30"
                            : "bg-card")
                      }
                    >
                      <div className="flex-1 min-w-0">
                        <div className={"text-sm font-semibold leading-tight " + (zeroed ? "text-muted-foreground line-through" : "text-ink")}>
                          {info?.nombre ?? "—"}
                        </div>
                        <div className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground mt-0.5 flex gap-1.5 items-center">
                          <span>{info?.marca ?? ""}</span>
                          {dirty && original > 0 && (
                            <span className="text-amber font-bold">· cliente: ×{original}</span>
                          )}
                          {dirty && original === 0 && (
                            <span className="text-amber font-bold">· agregado por admin</span>
                          )}
                        </div>
                      </div>
                      <div className="inline-flex items-center rounded-full border hairline bg-background overflow-hidden">
                        <button
                          type="button"
                          onClick={() => bumpQty(equipo_id, -1)}
                          disabled={cant === 0}
                          className="h-7 w-7 grid place-items-center text-muted-foreground hover:bg-muted hover:text-ink disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                          <Minus className="h-3 w-3" />
                        </button>
                        <span className="font-mono text-xs font-bold text-ink tabular-nums px-1.5 min-w-[28px] text-center">
                          {cant}
                        </span>
                        <button
                          type="button"
                          onClick={() => bumpQty(equipo_id, +1)}
                          className="h-7 w-7 grid place-items-center text-muted-foreground hover:bg-muted hover:text-ink"
                        >
                          <Plus className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  );
                })}
                <div className="flex items-center gap-2 px-3 py-2 bg-amber-soft/30 border-t hairline">
                  <Search className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                  <Input
                    placeholder={equiposQ.isLoading ? "Cargando catálogo…" : "Buscar otro equipo del catálogo…"}
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="h-7 text-xs border-hairline bg-background"
                  />
                </div>
              </div>
              {searchResults.length > 0 && (
                <div className="mt-1.5 rounded-md border hairline bg-card max-h-44 overflow-y-auto">
                  {searchResults.map((eq) => (
                    <button
                      key={eq.id}
                      type="button"
                      onClick={() => addEquipo(eq.id)}
                      className="w-full text-left flex items-center gap-2 px-3 py-2 border-b hairline last:border-b-0 hover:bg-surface transition-colors"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-semibold text-ink truncate">{eq.nombre}</div>
                        <div className="font-mono text-[9px] tracking-wider text-muted-foreground truncate">
                          {eq.marca ?? "—"} · {eq.categorias?.[0]?.nombre ?? "—"} · {fmtArs(eq.precio_jornada ?? 0)}/jornada
                        </div>
                      </div>
                      <span className="h-6 w-6 grid place-items-center rounded-full bg-ink text-amber shrink-0">
                        <Plus className="h-3 w-3" strokeWidth={2.5} />
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <p className="text-[11px] italic text-muted-foreground leading-relaxed">
              Al aprobar, se aplicará tu versión en lugar de la del cliente. Cantidades en 0 quitan el equipo del pedido. Las fechas y los items efectivos sobreescriben los del pedido.
            </p>
          </div>
        )}
      </div>

      <div className="border-t hairline bg-surface px-5 py-4">
        <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground mb-1.5">
          Respuesta para el cliente (opcional)
        </div>
        <Textarea
          placeholder="Confirmá los cambios o explicá por qué rechazás…"
          value={respuesta}
          onChange={(e) => setRespuesta(e.target.value)}
          className="min-h-[58px] bg-card"
        />

        <div className="mt-3 flex gap-2">
          <Button
            type="button"
            variant="outline"
            className="flex-1 rounded-full text-destructive border-hairline hover:bg-destructive/5 hover:border-destructive hover:text-destructive"
            disabled={resolveMut.isPending}
            onClick={() => resolveMut.mutate("rechazada")}
          >
            <X className="h-4 w-4 mr-1.5" /> Rechazar
          </Button>
          <Button
            type="button"
            className={
              "flex-1 rounded-full " +
              (hayOverride
                ? "bg-amber text-ink hover:bg-amber/80"
                : "bg-ink text-amber hover:bg-amber hover:text-ink")
            }
            disabled={resolveMut.isPending || overrideVacio}
            onClick={() => resolveMut.mutate("aprobada")}
          >
            <Check className="h-4 w-4 mr-1.5" />
            {hayOverride ? "Aprobar con mis cambios" : "Aprobar tal cual"}
          </Button>
        </div>

        {overrideVacio && (
          <div className="mt-2 flex items-center gap-1.5 text-[11px] text-destructive">
            <AlertTriangle className="h-3 w-3" />
            Tu contrapropuesta deja al pedido sin equipos. Subí al menos uno a cantidad ≥ 1.
          </div>
        )}
      </div>
    </article>
  );
}

// ── DiffCol ──────────────────────────────────────────────────────────────────

function DiffCol({
  title, fechaDesde, fechaHasta, jornadas, items, total, delta, tone,
}: {
  title: string;
  fechaDesde: string | null;
  fechaHasta: string | null;
  jornadas: number;
  items: { key: string; nombre: string; cantidad: number; antes?: number; kind: DiffRowKind }[];
  total: number;
  delta?: number;
  tone: "before" | "after";
}) {
  return (
    <div
      className={
        "rounded-md border p-3 " +
        (tone === "after"
          ? "border-amber/40 bg-amber-soft/20"
          : "border-hairline bg-surface")
      }
    >
      <div className={"font-mono text-[9px] uppercase tracking-widest mb-2 " + (tone === "after" ? "text-amber" : "text-muted-foreground")}>
        {title}
      </div>
      <div className="text-sm font-semibold text-ink tabular-nums leading-snug">
        {fmtFechaLarga(fechaDesde)}
        <span className="text-muted-foreground mx-1.5">→</span>
        {fmtFechaLarga(fechaHasta)}
      </div>
      <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground mt-1">
        {jornadas} {jornadas === 1 ? "jornada" : "jornadas"}
      </div>
      <div className="flex flex-col mt-2">
        {items.map((row) => (
          <div
            key={row.key}
            className="flex items-center gap-2 py-1.5 border-b border-dashed border-hairline last:border-b-0 text-xs"
          >
            <span
              className={
                "flex-1 truncate font-medium " +
                (row.kind === "removed"
                  ? "text-muted-foreground line-through"
                  : row.kind === "added"
                    ? "text-amber font-semibold"
                    : "text-ink")
              }
            >
              {row.nombre}
            </span>
            <span
              className={
                "font-mono text-[11px] font-bold tabular-nums rounded px-1.5 py-0.5 border " +
                (row.kind === "removed"
                  ? "border-destructive/30 text-destructive"
                  : row.kind === "added"
                    ? "bg-amber-soft border-amber/50"
                    : row.kind === "changed"
                      ? "bg-amber-soft/40 border-amber/40"
                      : "bg-background border-hairline")
              }
            >
              {row.kind === "removed"
                ? "×0"
                : row.kind === "changed" && row.antes != null
                  ? (<>
                      <span className="opacity-50 mr-1 line-through">×{row.antes}</span>
                      ×{row.cantidad}
                    </>)
                  : `×${row.cantidad}`}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-2 pt-2 border-t border-dashed border-hairline flex items-baseline justify-between">
        <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
          {tone === "after" ? "Total estimado" : "Total"}
        </span>
        <span className="font-display text-base font-black text-ink tabular-nums">
          {fmtArs(total)}
        </span>
      </div>
      {delta !== undefined && delta !== 0 && (
        <div
          className={
            "mt-1 font-mono text-[10px] font-bold tracking-wide " +
            (delta > 0 ? "text-amber" : "text-green-700")
          }
        >
          {delta > 0 ? "+" : ""}{fmtArs(Math.abs(delta))} vs actual
        </div>
      )}
    </div>
  );
}

// ── ResueltaRow ──────────────────────────────────────────────────────────────

const ESTADO_PILL_CLASS: Record<SolicitudEstado, string> = {
  pendiente: "bg-amber text-ink",
  aprobada:  "bg-green-100 text-green-800",
  rechazada: "bg-red-100 text-red-800",
  cancelada: "bg-muted text-muted-foreground",
};

const ESTADO_PILL_LABEL: Record<SolicitudEstado, string> = {
  pendiente: "Pendiente",
  aprobada:  "Aprobada",
  rechazada: "Rechazada",
  cancelada: "Cancelada",
};

function ResueltaRow({ solicitud }: { solicitud: SolicitudAdmin }) {
  const numero = solicitud.numero_pedido ?? solicitud.pedido_id;
  const clienteFull = `${solicitud.cliente_nombre ?? ""} ${solicitud.cliente_apellido ?? ""}`.trim();

  return (
    <div className="mb-1.5 flex flex-wrap items-center gap-3 rounded-md border hairline bg-surface px-4 py-3 hover:border-ink transition-colors">
      <div className="flex-1 min-w-0 flex flex-wrap items-baseline gap-3">
        <Link
          to="/admin/pedidos/$id"
          params={{ id: String(solicitud.pedido_id) }}
          className="font-mono text-xs font-bold tracking-wider px-2 py-0.5 rounded-full bg-card border hairline hover:border-ink"
        >
          #{numero}
        </Link>
        <span className="text-sm font-semibold text-ink">{clienteFull || "Sin cliente"}</span>
        <span className="font-mono text-[10px] text-muted-foreground">
          {fmtFechaCorta(solicitud.created_at.slice(0, 10))}
        </span>
        {solicitud.respuesta && (
          <div className="basis-full mt-1.5 border-l-2 border-hairline pl-2.5 py-0.5 text-xs italic text-muted-foreground leading-relaxed">
            “{solicitud.respuesta}”
          </div>
        )}
      </div>
      <span
        className={
          "inline-flex items-center rounded-full px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-widest " +
          ESTADO_PILL_CLASS[solicitud.estado]
        }
      >
        {ESTADO_PILL_LABEL[solicitud.estado]}
      </span>
    </div>
  );
}
