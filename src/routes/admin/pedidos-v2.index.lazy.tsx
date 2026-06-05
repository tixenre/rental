import { createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import { useMemo, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Search,
  FileText,
  Plus,
  PanelLeft,
  Pencil,
  Coins,
  Mail,
  Box,
  ArrowRight,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

import { Button } from "@/components/ui/button";
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
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { adminApi, ESTADO_LABEL, type Pedido } from "@/lib/admin/api";
import { EstadoBadge } from "@/components/kit/EstadoBadge";
import { WhatsAppButton } from "@/components/admin/WhatsAppButton";
import {
  AdminCard,
  AdminCardHeader,
  AdminCardMeta,
  AdminCardFooter,
  AdminCardPrice,
  FAB,
} from "@/components/mobile";
import { useDocumentTitle } from "@/lib/use-document-title";
import { formatARS, formatFechaCorta } from "@/lib/format";

export const Route = createLazyFileRoute("/admin/pedidos-v2/")({
  component: PedidosV2Page,
});

// ── Helpers de fecha / cobranza ──────────────────────────────────────────────

const fmtArs = (n: number | null | undefined) => formatARS(n ?? 0);
const todayYmd = () => new Date().toISOString().slice(0, 10);
const esHoy = (s: string | null) => !!s && s.slice(0, 10) === todayYmd();

const DIAS = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
/** "lun 1 jun" — día de semana + fecha corta (matchea el prototipo). */
function fechaDia(s: string | null): string {
  if (!s) return "—";
  const d = new Date(s.slice(0, 10) + "T12:00:00");
  return `${DIAS[d.getDay()]} ${formatFechaCorta(s)}`;
}

/** "creado hace 2 h" — relativo simple desde created_at. */
function creadoHace(iso?: string): string | null {
  if (!iso) return null;
  const diff = Date.now() - new Date(iso).getTime();
  if (Number.isNaN(diff)) return null;
  const h = Math.floor(diff / 3_600_000);
  if (h < 1) return "recién";
  if (h < 24) return `hace ${h} h`;
  const d = Math.floor(h / 24);
  return `hace ${d} d`;
}

const saldoDe = (p: Pedido) => Math.max(0, (p.monto_total ?? 0) - (p.monto_pagado ?? 0));
const tieneSaldo = (p: Pedido) => !["borrador", "cancelado"].includes(p.estado) && saldoDe(p) > 0;

/** Tag de cobranza para la fila (pagado / seña / sin seña). */
function cobranzaTag(p: Pedido): { label: string; cls: string } {
  const pagado = p.monto_pagado ?? 0;
  const total = p.monto_total ?? 0;
  if (total > 0 && pagado >= total) return { label: "pagado", cls: "text-verde" };
  if (pagado > 0) return { label: `seña ${fmtArs(pagado)}`, cls: "text-muted-foreground" };
  return { label: "sin seña", cls: "text-destructive" };
}

type EstadoFilter = "activos" | "presupuesto" | "confirmado" | "cerrados" | "todos";
const ESTADO_FILTERS: { id: EstadoFilter; label: string }[] = [
  { id: "activos", label: "Activos" },
  { id: "presupuesto", label: "Solicitados" },
  { id: "confirmado", label: "Confirmados" },
  { id: "cerrados", label: "Cerrados" },
  { id: "todos", label: "Todos" },
];

type SmartChip = "retiraHoy" | "devuelveHoy" | "nuevos" | "saldo";

// ── Página ───────────────────────────────────────────────────────────────────

function PedidosV2Page() {
  useDocumentTitle("Pedidos v2 · Back Office");
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [tab, setTab] = useState<"todos" | "cobranzas">("todos");
  const [estadoF, setEstadoF] = useState<EstadoFilter>("activos");
  const [smart, setSmart] = useState<SmartChip | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [panelOpen, setPanelOpen] = useState(true);

  // Lista (mismo endpoint que la v1; per_page alto cubre el volumen real).
  const pedidosQ = useQuery({
    queryKey: ["admin", "pedidos", "v2", { q, tab }],
    queryFn: () =>
      adminApi.listPedidos({
        q: q || undefined,
        con_saldo: tab === "cobranzas" || undefined,
        per_page: 200,
      }),
    refetchInterval: 5000,
  });

  const solicitudesQ = useQuery({
    queryKey: ["admin", "solicitudes", "count"],
    queryFn: () => adminApi.listPedidos({ estado: "solicitado", per_page: 1 }),
  });
  const pendientes = solicitudesQ.data?.total ?? 0;

  const raw = useMemo(() => pedidosQ.data?.items ?? [], [pedidosQ.data]);

  // Conteos para smart-chips + estado chips.
  const counts = useMemo(
    () => ({
      retiraHoy: raw.filter((p) => esHoy(p.fecha_desde) && p.estado === "confirmado").length,
      devuelveHoy: raw.filter((p) => esHoy(p.fecha_hasta) && p.estado === "retirado").length,
      nuevos: raw.filter((p) => p.estado === "presupuesto" || p.estado === "solicitado").length,
      saldo: raw.filter(tieneSaldo).length,
      activos: raw.filter((p) => p.estado !== "finalizado" && p.estado !== "cancelado").length,
    }),
    [raw],
  );

  // Pipeline de filtros: tab (lo aplica el backend con con_saldo) → smart-chip → estado.
  const items = useMemo(() => {
    let list = raw;
    if (smart === "retiraHoy")
      list = list.filter((p) => esHoy(p.fecha_desde) && p.estado === "confirmado");
    else if (smart === "devuelveHoy")
      list = list.filter((p) => esHoy(p.fecha_hasta) && p.estado === "retirado");
    else if (smart === "nuevos")
      list = list.filter((p) => p.estado === "presupuesto" || p.estado === "solicitado");
    else if (smart === "saldo") list = list.filter(tieneSaldo);

    if (tab === "cobranzas") return list; // ya filtrado por con_saldo en el backend
    if (estadoF === "activos")
      return list.filter((p) => p.estado !== "finalizado" && p.estado !== "cancelado");
    if (estadoF === "cerrados")
      return list.filter((p) => p.estado === "finalizado" || p.estado === "cancelado");
    if (estadoF === "presupuesto")
      return list.filter((p) => p.estado === "presupuesto" || p.estado === "solicitado");
    if (estadoF === "confirmado") return list.filter((p) => p.estado === "confirmado");
    return list;
  }, [raw, smart, tab, estadoF]);

  // Selección: la primera de la lista si no hay ninguna válida.
  const selId =
    selectedId != null && items.some((p) => p.id === selectedId)
      ? selectedId
      : (items[0]?.id ?? null);
  const total = pedidosQ.data?.total ?? 0;

  const openEditor = (id: number) =>
    navigate({ to: "/admin/pedidos-v2/$id", params: { id: String(id) } });

  const smartChips: { id: SmartChip; label: string; n: number; dot: string }[] = [
    { id: "retiraHoy", label: "Retiran hoy", n: counts.retiraHoy, dot: "bg-amber" },
    { id: "devuelveHoy", label: "Devuelven hoy", n: counts.devuelveHoy, dot: "bg-rosa" },
    { id: "nuevos", label: "Presupuestos nuevos", n: counts.nuevos, dot: "bg-azul" },
    { id: "saldo", label: "Con saldo", n: counts.saldo, dot: "bg-verde" },
  ];

  return (
    <div className="flex flex-col h-[calc(100dvh-var(--admin-topbar-h,56px))] min-h-0">
      {/* Header */}
      <div className="px-4 md:px-6 pt-5 pb-3 shrink-0">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-3">
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
          <div className="hidden md:flex items-center gap-2">
            <Button variant="outline" onClick={() => navigate({ to: "/admin/pedidos-v2/nuevo" })}>
              <FileText className="h-4 w-4 mr-1" /> Presupuesto
            </Button>
            <Button onClick={() => navigate({ to: "/admin/pedidos-v2/nuevo" })}>
              <Plus className="h-4 w-4 mr-1" /> Nuevo pedido
            </Button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 border-b hairline mt-4 -mb-px">
          <TabBtn active={tab === "todos"} onClick={() => setTab("todos")}>
            Todos
          </TabBtn>
          <TabBtn active={tab === "cobranzas"} onClick={() => setTab("cobranzas")}>
            <Coins className="h-3.5 w-3.5" /> Cobranzas
          </TabBtn>
          <TabBtn
            active={false}
            onClick={() => navigate({ to: "/admin/solicitudes" })}
            badge={pendientes}
          >
            <Pencil className="h-3.5 w-3.5" /> Solicitudes
          </TabBtn>
        </div>

        {/* Smart-chips */}
        <div className="flex flex-wrap items-center gap-1.5 mt-3">
          {smartChips.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => setSmart(smart === c.id ? null : c.id)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                smart === c.id
                  ? "border-ink bg-surface text-ink"
                  : "border-hairline text-muted-foreground hover:text-ink hover:border-ink",
              )}
            >
              <span className={cn("h-1.5 w-1.5 rounded-full", c.dot)} />
              {c.label}
              <span className="font-mono text-[10px] tabular-nums text-ink/70">{c.n}</span>
            </button>
          ))}
        </div>

        {/* Búsqueda + chips de estado */}
        <div className="flex flex-col md:flex-row md:items-center gap-2 mt-3">
          <div className="relative md:max-w-sm flex-1">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Buscar cliente o número…"
              className="pl-9"
            />
          </div>
          {tab === "todos" && (
            <div className="flex flex-wrap items-center gap-1.5 md:ml-auto">
              {ESTADO_FILTERS.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setEstadoF(f.id)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors",
                    estadoF === f.id
                      ? "bg-ink text-amber border-ink"
                      : "border-hairline text-muted-foreground hover:text-ink hover:border-ink",
                  )}
                >
                  {f.label}
                  {f.id === "activos" && (
                    <span className="font-mono text-[10px] tabular-nums">{counts.activos}</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Split master / detail (desktop) */}
      <div className="flex-1 min-h-0 hidden md:flex border-t hairline">
        <div
          className={cn(
            "shrink-0 flex flex-col min-h-0 border-r hairline",
            panelOpen ? "w-[360px]" : "flex-1",
          )}
        >
          {!panelOpen && (
            <div className="flex items-center gap-2 px-4 py-2 border-b hairline bg-surface-elevated shrink-0">
              <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {items.length} pedido{items.length !== 1 ? "s" : ""}
              </span>
              <div className="flex-1" />
              <button
                type="button"
                onClick={() => setPanelOpen(true)}
                aria-label="Mostrar detalle"
                className="inline-flex h-7 w-7 items-center justify-center rounded-md border hairline text-muted-foreground hover:text-ink"
              >
                <PanelLeft className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
          <div className="flex-1 overflow-y-auto">
            <MasterList
              items={items}
              loading={pedidosQ.isLoading}
              selId={selId}
              onSelect={setSelectedId}
              onOpen={openEditor}
            />
          </div>
        </div>
        {panelOpen && (
          <div className="flex-1 min-w-0 overflow-y-auto bg-surface/40">
            <PreviewPane
              id={selId}
              onOpen={openEditor}
              onTogglePanel={() => setPanelOpen(false)}
              onDeleted={() => setSelectedId(null)}
            />
          </div>
        )}
      </div>

      {/* Mobile: cards */}
      <div className="md:hidden flex-1 overflow-y-auto px-4 pb-24 space-y-3 border-t hairline pt-3">
        {pedidosQ.isLoading &&
          Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full rounded-xl" />
          ))}
        {!pedidosQ.isLoading && items.length === 0 && (
          <div className="py-12 text-center text-sm text-muted-foreground">Sin pedidos.</div>
        )}
        {items.map((p) => (
          <AdminCard key={p.id} onClick={() => openEditor(p.id)}>
            <AdminCardHeader
              label={`#${p.numero_pedido ?? p.id}`}
              title={p.cliente_nombre || "Sin cliente"}
              subtitle={p.cliente_email ?? undefined}
              badge={<EstadoBadge estado={p.estado} label={ESTADO_LABEL[p.estado]} />}
            />
            <AdminCardMeta>
              {hoyTag(p) ?? (
                <>
                  {fechaDia(p.fecha_desde)} → {fechaDia(p.fecha_hasta)}
                </>
              )}
            </AdminCardMeta>
            <AdminCardFooter>
              <AdminCardPrice
                total={p.monto_total ?? 0}
                saldo={saldoDe(p) > 0 ? saldoDe(p) : null}
              />
              <WhatsAppButton pedido={p} phone={p.cliente_telefono} variant="icon" />
            </AdminCardFooter>
          </AdminCard>
        ))}
      </div>

      <FAB
        className="md:hidden"
        onClick={() => navigate({ to: "/admin/pedidos-v2/nuevo" })}
        label="Nuevo pedido"
      />
    </div>
  );
}

// ── Subcomponentes ───────────────────────────────────────────────────────────

function TabBtn({
  active,
  onClick,
  children,
  badge,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
  badge?: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 transition",
        active
          ? "border-amber text-ink"
          : "border-transparent text-muted-foreground hover:text-ink",
      )}
    >
      {children}
      {!!badge && badge > 0 && (
        <span className="inline-flex min-w-[18px] items-center justify-center rounded-full bg-amber px-1.5 font-mono text-[10px] font-bold text-ink">
          {badge}
        </span>
      )}
    </button>
  );
}

/** Tag "RETIRA HOY" / "DEVUELVE HOY" si aplica (para meta de fila/card). */
function hoyTag(p: Pedido): ReactNode | null {
  if (esHoy(p.fecha_desde) && p.estado === "confirmado")
    return (
      <span className="font-mono text-[10px] font-bold uppercase tracking-wide text-amber">
        retira hoy
      </span>
    );
  if (esHoy(p.fecha_hasta) && p.estado === "retirado")
    return (
      <span className="font-mono text-[10px] font-bold uppercase tracking-wide text-rosa">
        devuelve hoy
      </span>
    );
  return null;
}

function MasterList({
  items,
  loading,
  selId,
  onSelect,
  onOpen,
}: {
  items: Pedido[];
  loading: boolean;
  selId: number | null;
  onSelect: (id: number) => void;
  onOpen: (id: number) => void;
}) {
  if (loading) {
    return (
      <div className="p-2 space-y-1.5">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-[72px] w-full rounded-lg" />
        ))}
      </div>
    );
  }
  if (items.length === 0) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Sin pedidos.</div>;
  }
  return (
    <ul className="divide-y hairline">
      {items.map((p) => {
        const tag = cobranzaTag(p);
        const sel = p.id === selId;
        return (
          <li key={p.id}>
            <button
              type="button"
              onClick={() => onSelect(p.id)}
              onDoubleClick={() => onOpen(p.id)}
              className={cn(
                "w-full text-left px-3.5 py-2.5 transition-colors border-l-2",
                sel ? "border-amber bg-amber-soft" : "border-transparent hover:bg-surface",
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="font-medium text-ink truncate">
                  {p.cliente_nombre || "Sin cliente"}
                </span>
                <EstadoBadge estado={p.estado} label={ESTADO_LABEL[p.estado]} />
              </div>
              <div className="mt-0.5 flex items-center gap-2 font-mono text-[11px] text-muted-foreground">
                <span>#{p.numero_pedido ?? p.id}</span>
                <span>·</span>
                {hoyTag(p) ?? (
                  <span className="tabular-nums">
                    {fechaDia(p.fecha_desde)} → {fechaDia(p.fecha_hasta)}
                  </span>
                )}
              </div>
              <div className="mt-1 flex items-center justify-between gap-2">
                <span className={cn("font-mono text-[11px]", tag.cls)}>{tag.label}</span>
                <span className="font-mono text-sm tabular-nums text-ink">
                  {fmtArs(p.monto_total)}
                </span>
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function PreviewPane({
  id,
  onOpen,
  onTogglePanel,
  onDeleted,
}: {
  id: number | null;
  onOpen: (id: number) => void;
  onTogglePanel: () => void;
  onDeleted: () => void;
}) {
  const detalleQ = useQuery({
    queryKey: ["admin", "pedido", id],
    queryFn: () => adminApi.getPedido(id as number),
    enabled: id != null,
  });
  const p = detalleQ.data;
  const qc = useQueryClient();
  const [askDelete, setAskDelete] = useState(false);
  const deleteMut = useMutation({
    mutationFn: () => adminApi.deletePedido(id as number),
    onSuccess: () => {
      toast.success("Pedido eliminado");
      qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
      onDeleted();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (id == null) {
    return (
      <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
        Elegí un pedido de la lista.
      </div>
    );
  }
  if (detalleQ.isLoading || !p) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-20 w-full rounded-lg" />
        <Skeleton className="h-32 w-full rounded-lg" />
      </div>
    );
  }

  const pagado = p.monto_pagado ?? 0;
  const total = p.monto_total ?? 0;
  const saldo = Math.max(0, total - pagado);
  const jornadas = p.cantidad_jornadas ?? 1;

  return (
    <div className="p-5 md:p-6 max-w-3xl">
      {/* Header del preview */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-2xl font-bold text-ink truncate">
              {p.cliente_nombre || "Sin cliente"}
            </h2>
            <EstadoBadge estado={p.estado} label={ESTADO_LABEL[p.estado]} />
          </div>
          <div className="mt-1 font-mono text-[11px] text-muted-foreground flex items-center gap-1.5 flex-wrap">
            <span>Pedido #{p.numero_pedido ?? p.id}</span>
            {creadoHace(p.created_at) && (
              <>
                <span>·</span>
                <span>creado {creadoHace(p.created_at)}</span>
              </>
            )}
            {p.fuente && (
              <>
                <span>·</span>
                <span>{p.fuente}</span>
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <Button variant="outline" size="sm" onClick={() => onOpen(p.id)}>
            <Pencil className="h-3.5 w-3.5 mr-1" /> Editar
          </Button>
          <button
            type="button"
            onClick={() => setAskDelete(true)}
            aria-label="Eliminar pedido"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border hairline text-muted-foreground hover:border-destructive/40 hover:text-destructive"
          >
            <Trash2 className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onTogglePanel}
            aria-label="Ocultar panel"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border hairline text-muted-foreground hover:text-ink"
          >
            <PanelLeft className="h-4 w-4" />
          </button>
        </div>
      </div>

      <AlertDialog open={askDelete} onOpenChange={setAskDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminar pedido #{p.numero_pedido ?? p.id}</AlertDialogTitle>
            <AlertDialogDescription>
              Se borran también sus ítems y pagos. No se puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMut.mutate()}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Siguiente paso — abre el editor v2 (la máquina de estados real vive ahí). */}
      {!["finalizado", "cancelado"].includes(p.estado) && (
        <div className="mt-4 rounded-lg border border-amber bg-amber-soft px-4 py-3 flex items-center justify-between gap-3">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              Siguiente paso
            </div>
            <div className="font-medium text-ink">{siguientePasoLabel(p.estado)}</div>
          </div>
          <Button variant="amber" onClick={() => onOpen(p.id)} className="shrink-0">
            <ArrowRight className="h-4 w-4 mr-1" /> Gestionar
          </Button>
        </div>
      )}

      {/* Fechas + total */}
      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="rounded-xl border hairline bg-surface-elevated px-4 py-3">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Fechas
          </div>
          <div className="mt-1 text-ink font-medium tabular-nums">
            {fechaDia(p.fecha_desde)} → {fechaDia(p.fecha_hasta)}
          </div>
          <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">
            {jornadas} jornada{jornadas !== 1 ? "s" : ""}
          </div>
        </div>
        <div className="rounded-xl border hairline bg-surface-elevated px-4 py-3">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Total neto
          </div>
          <div className="mt-1 font-mono text-2xl font-semibold tabular-nums text-ink">
            {fmtArs(total)}
          </div>
          <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">
            {pagado >= total && total > 0
              ? "pagado"
              : pagado > 0
                ? `seña ${fmtArs(pagado)} · resta ${fmtArs(saldo)}`
                : "sin seña registrada"}
          </div>
        </div>
      </div>

      {/* Equipos */}
      <div className="mt-4 rounded-xl border hairline bg-surface-elevated">
        <div className="flex items-center justify-between px-4 py-2.5 border-b hairline">
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Equipos · {p.items?.length ?? 0}
          </span>
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            precio / jornada
          </span>
        </div>
        <ul className="divide-y hairline">
          {(p.items ?? []).map((it) => (
            <li key={it.id} className="flex items-center gap-3 px-4 py-2.5">
              <span className="inline-flex h-9 w-9 items-center justify-center rounded-md border hairline text-muted-foreground shrink-0">
                <Box className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-sm text-ink truncate">{it.nombre_publico || it.nombre}</div>
                {it.marca && (
                  <div className="font-mono text-[11px] text-muted-foreground">{it.marca}</div>
                )}
              </div>
              <div className="font-mono text-sm tabular-nums text-ink shrink-0">
                {it.cantidad}× {fmtArs(it.precio_jornada)}
              </div>
            </li>
          ))}
          {(p.items?.length ?? 0) === 0 && (
            <li className="px-4 py-6 text-center text-sm text-muted-foreground">
              Sin equipos cargados.
            </li>
          )}
        </ul>
      </div>

      {/* Acciones */}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <WhatsAppButton pedido={p} phone={p.cliente_telefono} />
        <Button variant="outline" onClick={() => onOpen(p.id)}>
          <Mail className="h-4 w-4 mr-1" /> Email
        </Button>
        <Button variant="outline" onClick={() => onOpen(p.id)}>
          <Coins className="h-4 w-4 mr-1" /> Registrar pago
        </Button>
        <Button variant="outline" onClick={() => onOpen(p.id)}>
          <FileText className="h-4 w-4 mr-1" /> Documentos
        </Button>
      </div>
    </div>
  );
}

/** Etiqueta informativa del próximo paso típico (la transición real la maneja el editor v1). */
function siguientePasoLabel(estado: Pedido["estado"]): string {
  const map: Partial<Record<Pedido["estado"], string>> = {
    borrador: "Cargar y presupuestar",
    presupuesto: "Confirmar pedido",
    solicitado: "Confirmar pedido",
    confirmado: "Marcar retirado",
    retirado: "Registrar devolución",
    entregado: "Registrar devolución",
    devuelto: "Cobrar saldo y finalizar",
  };
  return map[estado] ?? "Gestionar pedido";
}
